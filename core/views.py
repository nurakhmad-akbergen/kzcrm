from datetime import timedelta
import json
import secrets
import logging
from urllib import error, parse, request as urllib_request

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Max, Min, Q, Sum
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.db.models.functions import TruncDay
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from .forms import (
    AppointmentStatusForm,
    ClientProfileForm,
    GoogleSignupForm,
    RegisterForm,
    ShopProfileForm,
)
import re
from django.http import JsonResponse
from .forms import AppointmentForm, BarberForm, ServiceForm
from .models import Appointment, Barber, Client, Payment, Service, Shop
from django.utils.dateparse import parse_date
from .terminology import get_shop_labels

User = get_user_model()
logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def google_oauth_configured():
    return bool(
        settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET
    )


def build_google_redirect_uri(request):
    return request.build_absolute_uri(reverse("google_auth_callback"))


def exchange_google_code(request, code):
    body = parse.urlencode(
        {
            "code": code,
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uri": build_google_redirect_uri(request),
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")

    req = urllib_request.Request(
        GOOGLE_TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    with urllib_request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_google_userinfo(access_token):
    req = urllib_request.Request(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )

    with urllib_request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def build_google_username(email):
    base = re.sub(r"[^a-zA-Z0-9_]+", "", email.split("@", 1)[0]) or "user"
    candidate = base[:20]
    suffix = 1

    while User.objects.filter(username__iexact=candidate).exists():
        candidate = f"{base[:16]}{suffix}"
        suffix += 1

    return candidate


def send_activation_email(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    activation_url = request.build_absolute_uri(
        reverse("activate_account", kwargs={"uidb64": uid, "token": token})
    )

    subject = "Подтверждение аккаунта в Azeka$Nurchik CRM"
    message = render_to_string(
        "emails/account_activation.txt",
        {
            "user": user,
            "activation_url": activation_url,
        },
    )

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def landing_page(request):
    return render(request, "landing.html")


def google_auth_start(request):
    if not google_oauth_configured():
        messages.error(request, "Google-вход пока не настроен.")
        return redirect("login")

    state = secrets.token_urlsafe(24)
    request.session["google_oauth_state"] = state

    params = parse.urlencode(
        {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "redirect_uri": build_google_redirect_uri(request),
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "online",
            "state": state,
            "prompt": "select_account",
        }
    )

    return redirect(f"{GOOGLE_AUTH_URL}?{params}")


def google_auth_callback(request):
    expected_state = request.session.get("google_oauth_state")
    state = request.GET.get("state")
    code = request.GET.get("code")

    if not expected_state or state != expected_state:
        messages.error(request, "Не удалось подтвердить вход через Google.")
        return redirect("login")

    request.session.pop("google_oauth_state", None)

    if not code:
        messages.error(request, "Google не вернул код авторизации.")
        return redirect("login")

    try:
        token_data = exchange_google_code(request, code)
        userinfo = fetch_google_userinfo(token_data["access_token"])
    except (KeyError, error.URLError, error.HTTPError, ValueError):
        messages.error(request, "Не удалось завершить вход через Google.")
        return redirect("login")

    email = (userinfo.get("email") or "").strip().lower()
    if not email:
        messages.error(request, "Google не передал email пользователя.")
        return redirect("login")

    user = User.objects.filter(email__iexact=email).first()
    if user:
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])
        login(request, user)
        messages.success(request, "Вход через Google выполнен успешно.")
        return redirect("dashboard_overview")

    request.session["google_signup_profile"] = {
        "email": email,
        "full_name": userinfo.get("name", ""),
        "given_name": userinfo.get("given_name", ""),
    }
    return redirect("google_signup")


def google_signup(request):
    profile = request.session.get("google_signup_profile")
    if not profile:
        messages.info(request, "Сначала выполните вход через Google.")
        return redirect("login")

    initial = {"username": build_google_username(profile["email"])}
    if request.method == "POST":
        form = GoogleSignupForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = User.objects.create_user(
                    username=form.cleaned_data["username"],
                    email=profile["email"],
                    password=None,
                    is_active=True,
                )
                user.set_unusable_password()
                user.save(update_fields=["password"])

                shop = Shop.objects.create(
                    owner=user,
                    name=form.cleaned_data["shop_name"],
                    industry_type=form.cleaned_data["industry_type"],
                )

                labels = get_shop_labels(shop)

                Barber.objects.create(
                    shop=shop,
                    name=f"Основной {labels['staff_singular'].lower()}",
                    commission_percent=50,
                )
                Service.objects.create(
                    shop=shop,
                    name="Базовая услуга",
                    duration_min=60,
                    price_kzt=5000,
                )

            request.session.pop("google_signup_profile", None)
            login(request, user)
            messages.success(request, "Аккаунт через Google успешно создан.")
            return redirect("dashboard_overview")
    else:
        form = GoogleSignupForm(initial=initial)

    return render(request, "google_signup.html", {"form": form, "google_email": profile["email"]})


def activation_sent(request):
    return render(request, "activation_sent.html")


def activate_account(request, uidb64, token):
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save(update_fields=["is_active"])
        messages.success(request, "Аккаунт подтверждён. Теперь можно войти.")
        return render(request, "activation_result.html", {"success": True})

    return render(request, "activation_result.html", {"success": False})


@login_required
def dashboard_overview(request):

    shop = request.user.shop
    labels = get_shop_labels(shop)
    today = timezone.localdate()
    now = timezone.now()
    month_start = today.replace(day=1)

    appointments = Appointment.objects.filter(shop=shop)
    paid_payments = Payment.objects.filter(appointment__shop=shop, is_paid=True)
    today_appointments = appointments.filter(start_at__date=today)

    upcoming_appointments = (
        appointments
        .filter(
            start_at__gte=now,
            status__in=[Appointment.Status.BOOKED, Appointment.Status.CONFIRMED],
        )
        .select_related("client", "barber", "service")
        .order_by("start_at")[:5]
    )

    total_clients = Client.objects.filter(shop=shop).count()
    total_staff = Barber.objects.filter(shop=shop, is_active=True).count()
    total_services = Service.objects.filter(shop=shop, is_active=True).count()
    today_bookings_count = today_appointments.count()
    completed_count = today_appointments.filter(
        status=Appointment.Status.DONE
    ).count()
    canceled_count = today_appointments.filter(
        status=Appointment.Status.CANCELED
    ).count()
    no_show_count = today_appointments.filter(
        status=Appointment.Status.NO_SHOW
    ).count()

    today_revenue = (
        paid_payments
        .filter(appointment__start_at__date=today)
        .aggregate(total=Sum("amount_kzt"))["total"] or 0
    )
    month_revenue = (
        paid_payments
        .filter(appointment__start_at__date__gte=month_start)
        .aggregate(total=Sum("amount_kzt"))["total"] or 0
    )
    lost_revenue_today = (
        today_appointments
        .filter(status__in=[Appointment.Status.CANCELED, Appointment.Status.NO_SHOW])
        .aggregate(total=Sum("service__price_kzt"))["total"] or 0
    )

    top_services = (
        appointments
        .values("service__name")
        .annotate(total=Count("id"))
        .order_by("-total", "service__name")[:4]
    )

    return render(request, "overview.html", {
        "today": today,
        "today_bookings_count": today_bookings_count,
        "today_revenue": today_revenue,
        "month_revenue": month_revenue,
        "total_clients": total_clients,
        "total_staff": total_staff,
        "total_services": total_services,
        "completed_count": completed_count,
        "canceled_count": canceled_count,
        "no_show_count": no_show_count,
        "lost_revenue_today": lost_revenue_today,
        "upcoming_appointments": upcoming_appointments,
        "top_services": top_services,
    })


@login_required
def client_detail(request, client_id):

    shop = request.user.shop

    client = get_object_or_404(
        Client,
        id=client_id,
        shop=shop
    )

    if request.method == "POST":
        form = ClientProfileForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, "Карточка клиента обновлена")
            return redirect("client_detail", client_id=client.id)
    else:
        form = ClientProfileForm(instance=client)

    appointments = (
        Appointment.objects
        .filter(client=client)
        .select_related("barber", "service")
        .order_by("-start_at")
    )

    now = timezone.now()
    next_appointment = (
        appointments
        .filter(
            start_at__gte=now,
            status__in=[Appointment.Status.BOOKED, Appointment.Status.CONFIRMED],
        )
        .order_by("start_at")
        .first()
    )
    last_appointment = (
        appointments
        .filter(
            start_at__lt=now,
            status=Appointment.Status.DONE,
        )
        .order_by("-start_at")
        .first()
    )

    total_spent = (
        Payment.objects
        .filter(appointment__client=client, is_paid=True)
        .aggregate(total=Sum("amount_kzt"))["total"]
        or 0
    )

    visit_count = appointments.filter(status=Appointment.Status.DONE).count()
    done_count = appointments.filter(status=Appointment.Status.DONE).count()
    avg_check = (
        Payment.objects
        .filter(appointment__client=client, is_paid=True)
        .aggregate(avg=Avg("amount_kzt"))["avg"] or 0
    )

    return render(request, "client_detail.html", {
        "client": client,
        "appointments": appointments,
        "form": form,
        "total_spent": total_spent,
        "visit_count": visit_count,
        "done_count": done_count,
        "avg_check": round(avg_check, 2),
        "next_appointment": next_appointment,
        "last_appointment": last_appointment,
    })


@login_required
def clients_list(request):
    shop = request.user.shop
    q = request.GET.get("q", "").strip()

    clients = Client.objects.filter(shop=shop)

    if q:
        clients = clients.filter(
            Q(name__icontains=q) |
            Q(phone__icontains=q) |
            Q(instagram__icontains=q)
        )

    clients = (
        clients
        .annotate(
            visits=Count(
                "appointments",
                filter=Q(appointments__status=Appointment.Status.DONE),
            ),
            total_spent=Sum("appointments__payment__amount_kzt"),
            last_visit=Max(
                "appointments__start_at",
                filter=Q(appointments__status=Appointment.Status.DONE),
            ),
            next_visit=Min(
                "appointments__start_at",
                filter=Q(
                    appointments__status__in=[
                        Appointment.Status.BOOKED,
                        Appointment.Status.CONFIRMED,
                    ],
                    appointments__start_at__gte=timezone.now(),
                ),
            ),
        )
        .order_by("-last_visit")
    )

    return render(request, "clients.html", {
        "clients": clients,
        "q": q,
    })


@login_required
def settings_dashboard(request):
    shop = request.user.shop
    labels = get_shop_labels(shop)

    configuration_items = [
        {
            "label": f"{labels['staff_plural']}",
            "done": Barber.objects.filter(shop=shop, is_active=True).exists(),
            "hint": "В системе есть хотя бы один активный сотрудник для распределения записей.",
        },
        {
            "label": "Услуги и цены",
            "done": Service.objects.filter(shop=shop, is_active=True).exists(),
            "hint": "Каталог услуг доступен для записи, оплаты и аналитики.",
        },
        {
            "label": "Часовой пояс",
            "done": bool(shop.timezone),
            "hint": "Расписание и ежедневные показатели опираются на установленный часовой пояс.",
        },
    ]

    configured_count = sum(1 for item in configuration_items if item["done"])
    configuration_total = len(configuration_items)

    return render(request, "settings_dashboard.html", {
        "configuration_items": configuration_items,
        "configured_count": configured_count,
        "configuration_total": configuration_total,
    })


@login_required
def business_settings(request):
    shop = request.user.shop

    if request.method == "POST":
        form = ShopProfileForm(request.POST, instance=shop)
        if form.is_valid():
            form.save()
            messages.success(request, "Профиль бизнеса обновлен")
            return redirect("profile_settings")
    else:
        form = ShopProfileForm(instance=shop)

    stats = {
        "clients": Client.objects.filter(shop=shop).count(),
        "staff": Barber.objects.filter(shop=shop, is_active=True).count(),
        "services": Service.objects.filter(shop=shop, is_active=True).count(),
        "appointments": Appointment.objects.filter(shop=shop).count(),
    }
    can_change_industry_template = form.can_change_industry_template

    return render(request, "settings_business.html", {
        "form": form,
        "stats": stats,
        "can_change_industry_template": can_change_industry_template,
    })


@login_required
def profile_settings(request):
    return business_settings(request)


@login_required
def delete_barber(request, barber_id):
    shop = request.user.shop
    barber = get_object_or_404(Barber, id=barber_id, shop=shop)

    barber.delete()

    messages.success(request, "Мастер удалён")
    return redirect("barbers_settings")


@login_required
def edit_barber(request, barber_id):
    shop = request.user.shop
    barber = get_object_or_404(Barber, id=barber_id, shop=shop)

    if request.method == "POST":
        form = BarberForm(request.POST, instance=barber)
        if form.is_valid():
            form.save()
            messages.success(request, "Мастер обновлён")
            return redirect("barbers_settings")
    else:
        form = BarberForm(instance=barber)

    return render(request, "edit_barber.html", {"form": form})


@login_required
def edit_service(request, service_id):
    shop = request.user.shop
    service = get_object_or_404(Service, id=service_id, shop=shop)

    if request.method == "POST":
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            messages.success(request, "Услуга обновлена")
            return redirect("services_settings")
    else:
        form = ServiceForm(instance=service)

    return render(request, "edit_service.html", {"form": form, "service": service})


@login_required
def delete_service(request, service_id):
    shop = request.user.shop
    service = get_object_or_404(Service, id=service_id, shop=shop)

    try:
        service.delete()
        messages.success(request, "Услуга удалена")
    except ProtectedError:
        messages.error(request, "Нельзя удалить услугу, которая уже используется в записях")

    return redirect("services_settings")


@login_required
def today_schedule(request):

    shop = request.user.shop

    date_str = request.GET.get("date")
    q = request.GET.get("q", "").strip()
    barber_id = request.GET.get("barber")
    status = request.GET.get("status", "").strip()

    # безопасный парсинг даты
    day = parse_date(date_str) if date_str else None

    if not day:
        day = timezone.localdate()

    week_start = day - timedelta(days=3)
    week_end = day + timedelta(days=3)

    week_days = [
        week_start + timedelta(days=i)
        for i in range(7)
    ]

    prev_week = day - timedelta(days=7)
    next_week = day + timedelta(days=7)

    appointments = (
        Appointment.objects
        .filter(shop=shop, start_at__date=day)
        .select_related("client", "barber", "service")
    )

    if q:
        appointments = appointments.filter(
            Q(client__name__icontains=q) |
            Q(client__phone__icontains=q) |
            Q(service__name__icontains=q)
        )

    if barber_id:
        appointments = appointments.filter(barber_id=barber_id)

    if status:
        appointments = appointments.filter(status=status)

    appointments = appointments.order_by("start_at")

    revenue = (
        Payment.objects.filter(
            appointment__shop=shop,
            appointment__start_at__date=day,
            is_paid=True
        )
        .aggregate(total=Sum("amount_kzt"))["total"]
        or 0
    )
    lost_revenue = (
        appointments
        .filter(status__in=[Appointment.Status.CANCELED, Appointment.Status.NO_SHOW])
        .aggregate(total=Sum("service__price_kzt"))["total"] or 0
    )

    return render(request, "today.html", {
        "appointments": appointments,
        "barbers": Barber.objects.filter(shop=shop, is_active=True).order_by("name"),
        "day": day,
        "week_days": week_days,
        "week_start": week_start,
        "week_end": week_end,
        "prev_week": prev_week,
        "next_week": next_week,
        "revenue": revenue,
        "lost_revenue": lost_revenue,
        "q": q,
        "selected_barber": str(barber_id or ""),
        "selected_status": status,
        "status_choices": [
            ("BOOKED", "Записан"),
            ("CONFIRMED", "Подтвержден"),
            ("DONE", "Пришел"),
            ("CANCELED", "Отмена"),
            ("NO_SHOW", "Не пришел"),
        ],
    })
    
    
@login_required
def create_appointment(request):
    shop = request.user.shop

    if request.method == "POST":

        form = AppointmentForm(request.POST, shop=shop)

        if form.is_valid():
            name = form.cleaned_data["client_name"].strip()
            phone = form.cleaned_data["client_phone"].strip()

            # тут телефон оььратно возвращается не забыввй
            phone_clean = re.sub(r"\D", "", phone)

            if phone_clean.startswith("8"):
                phone_clean = "7" + phone_clean[1:]

            last_10 = phone_clean[-10:]

            client = None
            for c in Client.objects.filter(shop=shop):
                existing_clean = re.sub(r"\D", "", c.phone)
                if existing_clean.endswith(last_10):
                    client = c
                    break

            if not client:
                client = Client.objects.create(
                    shop=shop,
                    name=name,
                    phone=phone_clean
                )

            appointment = form.save(commit=False)
            appointment.shop = shop
            appointment.client = client
            appointment.save()

            messages.success(request, "✅ Запись создана")
            return redirect("today_schedule")

    else:

        form = AppointmentForm(shop=shop)

    return render(request, "create.html", {"form": form})


@login_required
def mark_done(request, appointment_id):
    shop = request.user.shop
    appointment = get_object_or_404(Appointment, id=appointment_id, shop=shop)

    if request.method == "POST":
        method = request.POST.get("method") or Payment.Method.CASH

        appointment.status = Appointment.Status.DONE
        appointment.save()

        payment, _created = Payment.objects.get_or_create(
            appointment=appointment,
            defaults={
                "method": method,
                "amount_kzt": appointment.service.price_kzt,
                "is_paid": True,
            }
        )

        payment.method = method
        payment.amount_kzt = appointment.service.price_kzt
        payment.is_paid = True
        payment.save()

        messages.success(request, "💰 Оплата сохранена, запись отмечена как 'Пришел'")
        return redirect("today_schedule")

    return render(request, "pay_and_done.html", {
        "a": appointment,
        "methods": Payment.Method.choices,
    })


@login_required
def update_appointment_status(request, appointment_id, status):
    shop = request.user.shop
    appointment = get_object_or_404(Appointment, id=appointment_id, shop=shop)

    allowed_statuses = {
        Appointment.Status.CANCELED: "Отмена записи",
        Appointment.Status.NO_SHOW: "Клиент не пришел",
    }

    if status not in allowed_statuses:
        return redirect("today_schedule")

    if request.method == "POST":
        form = AppointmentStatusForm(request.POST)
        if form.is_valid():
            appointment.status = status
            appointment.comment = form.cleaned_data["comment"]
            appointment.save()
            messages.success(request, f"Статус записи обновлен: {appointment.get_status_display()}")
            return redirect("today_schedule")
    else:
        form = AppointmentStatusForm(initial={"comment": appointment.comment})

    return render(request, "appointment_status.html", {
        "appointment": appointment,
        "form": form,
        "status_title": allowed_statuses[status],
        "target_status": status,
    })


@login_required
def barber_report(request):
    shop = request.user.shop
    today = timezone.localdate()
    data = []

    for barber in Barber.objects.filter(shop=shop):
        total = (
            Payment.objects.filter(
                appointment__shop=shop,
                appointment__barber=barber,
                appointment__start_at__date=today,
                is_paid=True
            )
            .aggregate(total=Sum("amount_kzt"))["total"]
            or 0
        )

        salary = total * barber.commission_percent / 100
        owner_profit = total - salary

        data.append({
            "barber": barber,
            "total": total,
            "salary": round(salary, 2),
            "owner_profit": round(owner_profit, 2),
        })

    return render(request, "barber_report.html", {
        "data": data,
        "today": today,
    })


@login_required
def finance_dashboard(request):
    shop = request.user.shop
    today = timezone.localdate()

    # фильтр дат
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    payments = Payment.objects.filter(
        appointment__shop=shop,
        is_paid=True
    )

    if date_from:
        payments = payments.filter(
            appointment__start_at__date__gte=date_from
        )

    if date_to:
        payments = payments.filter(
            appointment__start_at__date__lte=date_to
        )

    # график по дням
    daily = (
        payments
        .annotate(day=TruncDay("appointment__start_at"))
        .values("day")
        .annotate(total=Sum("amount_kzt"))
        .order_by("day")
    )

    daily_labels = [d["day"].strftime("%d.%m") for d in daily]
    daily_totals = [d["total"] for d in daily]

    # методы оплаты
    methods = payments.values("method").annotate(total=Sum("amount_kzt"))
    method_labels = [m["method"] for m in methods]
    method_totals = [m["total"] for m in methods]

    # KPI
    today_total = payments.filter(
        appointment__start_at__date=today
    ).aggregate(total=Sum("amount_kzt"))["total"] or 0

    week_start = today - timedelta(days=today.weekday())

    week_total = payments.filter(
        appointment__start_at__date__gte=week_start
    ).aggregate(total=Sum("amount_kzt"))["total"] or 0

    month_start = today.replace(day=1)

    month_total = payments.filter(
        appointment__start_at__date__gte=month_start
    ).aggregate(total=Sum("amount_kzt"))["total"] or 0

    average_check = payments.aggregate(
        avg=Avg("amount_kzt")
    )["avg"] or 0

    top_barber = (
        payments
        .values("appointment__barber__name")
        .annotate(total=Sum("amount_kzt"))
        .order_by("-total")
        .first()
    )

    return render(request, "finance_dashboard.html", {

        "daily_labels": json.dumps(daily_labels),
        "daily_totals": json.dumps(daily_totals),

        "method_labels": json.dumps(method_labels),
        "method_totals": json.dumps(method_totals),

        "today_total": today_total,
        "week_total": week_total,
        "month_total": month_total,

        "average_check": round(average_check, 2),
        "top_barber": top_barber,

        "date_from": date_from,
        "date_to": date_to
    })
    
@login_required
def find_client(request):
    shop = request.user.shop
    phone = request.GET.get("phone", "").strip()

    if not phone:
        return JsonResponse({"exists": False})

    phone = phone.replace(" ", "")

    client = Client.objects.filter(
        shop=shop,
        phone=phone
    ).first()

    if client:
        return JsonResponse({
            "exists": True,
            "name": client.name
        })

    return JsonResponse({"exists": False})


@login_required
def barbers_settings(request):
    shop = request.user.shop
    barbers = Barber.objects.filter(shop=shop)

    if request.method == "POST":
        form = BarberForm(request.POST)
        if form.is_valid():
            barber = form.save(commit=False)
            barber.shop = shop
            barber.save()
            return redirect("barbers_settings")
    else:
        form = BarberForm()

    return render(request, "settings_barbers.html", {
        "barbers": barbers,
        "form": form
    })
    
    
@login_required
def services_settings(request):
    shop = request.user.shop
    services = Service.objects.filter(shop=shop)

    if request.method == "POST":
        form = ServiceForm(request.POST)
        if form.is_valid():
            service = form.save(commit=False)
            service.shop = shop
            service.save()
            return redirect("services_settings")
    else:
        form = ServiceForm()

    return render(request, "settings_services.html", {
        "services": services,
        "form": form
    })

    
def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save()
                    industry_type = form.cleaned_data["industry_type"]

                    shop = Shop.objects.create(
                        owner=user,
                        name=form.cleaned_data["shop_name"],
                        industry_type=industry_type,
                    )

                    labels = get_shop_labels(shop)

                    Barber.objects.create(
                        shop=shop,
                        name=f"Основной {labels['staff_singular'].lower()}",
                        commission_percent=50
                    )

                    Service.objects.create(
                        shop=shop,
                        name="Базовая услуга",
                        duration_min=60,
                        price_kzt=5000
                    )

                    send_activation_email(request, user)
            except Exception as exc:
                logger.exception("Failed to send activation email during registration")
                form.add_error(
                    "email",
                    f"Не удалось отправить письмо подтверждения. Проверь настройки почты и попробуй ещё раз. Ошибка: {exc}"
                )
            else:
                return redirect("activation_sent")
    else:
        form = RegisterForm()

    return render(request, "register.html", {"form": form})

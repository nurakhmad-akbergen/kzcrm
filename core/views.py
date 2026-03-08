from datetime import timedelta
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Avg
from django.db.models.functions import TruncDay
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.contrib.auth import login
from .forms import RegisterForm
from .models import Shop
from .models import Appointment, Barber, Payment, Client
import re
from .forms import AppointmentForm
from .models import Appointment, Barber, Payment
from .models import Shop, Barber, Service
from django.http import JsonResponse
from .forms import AppointmentForm, BarberForm
from .forms import ServiceForm
from django.db.models import Count, Sum, Max
from .models import Client, Appointment, Payment
from django.utils.dateparse import parse_date



@login_required
def client_detail(request, client_id):

    shop = request.user.shop

    client = get_object_or_404(
        Client,
        id=client_id,
        shop=shop
    )

    appointments = (
        Appointment.objects
        .filter(client=client)
        .select_related("barber", "service")
        .order_by("-start_at")
    )

    total_spent = (
        Payment.objects
        .filter(appointment__client=client, is_paid=True)
        .aggregate(total=Sum("amount_kzt"))["total"]
        or 0
    )

    return render(request, "client_detail.html", {
        "client": client,
        "appointments": appointments,
        "total_spent": total_spent
    })


@login_required
def clients_list(request):
    shop = request.user.shop

    clients = (
        Client.objects.filter(shop=shop)
        .annotate(
            visits=Count("appointments"),
            total_spent=Sum("appointments__payment__amount_kzt"),
            last_visit=Max("appointments__start_at")
        )
        .order_by("-last_visit")
    )

    return render(request, "clients.html", {
        "clients": clients
    })


@login_required
def settings_dashboard(request):
    return render(request, "settings_dashboard.html")


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
def today_schedule(request):
    shop = request.user.shop
    today = timezone.localdate()

    appointments = (
        Appointment.objects.filter(shop=shop, start_at__date=today)
        .select_related("client", "barber", "service")
        .order_by("start_at")
    )

    revenue = (
        Payment.objects.filter(
            appointment__shop=shop,
            appointment__start_at__date=today,
            is_paid=True
        )
        .aggregate(total=Sum("amount_kzt"))["total"]
        or 0
    )

    return render(request, "today.html", {
        "appointments": appointments,
        "today": today,
        "revenue": revenue,
    })
    
    
@login_required
def create_appointment(request):
    shop = request.user.shop

    if request.method == "POST":
        # 🔥 ПЕРЕДАЁМ shop В ФОРМУ
        form = AppointmentForm(request.POST, shop=shop)

        if form.is_valid():
            name = form.cleaned_data["client_name"].strip()
            phone = form.cleaned_data["client_phone"].strip()

            # очищаем телефон
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
        # 🔥 И ЗДЕСЬ ТОЖЕ ПЕРЕДАЁМ shop
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
            user = form.save()

            # создаём Shop
            shop = Shop.objects.create(
                owner=user,
                name=form.cleaned_data["shop_name"]
            )

            # 👇 создаём мастера по умолчанию
            Barber.objects.create(
                shop=shop,
                name="Основной мастер",
                commission_percent=50
            )

            # 👇 создаём услугу по умолчанию
            Service.objects.create(
                shop=shop,
                name="Стрижка",
                duration_min=60,
                price_kzt=5000
            )

            login(request, user)
            return redirect("today_schedule")
    else:
        form = RegisterForm()

    return render(request, "register.html", {"form": form})




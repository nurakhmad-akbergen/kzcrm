from django.core import mail
from django.contrib.auth.models import User
from django.test import Client as DjangoClient, RequestFactory, TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.tokens import default_token_generator
from django.utils import timezone
from unittest.mock import patch

from .context_processors import current_shop
from .models import Appointment, Barber, Client, Payment, Service, Shop
from .terminology import get_shop_labels


class TerminologyTests(TestCase):
    def test_dentistry_labels_are_applied(self):
        user = User.objects.create_user(username="dentist", password="12345678")
        shop = Shop.objects.create(
            owner=user,
            name="Dental Space",
            industry_type=Shop.IndustryType.DENTISTRY,
        )

        labels = get_shop_labels(shop)

        self.assertEqual(labels["client_singular"], "Пациент")
        self.assertEqual(labels["staff_singular"], "Врач")
        self.assertEqual(labels["booking_singular"], "Прием")


class CurrentShopContextProcessorTests(TestCase):
    def test_context_uses_authenticated_users_shop(self):
        user = User.objects.create_user(username="owner", password="12345678")
        shop = Shop.objects.create(owner=user, name="Focus CRM")
        other_user = User.objects.create_user(username="other", password="12345678")
        Shop.objects.create(owner=other_user, name="Other CRM")

        request = RequestFactory().get("/")
        request.user = user

        context = current_shop(request)

        self.assertEqual(context["current_shop"], shop)
        self.assertEqual(context["crm_labels"]["staff_singular"], "Мастер")


class DashboardOverviewTests(TestCase):
    def test_dashboard_overview_shows_business_metrics(self):
        user = User.objects.create_user(username="owner2", password="12345678")
        shop = Shop.objects.create(owner=user, name="Studio Flow")
        barber = Barber.objects.create(shop=shop, name="Main Barber")
        service = Service.objects.create(shop=shop, name="Fade", duration_min=60, price_kzt=7000)
        client = Client.objects.create(shop=shop, name="Ali", phone="77010000000")

        appointment = Appointment.objects.create(
            shop=shop,
            client=client,
            barber=barber,
            service=service,
            start_at=timezone.now() + timezone.timedelta(hours=1),
            status=Appointment.Status.BOOKED,
        )
        Payment.objects.create(
            appointment=appointment,
            method=Payment.Method.CASH,
            amount_kzt=7000,
            is_paid=True,
        )

        client_http = DjangoClient()
        client_http.login(username="owner2", password="12345678")
        response = client_http.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Обзор бизнеса")
        self.assertContains(response, "Следующие записи")
        self.assertContains(response, "7000")

    def test_guest_is_redirected_to_login_on_root(self):
        response = DjangoClient().get("/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_guest_sees_marketing_landing_on_welcome(self):
        response = DjangoClient().get("/welcome/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CRM, которая наводит порядок в записях, клиентах и деньгах.")
        self.assertContains(response, "Начать бесплатно")


class AuthenticationFlowTests(TestCase):
    def test_register_creates_inactive_user_and_sends_activation_email(self):
        response = DjangoClient().post(
            "/register/",
            {
                "email": "owner@example.com",
                "username": "owner-auth",
                "shop_name": "Auth Studio",
                "industry_type": Shop.IndustryType.DENTISTRY,
                "password1": "Strongpass123!",
                "password2": "Strongpass123!",
            },
            follow=True,
        )

        user = User.objects.get(username="owner-auth")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Подтверждение аккаунта", mail.outbox[0].subject)

    def test_activation_link_activates_user(self):
        user = User.objects.create_user(
            username="inactive-user",
            email="inactive@example.com",
            password="Strongpass123!",
            is_active=False,
        )
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        response = DjangoClient().get(reverse("activate_account", args=[uid, token]))

        user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(user.is_active)
        self.assertContains(response, "Email подтверждён")

    def test_password_reset_sends_email(self):
        User.objects.create_user(
            username="reset-user",
            email="reset@example.com",
            password="Strongpass123!",
        )

        response = DjangoClient().post(
            reverse("password_reset"),
            {"email": "reset@example.com"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Восстановление пароля", mail.outbox[0].subject)


@override_settings(
    GOOGLE_OAUTH_CLIENT_ID="google-client-id",
    GOOGLE_OAUTH_CLIENT_SECRET="google-client-secret",
)
class GoogleAuthTests(TestCase):
    def test_google_auth_start_redirects_to_google(self):
        response = DjangoClient().get(reverse("google_auth_start"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts.google.com", response["Location"])

    @patch("core.views.fetch_google_userinfo")
    @patch("core.views.exchange_google_code")
    def test_google_callback_logs_in_existing_user(self, mock_exchange_google_code, mock_fetch_google_userinfo):
        user = User.objects.create_user(
            username="google-existing",
            email="google@example.com",
            password="Strongpass123!",
            is_active=True,
        )
        Shop.objects.create(owner=user, name="Google Existing", industry_type=Shop.IndustryType.BARBERSHOP)

        mock_exchange_google_code.return_value = {"access_token": "token-123"}
        mock_fetch_google_userinfo.return_value = {"email": "google@example.com", "name": "Google User"}

        client = DjangoClient()
        session = client.session
        session["google_oauth_state"] = "state-123"
        session.save()

        response = client.get(
            reverse("google_auth_callback"),
            {"code": "google-code", "state": "state-123"},
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("dashboard_overview"))

    @patch("core.views.fetch_google_userinfo")
    @patch("core.views.exchange_google_code")
    def test_google_callback_redirects_new_user_to_signup(self, mock_exchange_google_code, mock_fetch_google_userinfo):
        mock_exchange_google_code.return_value = {"access_token": "token-123"}
        mock_fetch_google_userinfo.return_value = {"email": "new-google@example.com", "name": "New Google User"}

        client = DjangoClient()
        session = client.session
        session["google_oauth_state"] = "state-123"
        session.save()

        response = client.get(
            reverse("google_auth_callback"),
            {"code": "google-code", "state": "state-123"},
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("google_signup"))


class ClientDetailTests(TestCase):
    def test_client_detail_updates_profile(self):
        user = User.objects.create_user(username="owner3", password="12345678")
        shop = Shop.objects.create(owner=user, name="Client Hub")
        client = Client.objects.create(shop=shop, name="Aruzhan", phone="77020000000")

        client_http = DjangoClient()
        client_http.login(username="owner3", password="12345678")
        response = client_http.post(
            f"/clients/{client.id}/",
            {
                "name": "Aruzhan Updated",
                "phone": "77025554433",
                "instagram": "@aruzhan",
                "notes": "Предпочитает вечернее время",
            },
            follow=True,
        )

        client.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.name, "Aruzhan Updated")
        self.assertEqual(client.instagram, "@aruzhan")
        self.assertContains(response, "Карточка клиента обновлена")


class AppointmentStatusTests(TestCase):
    def test_can_mark_appointment_as_no_show(self):
        user = User.objects.create_user(username="owner4", password="12345678")
        shop = Shop.objects.create(owner=user, name="Status Lab")
        barber = Barber.objects.create(shop=shop, name="Specialist")
        service = Service.objects.create(shop=shop, name="Consultation", duration_min=60, price_kzt=9000)
        client = Client.objects.create(shop=shop, name="Dana", phone="77030000000")
        appointment = Appointment.objects.create(
            shop=shop,
            client=client,
            barber=barber,
            service=service,
            start_at=timezone.now() + timezone.timedelta(hours=2),
        )

        client_http = DjangoClient()
        client_http.login(username="owner4", password="12345678")
        response = client_http.post(
            f"/appointments/{appointment.id}/status/NO_SHOW/",
            {"comment": "Не ответил на звонок и не пришел"},
            follow=True,
        )

        appointment.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(appointment.status, Appointment.Status.NO_SHOW)
        self.assertEqual(appointment.comment, "Не ответил на звонок и не пришел")
        self.assertContains(response, "Статус записи обновлен")


class BusinessSettingsTests(TestCase):
    def test_can_update_business_profile(self):
        user = User.objects.create_user(username="owner5", password="12345678")
        shop = Shop.objects.create(owner=user, name="Old Name", industry_type=Shop.IndustryType.BARBERSHOP)

        client_http = DjangoClient()
        client_http.login(username="owner5", password="12345678")
        response = client_http.post(
            "/settings/business/",
            {
                "name": "New Name",
                "industry_type": Shop.IndustryType.DENTISTRY,
                "city": "Almaty",
                "phone": "+77771234567",
                "timezone": "Asia/Almaty",
            },
            follow=True,
        )

        shop.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(shop.name, "New Name")
        self.assertEqual(shop.industry_type, Shop.IndustryType.DENTISTRY)
        self.assertEqual(shop.city, "Almaty")
        self.assertContains(response, "Настройки бизнеса обновлены")


class ClientListLogicTests(TestCase):
    def test_last_visit_ignores_future_and_no_show(self):
        user = User.objects.create_user(username="owner6", password="12345678")
        shop = Shop.objects.create(owner=user, name="Clients Logic")
        barber = Barber.objects.create(shop=shop, name="Barber")
        service = Service.objects.create(shop=shop, name="Cut", duration_min=60, price_kzt=5000)
        client = Client.objects.create(shop=shop, name="Madi", phone="77040000000")

        past_done = Appointment.objects.create(
            shop=shop,
            client=client,
            barber=barber,
            service=service,
            start_at=timezone.now() - timezone.timedelta(days=2),
            status=Appointment.Status.DONE,
        )
        Appointment.objects.create(
            shop=shop,
            client=client,
            barber=barber,
            service=service,
            start_at=timezone.now() - timezone.timedelta(days=1),
            status=Appointment.Status.NO_SHOW,
        )
        future_booked = Appointment.objects.create(
            shop=shop,
            client=client,
            barber=barber,
            service=service,
            start_at=timezone.now() + timezone.timedelta(days=1),
            status=Appointment.Status.BOOKED,
        )

        client_http = DjangoClient()
        client_http.login(username="owner6", password="12345678")
        response = client_http.get("/clients/")

        annotated_client = response.context["clients"][0]
        self.assertEqual(annotated_client.last_visit.date(), past_done.start_at.date())
        self.assertEqual(annotated_client.next_visit.date(), future_booked.start_at.date())
        self.assertEqual(annotated_client.visits, 1)

    def test_client_search_filters_results(self):
        user = User.objects.create_user(username="owner9", password="12345678")
        shop = Shop.objects.create(owner=user, name="Search Clients")
        Client.objects.create(shop=shop, name="Aruzhan", phone="77050000000")
        Client.objects.create(shop=shop, name="Nursultan", phone="77059999999")

        client_http = DjangoClient()
        client_http.login(username="owner9", password="12345678")
        response = client_http.get("/clients/?q=Aru")

        clients = list(response.context["clients"])
        self.assertEqual(len(clients), 1)
        self.assertEqual(clients[0].name, "Aruzhan")


class ServiceManagementTests(TestCase):
    def test_can_edit_and_delete_unused_service(self):
        user = User.objects.create_user(username="owner7", password="12345678")
        shop = Shop.objects.create(owner=user, name="Service Lab")
        service = Service.objects.create(shop=shop, name="Old Service", duration_min=60, price_kzt=5000)

        client_http = DjangoClient()
        client_http.login(username="owner7", password="12345678")

        response = client_http.post(
            f"/settings/services/edit/{service.id}/",
            {"name": "New Service", "duration_min": 45, "price_kzt": 6500},
            follow=True,
        )
        service.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(service.name, "New Service")

        response = client_http.get(f"/settings/services/delete/{service.id}/", follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Service.objects.filter(id=service.id).exists())


class ScheduleCenteringTests(TestCase):
    def test_today_is_centered_in_default_schedule_strip(self):
        user = User.objects.create_user(username="owner8", password="12345678")
        shop = Shop.objects.create(owner=user, name="Schedule Lab")

        client_http = DjangoClient()
        client_http.login(username="owner8", password="12345678")
        response = client_http.get("/today/")

        week_days = list(response.context["week_days"])
        self.assertEqual(week_days[3], timezone.localdate())

    def test_schedule_filters_by_query_barber_and_status(self):
        user = User.objects.create_user(username="owner10", password="12345678")
        shop = Shop.objects.create(owner=user, name="Schedule Filters")
        barber_a = Barber.objects.create(shop=shop, name="Aidar")
        barber_b = Barber.objects.create(shop=shop, name="Dana")
        service = Service.objects.create(shop=shop, name="Consult", duration_min=60, price_kzt=4000)
        client_a = Client.objects.create(shop=shop, name="Aliya", phone="77061111111")
        client_b = Client.objects.create(shop=shop, name="Marat", phone="77062222222")
        today_dt = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)

        Appointment.objects.create(
            shop=shop,
            client=client_a,
            barber=barber_a,
            service=service,
            start_at=today_dt,
            status=Appointment.Status.BOOKED,
        )
        Appointment.objects.create(
            shop=shop,
            client=client_b,
            barber=barber_b,
            service=service,
            start_at=today_dt + timezone.timedelta(hours=1),
            status=Appointment.Status.CANCELED,
        )

        client_http = DjangoClient()
        client_http.login(username="owner10", password="12345678")
        response = client_http.get(f"/today/?q=Aliya&barber={barber_a.id}&status=BOOKED")

        appointments = list(response.context["appointments"])
        self.assertEqual(len(appointments), 1)
        self.assertEqual(appointments[0].client.name, "Aliya")

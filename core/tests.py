from django.core import mail
from django.core.cache import cache
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
from .models import Appointment, Barber, Client, Payment, PaymentMethod, Service, Shop
from .terminology import get_shop_labels


class TerminologyTests(TestCase):
    def setUp(self):
        cache.clear()

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
    def setUp(self):
        cache.clear()

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
    def setUp(self):
        cache.clear()

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
        response = client_http.get(reverse("dashboard_overview"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Обзор бизнеса")
        self.assertContains(response, "Следующие записи")
        self.assertContains(response, "7000")

    def test_guest_is_redirected_to_login_on_root(self):
        response = DjangoClient().get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CRM, которая наводит порядок в записях, клиентах и деньгах.")

    def test_guest_sees_marketing_landing_on_welcome(self):
        response = DjangoClient().get("/welcome/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CRM, которая наводит порядок в записях, клиентах и деньгах.")
        self.assertContains(response, "Начать бесплатно")


class AuthenticationFlowTests(TestCase):
    def setUp(self):
        cache.clear()

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

        shop = Shop.objects.get(owner=user)
        self.assertEqual(shop.access_mode, Shop.AccessMode.TRIAL)
        self.assertIsNotNone(shop.trial_ends_at)
        self.assertGreater(shop.remaining_access_days, 0)
        self.assertEqual(shop.barbers.first().name, "Главный врач")
        self.assertEqual(shop.services.first().name, "Первичная консультация")
        self.assertTrue(shop.payment_methods.filter(name="Наличные").exists())
        self.assertTrue(shop.payment_methods.filter(name="Kaspi").exists())

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

    @patch("core.views.send_activation_email")
    def test_register_does_not_leak_internal_email_error_details(self, mock_send_activation_email):
        mock_send_activation_email.side_effect = Exception("smtp://internal-host-secret")

        response = DjangoClient().post(
            "/register/",
            {
                "email": "secure-owner@example.com",
                "username": "secure-owner",
                "shop_name": "Secure Studio",
                "industry_type": Shop.IndustryType.DENTISTRY,
                "password1": "Strongpass123!",
                "password2": "Strongpass123!",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Не удалось отправить письмо подтверждения")
        self.assertNotContains(response, "smtp://internal-host-secret")

    def test_login_rate_limit_blocks_excessive_attempts(self):
        User.objects.create_user(
            username="rate-user",
            email="rate@example.com",
            password="Strongpass123!",
            is_active=True,
        )
        client = DjangoClient()

        for _ in range(5):
            client.post(
                reverse("login"),
                {"username": "rate-user", "password": "wrong-password"},
            )

        response = client.post(
            reverse("login"),
            {"username": "rate-user", "password": "wrong-password"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Слишком много попыток")

    def test_password_reset_rate_limit_blocks_excessive_attempts(self):
        User.objects.create_user(
            username="reset-limit-user",
            email="reset-limit@example.com",
            password="Strongpass123!",
            is_active=True,
        )
        client = DjangoClient()

        for _ in range(5):
            client.post(reverse("password_reset"), {"email": "reset-limit@example.com"})

        response = client.post(
            reverse("password_reset"),
            {"email": "reset-limit@example.com"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Слишком много попыток")


@override_settings(
    GOOGLE_OAUTH_CLIENT_ID="google-client-id",
    GOOGLE_OAUTH_CLIENT_SECRET="google-client-secret",
)
class GoogleAuthTests(TestCase):
    def setUp(self):
        cache.clear()

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

    def test_google_signup_creates_industry_specific_defaults(self):
        client = DjangoClient()
        session = client.session
        session["google_signup_profile"] = {
            "email": "new-google@example.com",
            "full_name": "New Google User",
            "given_name": "New",
        }
        session.save()

        response = client.post(
            reverse("google_signup"),
            {
                "username": "google-seeded",
                "shop_name": "Smile Flow",
                "industry_type": Shop.IndustryType.DENTISTRY,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        user = User.objects.get(username="google-seeded")
        shop = Shop.objects.get(owner=user)
        self.assertEqual(shop.access_mode, Shop.AccessMode.TRIAL)
        self.assertIsNotNone(shop.trial_ends_at)
        self.assertEqual(shop.barbers.first().name, "Главный врач")
        self.assertEqual(shop.services.first().name, "Первичная консультация")
        self.assertTrue(shop.payment_methods.filter(name="Наличные").exists())


class AccessControlTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_expired_trial_redirects_to_access_page(self):
        user = User.objects.create_user(username="expired-owner", password="12345678")
        shop = Shop.objects.create(
            owner=user,
            name="Expired Trial",
            access_mode=Shop.AccessMode.TRIAL,
            trial_ends_at=timezone.now() - timezone.timedelta(days=1),
        )

        client_http = DjangoClient()
        client_http.login(username="expired-owner", password="12345678")

        response = client_http.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("access_status"))

        access_response = client_http.get(reverse("access_status"))
        self.assertEqual(access_response.status_code, 200)
        self.assertContains(access_response, "Пробный период завершен")

    def test_superuser_can_extend_shop_access(self):
        superuser = User.objects.create_superuser(username="platform-admin", email="admin@example.com", password="12345678")
        owner = User.objects.create_user(username="trial-owner", password="12345678")
        shop = Shop.objects.create(
            owner=owner,
            name="Trial Shop",
            access_mode=Shop.AccessMode.TRIAL,
            trial_ends_at=timezone.now() - timezone.timedelta(days=1),
        )

        client_http = DjangoClient()
        client_http.login(username="platform-admin", password="12345678")
        response = client_http.post(
            reverse("access_management"),
            {"shop_id": shop.id, "days": 30},
            follow=True,
        )

        shop.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(shop.access_mode, Shop.AccessMode.SUBSCRIPTION)
        self.assertIsNotNone(shop.subscription_ends_at)
        self.assertTrue(shop.has_active_access)


class ClientDetailTests(TestCase):
    def setUp(self):
        cache.clear()

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
    def setUp(self):
        cache.clear()

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

    def test_mark_done_saves_selected_payment_method(self):
        user = User.objects.create_user(username="owner4-paid", password="12345678")
        shop = Shop.objects.create(owner=user, name="Payments Lab")
        barber = Barber.objects.create(shop=shop, name="Specialist")
        service = Service.objects.create(shop=shop, name="Consultation", duration_min=60, price_kzt=9000)
        client = Client.objects.create(shop=shop, name="Dana", phone="77030000000")
        payment_method = PaymentMethod.objects.create(shop=shop, name="Kaspi QR")
        appointment = Appointment.objects.create(
            shop=shop,
            client=client,
            barber=barber,
            service=service,
            start_at=timezone.now() + timezone.timedelta(hours=2),
        )

        client_http = DjangoClient()
        client_http.login(username="owner4-paid", password="12345678")
        response = client_http.post(
            reverse("mark_done", args=[appointment.id]),
            {"payment_method": payment_method.id},
            follow=True,
        )

        appointment.refresh_from_db()
        payment = appointment.payment

        self.assertEqual(response.status_code, 200)
        self.assertEqual(appointment.status, Appointment.Status.DONE)
        self.assertEqual(payment.payment_method, payment_method)
        self.assertEqual(payment.method_label, "Kaspi QR")
        self.assertTrue(payment.is_paid)


class BusinessSettingsTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_profile_route_is_available(self):
        user = User.objects.create_user(username="owner5-profile", password="12345678")
        shop = Shop.objects.create(owner=user, name="Profile Route", industry_type=Shop.IndustryType.BARBERSHOP)

        client_http = DjangoClient()
        client_http.login(username="owner5-profile", password="12345678")
        response = client_http.get(reverse("profile_settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Профиль бизнеса")
        self.assertContains(response, shop.name)

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
        self.assertContains(response, "Профиль бизнеса обновлен")

    def test_locks_industry_template_after_operational_data_exists(self):
        user = User.objects.create_user(username="owner5-locked", password="12345678")
        shop = Shop.objects.create(owner=user, name="Dental Flow", industry_type=Shop.IndustryType.DENTISTRY)
        barber = Barber.objects.create(shop=shop, name="Doctor")
        service = Service.objects.create(shop=shop, name="Cleaning", duration_min=60, price_kzt=12000)
        client = Client.objects.create(shop=shop, name="Patient", phone="77071112233")
        Appointment.objects.create(
            shop=shop,
            client=client,
            barber=barber,
            service=service,
            start_at=timezone.now() + timezone.timedelta(hours=3),
        )

        client_http = DjangoClient()
        client_http.login(username="owner5-locked", password="12345678")
        response = client_http.post(
            "/settings/business/",
            {
                "name": "Dental Flow",
                "industry_type": Shop.IndustryType.BARBERSHOP,
                "city": "",
                "phone": "",
                "timezone": "Asia/Almaty",
            },
            follow=True,
        )

        shop.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(shop.industry_type, Shop.IndustryType.DENTISTRY)
        self.assertContains(response, "Смена шаблона заблокирована")
        self.assertContains(response, "Отраслевой шаблон")


class ClientListLogicTests(TestCase):
    def setUp(self):
        cache.clear()

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
    def setUp(self):
        cache.clear()

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

        response = client_http.post(f"/settings/services/delete/{service.id}/", follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Service.objects.filter(id=service.id).exists())

    def test_delete_service_rejects_get_request(self):
        user = User.objects.create_user(username="owner7-get", password="12345678")
        shop = Shop.objects.create(owner=user, name="Service Lab")
        service = Service.objects.create(shop=shop, name="Old Service", duration_min=60, price_kzt=5000)

        client_http = DjangoClient()
        client_http.login(username="owner7-get", password="12345678")

        response = client_http.get(f"/settings/services/delete/{service.id}/")

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Service.objects.filter(id=service.id).exists())


class PaymentMethodSettingsTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_can_add_payment_method(self):
        user = User.objects.create_user(username="owner-payments", password="12345678")
        shop = Shop.objects.create(owner=user, name="Methods Hub")

        client_http = DjangoClient()
        client_http.login(username="owner-payments", password="12345678")
        response = client_http.post(
            reverse("payment_methods_settings"),
            {"name": "Kaspi QR"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(PaymentMethod.objects.filter(shop=shop, name="Kaspi QR").exists())
        self.assertContains(response, "Способ оплаты добавлен")

    def test_cannot_add_duplicate_payment_method(self):
        user = User.objects.create_user(username="owner-payments-duplicate", password="12345678")
        shop = Shop.objects.create(owner=user, name="Methods Hub")
        PaymentMethod.objects.create(shop=shop, name="Kaspi QR")

        client_http = DjangoClient()
        client_http.login(username="owner-payments-duplicate", password="12345678")
        response = client_http.post(
            reverse("payment_methods_settings"),
            {"name": "kaspi qr"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PaymentMethod.objects.filter(shop=shop, name__iexact="Kaspi QR").count(), 1)
        self.assertContains(response, "Такой способ оплаты уже добавлен.")

    def test_cannot_delete_used_payment_method(self):
        user = User.objects.create_user(username="owner-payments-protected", password="12345678")
        shop = Shop.objects.create(owner=user, name="Methods Hub")
        barber = Barber.objects.create(shop=shop, name="Specialist")
        service = Service.objects.create(shop=shop, name="Consultation", duration_min=60, price_kzt=9000)
        client = Client.objects.create(shop=shop, name="Dana", phone="77030000000")
        payment_method = PaymentMethod.objects.create(shop=shop, name="Kaspi QR")
        appointment = Appointment.objects.create(
            shop=shop,
            client=client,
            barber=barber,
            service=service,
            start_at=timezone.now() - timezone.timedelta(hours=2),
            status=Appointment.Status.DONE,
        )
        Payment.objects.create(
            appointment=appointment,
            payment_method=payment_method,
            method=Payment.Method.TRANSFER,
            amount_kzt=service.price_kzt,
            is_paid=True,
        )

        client_http = DjangoClient()
        client_http.login(username="owner-payments-protected", password="12345678")
        response = client_http.post(
            reverse("delete_payment_method", args=[payment_method.id]),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(PaymentMethod.objects.filter(id=payment_method.id).exists())
        self.assertContains(response, "Нельзя удалить способ оплаты, который уже использовался в платежах")


class FinanceDashboardTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_finance_dashboard_uses_custom_payment_method_labels(self):
        user = User.objects.create_user(username="finance-owner", password="12345678")
        shop = Shop.objects.create(owner=user, name="Finance Hub")
        barber = Barber.objects.create(shop=shop, name="Specialist")
        service = Service.objects.create(shop=shop, name="Consultation", duration_min=60, price_kzt=12000)
        client = Client.objects.create(shop=shop, name="Client", phone="77070000000")
        payment_method = PaymentMethod.objects.create(shop=shop, name="Kaspi QR")
        appointment = Appointment.objects.create(
            shop=shop,
            client=client,
            barber=barber,
            service=service,
            start_at=timezone.now() - timezone.timedelta(days=1),
            status=Appointment.Status.DONE,
        )
        Payment.objects.create(
            appointment=appointment,
            payment_method=payment_method,
            method=Payment.Method.TRANSFER,
            amount_kzt=service.price_kzt,
            is_paid=True,
        )

        client_http = DjangoClient()
        client_http.login(username="finance-owner", password="12345678")
        response = client_http.get(reverse("finance_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("Kaspi QR", response.context["method_labels"])


class StaffReportTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_report_includes_commission_and_fixed_salary_for_period(self):
        user = User.objects.create_user(username="owner-report", password="12345678")
        shop = Shop.objects.create(owner=user, name="Team Metrics")
        barber = Barber.objects.create(
            shop=shop,
            name="Amina",
            commission_percent=40,
            fixed_salary_kzt=300000,
        )
        service = Service.objects.create(shop=shop, name="Consultation", duration_min=60, price_kzt=20000)
        client = Client.objects.create(shop=shop, name="Client A", phone="77073334455")
        start_at = timezone.now().replace(day=10, hour=11, minute=0, second=0, microsecond=0)
        appointment = Appointment.objects.create(
            shop=shop,
            client=client,
            barber=barber,
            service=service,
            start_at=start_at,
            status=Appointment.Status.DONE,
        )
        Payment.objects.create(
            appointment=appointment,
            method=Payment.Method.CASH,
            amount_kzt=20000,
            is_paid=True,
        )

        client_http = DjangoClient()
        client_http.login(username="owner-report", password="12345678")
        response = client_http.get(
            "/barbers/",
            {
                "date_from": start_at.date().replace(day=1).isoformat(),
                "date_to": start_at.date().replace(day=15).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        row = response.context["data"][0]
        self.assertEqual(row["total"], 20000)
        self.assertEqual(row["commission_payout"], 8000)
        self.assertGreater(row["fixed_salary"], 0)
        self.assertEqual(row["completed_count"], 1)
        self.assertContains(response, "Итого выплата")
        self.assertContains(response, "Фикс")


class StaffDetailTests(TestCase):
    def test_staff_detail_shows_metrics_and_allows_update(self):
        user = User.objects.create_user(username="owner-staff-detail", password="12345678")
        shop = Shop.objects.create(owner=user, name="Staff Cards")
        barber = Barber.objects.create(
            shop=shop,
            name="Dana",
            commission_percent=35,
            fixed_salary_kzt=150000,
        )
        service = Service.objects.create(shop=shop, name="Consult", duration_min=60, price_kzt=12000)
        client = Client.objects.create(shop=shop, name="Aliya", phone="77074445566")
        appointment = Appointment.objects.create(
            shop=shop,
            client=client,
            barber=barber,
            service=service,
            start_at=timezone.now() - timezone.timedelta(days=1),
            status=Appointment.Status.DONE,
        )
        Payment.objects.create(
            appointment=appointment,
            method=Payment.Method.CASH,
            amount_kzt=12000,
            is_paid=True,
        )

        client_http = DjangoClient()
        client_http.login(username="owner-staff-detail", password="12345678")

        response = client_http.get(f"/staff/{barber.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Карточка")
        self.assertContains(response, "12000")
        self.assertContains(response, client.name)

        update_response = client_http.post(
            f"/staff/{barber.id}/",
            {
                "name": "Dana Updated",
                "commission_percent": 40,
                "fixed_salary_kzt": 200000,
            },
            follow=True,
        )
        barber.refresh_from_db()
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(barber.name, "Dana Updated")
        self.assertEqual(barber.commission_percent, 40)
        self.assertEqual(barber.fixed_salary_kzt, 200000)

    def test_schedule_links_to_client_and_staff_cards(self):
        user = User.objects.create_user(username="owner-schedule-links", password="12345678")
        shop = Shop.objects.create(owner=user, name="Schedule Links")
        barber = Barber.objects.create(shop=shop, name="Specialist")
        service = Service.objects.create(shop=shop, name="Session", duration_min=60, price_kzt=5000)
        client = Client.objects.create(shop=shop, name="Client", phone="77075556677")
        Appointment.objects.create(
            shop=shop,
            client=client,
            barber=barber,
            service=service,
            start_at=timezone.now(),
            status=Appointment.Status.BOOKED,
        )

        client_http = DjangoClient()
        client_http.login(username="owner-schedule-links", password="12345678")
        response = client_http.get("/today/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'/clients/{client.id}/')
        self.assertContains(response, f'/staff/{barber.id}/')


class ScheduleCenteringTests(TestCase):
    def test_today_is_centered_in_default_schedule_strip(self):
        user = User.objects.create_user(username="owner8", password="12345678")
        shop = Shop.objects.create(owner=user, name="Schedule Lab")

        client_http = DjangoClient()
        client_http.login(username="owner8", password="12345678")
        response = client_http.get("/today/")

        week_days = list(response.context["week_days"])
        self.assertEqual(week_days[3], timezone.localdate())
        self.assertEqual(response.context["mode"], "history")

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

    def test_schedule_without_date_shows_history_and_manual_date_filters_day(self):
        user = User.objects.create_user(username="owner11", password="12345678")
        shop = Shop.objects.create(owner=user, name="Schedule History")
        barber = Barber.objects.create(shop=shop, name="Specialist")
        service = Service.objects.create(shop=shop, name="Session", duration_min=60, price_kzt=6000)
        client = Client.objects.create(shop=shop, name="Dana", phone="77070001122")
        today_dt = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        old_dt = today_dt - timezone.timedelta(days=10)

        Appointment.objects.create(
            shop=shop,
            client=client,
            barber=barber,
            service=service,
            start_at=today_dt,
            status=Appointment.Status.BOOKED,
        )
        Appointment.objects.create(
            shop=shop,
            client=client,
            barber=barber,
            service=service,
            start_at=old_dt,
            status=Appointment.Status.DONE,
        )

        client_http = DjangoClient()
        client_http.login(username="owner11", password="12345678")

        history_response = client_http.get("/today/")
        self.assertEqual(history_response.context["appointments_count"], 2)
        self.assertEqual(history_response.context["mode"], "history")

        daily_response = client_http.get("/today/", {"date": today_dt.date().isoformat()})
        self.assertEqual(daily_response.context["appointments_count"], 1)
        self.assertEqual(daily_response.context["mode"], "day")

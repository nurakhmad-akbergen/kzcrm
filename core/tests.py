from django.contrib.auth.models import User
from django.test import Client as DjangoClient, RequestFactory, TestCase
from django.utils import timezone

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
        self.assertContains(response, "Сервис, который помогает вести записи, клиентов и деньги в одном месте.")
        self.assertContains(response, "Перейти к регистрации")


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

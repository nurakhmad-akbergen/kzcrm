from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User


# =========================================
# Base model
# =========================================

class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# =========================================
# Shop (SaaS multi-tenant)
# =========================================

class Shop(TimestampedModel):
    class IndustryType(models.TextChoices):
        BARBERSHOP = "BARBERSHOP", "Барбершоп"
        DENTISTRY = "DENTISTRY", "Стоматология"
        BEAUTY_SALON = "BEAUTY_SALON", "Салон красоты"
        CLINIC = "CLINIC", "Клиника"
        GENERIC = "GENERIC", "Другое"

    owner = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="shop"
    )

    name = models.CharField(max_length=120)
    industry_type = models.CharField(
        max_length=30,
        choices=IndustryType.choices,
        default=IndustryType.BARBERSHOP,
    )
    timezone = models.CharField(max_length=64, default="Asia/Almaty")
    city = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return self.name


# =========================================
# Barber
# =========================================

class Barber(TimestampedModel):
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="barbers"
    )

    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    commission_percent = models.PositiveSmallIntegerField(default=50)

    def __str__(self):
        return f"{self.name} ({self.shop.name})"


# =========================================
# Client
# =========================================

class Client(TimestampedModel):
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="clients"
    )

    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30, blank=True)
    instagram = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.phone})" if self.phone else self.name


# =========================================
# Service
# =========================================

class Service(TimestampedModel):
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="services"
    )

    name = models.CharField(max_length=120)
    duration_min = models.PositiveSmallIntegerField(default=60)
    price_kzt = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} — {self.price_kzt}₸"


# =========================================
# Appointment
# =========================================

class Appointment(TimestampedModel):

    class Status(models.TextChoices):
        BOOKED = "BOOKED", "Записан"
        CONFIRMED = "CONFIRMED", "Подтвержден"
        DONE = "DONE", "Пришел"
        CANCELED = "CANCELED", "Отмена"
        NO_SHOW = "NO_SHOW", "Не пришёл"

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="appointments"
    )

    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name="appointments"
    )

    barber = models.ForeignKey(
        Barber,
        on_delete=models.PROTECT,
        related_name="appointments"
    )

    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="appointments"
    )

    start_at = models.DateTimeField()
    end_at = models.DateTimeField(editable=False)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.BOOKED
    )

    comment = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.start_at:%d.%m %H:%M} {self.client}"

    def save(self, *args, **kwargs):

        # рассчитываем окончание
        self.end_at = self.start_at + timezone.timedelta(
            minutes=self.service.duration_min
        )

        # проверяем пересечения ТОЛЬКО внутри одного shop
        overlapping = Appointment.objects.filter(
            shop=self.shop,
            barber=self.barber,
            start_at__lt=self.end_at,
            end_at__gt=self.start_at
        ).exclude(id=self.id)

        if overlapping.exists():
            raise ValidationError(
                "У этого мастера уже есть запись в это время."
            )

        super().save(*args, **kwargs)


# =========================================
# Payment
# =========================================

class Payment(TimestampedModel):

    class Method(models.TextChoices):
        CASH = "CASH", "Наличные"
        KASPI = "KASPI", "Kaspi"
        TRANSFER = "TRANSFER", "Перевод"
        DEBT = "DEBT", "Долг"

    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.CASCADE,
        related_name="payment"
    )

    method = models.CharField(
        max_length=20,
        choices=Method.choices
    )

    amount_kzt = models.PositiveIntegerField(default=0)
    is_paid = models.BooleanField(default=False)

    def __str__(self):
        status = "оплачено" if self.is_paid else "не оплачено"
        return f"{self.amount_kzt}₸ — {self.get_method_display()} — {status}"

from django.contrib import admin
from .models import Shop, Barber, Client, Service, Appointment, Payment, PaymentMethod


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "phone", "created_at")


@admin.register(Barber)
class BarberAdmin(admin.ModelAdmin):
    list_display = ("name", "shop", "commission_percent", "is_active")
    list_filter = ("shop", "is_active")


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "instagram", "shop")
    list_filter = ("shop",)
    search_fields = ("name", "phone", "instagram")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "price_kzt", "duration_min", "shop", "is_active")
    list_filter = ("shop", "is_active")


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("start_at", "client", "barber", "service", "status", "shop")
    list_filter = ("shop", "status", "barber")
    search_fields = ("client__name", "client__phone")
    date_hierarchy = "start_at"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("appointment", "amount_kzt", "method", "is_paid", "created_at")
    list_filter = ("method", "is_paid")


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ("name", "shop", "is_active", "created_at")
    list_filter = ("shop", "is_active")

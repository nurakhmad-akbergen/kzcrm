from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from core.views import barbers_settings
from core.views import services_settings

from core.views import (
    today_schedule,
    create_appointment,
    mark_done,
    barber_report,
    finance_dashboard,
    register,
    find_client,
    edit_barber,
    delete_barber
)
from core.views import settings_dashboard
from core.views import clients_list
from core.views import client_detail

urlpatterns = [
    path('admin/', admin.site.urls),
    path("login/", auth_views.LoginView.as_view(template_name="login_plain.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("today/", today_schedule, name="today_schedule"),
    path("create/", create_appointment, name="create_appointment"),
    path("done/<int:appointment_id>/", mark_done, name="mark_done"),
    path("barbers/", barber_report, name="barber_report"),
    path("finance/", finance_dashboard, name="finance_dashboard"),
    path("register/", register, name="register"),
    path("api/find-client/", find_client, name="find_client"),
    path("settings/barbers/", barbers_settings, name="barbers_settings"),
    path("settings/services/", services_settings, name="services_settings"),
    path("settings/barbers/edit/<int:barber_id>/", edit_barber, name="edit_barber"),
    path("settings/barbers/delete/<int:barber_id>/", delete_barber, name="delete_barber"),
    path("settings/", settings_dashboard, name="settings_dashboard"),
    path("clients/", clients_list, name="clients_list"),
    path("clients/<int:client_id>/", client_detail, name="client_detail"),
    
]
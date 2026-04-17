from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from core.views import barbers_settings
from core.views import services_settings

from core.views import (
    landing_page,
    dashboard_overview,
    business_settings,
    today_schedule,
    create_appointment,
    mark_done,
    update_appointment_status,
    barber_report,
    finance_dashboard,
    register,
    find_client,
    edit_service,
    delete_service,
    edit_barber,
    delete_barber
)
from core.views import settings_dashboard
from core.views import clients_list
from core.views import client_detail

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", dashboard_overview, name="dashboard_overview"),
    path("welcome/", landing_page, name="landing_page"),
    path("login/", auth_views.LoginView.as_view(template_name="login_plain.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("today/", today_schedule, name="today_schedule"),
    path("create/", create_appointment, name="create_appointment"),
    path("done/<int:appointment_id>/", mark_done, name="mark_done"),
    path("appointments/<int:appointment_id>/status/<str:status>/", update_appointment_status, name="update_appointment_status"),
    path("barbers/", barber_report, name="barber_report"),
    path("finance/", finance_dashboard, name="finance_dashboard"),
    path("register/", register, name="register"),
    path("api/find-client/", find_client, name="find_client"),
    path("settings/barbers/", barbers_settings, name="barbers_settings"),
    path("settings/services/", services_settings, name="services_settings"),
    path("settings/business/", business_settings, name="business_settings"),
    path("settings/services/edit/<int:service_id>/", edit_service, name="edit_service"),
    path("settings/services/delete/<int:service_id>/", delete_service, name="delete_service"),
    path("settings/barbers/edit/<int:barber_id>/", edit_barber, name="edit_barber"),
    path("settings/barbers/delete/<int:barber_id>/", delete_barber, name="delete_barber"),
    path("settings/", settings_dashboard, name="settings_dashboard"),
    path("clients/", clients_list, name="clients_list"),
    path("clients/<int:client_id>/", client_detail, name="client_detail"),
    
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()

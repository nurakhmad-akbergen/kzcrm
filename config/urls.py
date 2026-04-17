from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from core.views import barbers_settings
from core.views import services_settings
from core.forms import (
    EmailOrUsernameAuthenticationForm,
    StyledPasswordResetForm,
    StyledSetPasswordForm,
)

from core.views import (
    activate_account,
    activation_sent,
    google_auth_callback,
    google_auth_start,
    google_signup,
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
    path("auth/google/", google_auth_start, name="google_auth_start"),
    path("auth/google/callback/", google_auth_callback, name="google_auth_callback"),
    path("auth/google/signup/", google_signup, name="google_signup"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="login_plain.html",
            authentication_form=EmailOrUsernameAuthenticationForm,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("register/activation-sent/", activation_sent, name="activation_sent"),
    path("activate/<uidb64>/<token>/", activate_account, name="activate_account"),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="password_reset_form.html",
            email_template_name="emails/password_reset_email.txt",
            subject_template_name="emails/password_reset_subject.txt",
            form_class=StyledPasswordResetForm,
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="password_reset_confirm.html",
            form_class=StyledSetPasswordForm,
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(template_name="password_reset_complete.html"),
        name="password_reset_complete",
    ),
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

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Appointment, Client, Barber, Service
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


class AppointmentForm(forms.ModelForm):

    client_name = forms.CharField(
        label="Имя клиента",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    client_phone = forms.CharField(
        label="Телефон",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    start_at = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            "type": "datetime-local",
            "class": "form-control"
        })
    )

    class Meta:
        model = Appointment
        fields = ["barber", "service", "start_at"]

        widgets = {
            "barber": forms.Select(attrs={"class": "form-select"}),
            "service": forms.Select(attrs={"class": "form-select"}),
        }
        
    def __init__(self, *args, shop=None, **kwargs):
        super().__init__(*args, **kwargs)

        if shop:
            self.fields["barber"].queryset = Barber.objects.filter(shop=shop)
            self.fields["service"].queryset = Service.objects.filter(shop=shop)

class RegisterForm(UserCreationForm):
    shop_name = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    username = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control"})
    )

    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control"})
    )

    class Meta:
        model = User
        fields = ["username", "shop_name", "password1", "password2"]
        
        
class BarberForm(forms.ModelForm):
    class Meta:
        model = Barber
        fields = ["name", "commission_percent"]

        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "commission_percent": forms.NumberInput(attrs={"class": "form-control"}),
        }
        
        
class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ["name", "duration_min", "price_kzt"]

        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "duration_min": forms.NumberInput(attrs={"class": "form-control"}),
            "price_kzt": forms.NumberInput(attrs={"class": "form-control"}),
        }
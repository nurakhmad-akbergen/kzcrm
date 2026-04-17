from django import forms
from .models import Appointment, Barber, Client, Service, Shop
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .terminology import get_shop_labels

INPUT_CLASS = (
    "mt-2 block w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 "
    "text-sm text-slate-900 shadow-sm outline-none transition "
    "placeholder:text-slate-400 focus:border-teal-400 focus:ring-4 "
    "focus:ring-teal-100"
)

SELECT_CLASS = (
    "mt-2 block w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 "
    "text-sm text-slate-900 shadow-sm outline-none transition "
    "focus:border-teal-400 focus:ring-4 focus:ring-teal-100"
)


class AppointmentForm(forms.ModelForm):

    client_name = forms.CharField(
        label="Имя клиента",
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Например, Алия"})
    )

    client_phone = forms.CharField(
        label="Телефон",
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "+7 777 123 45 67"})
    )

    start_at = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            "type": "datetime-local",
            "class": INPUT_CLASS
        })
    )

    class Meta:
        model = Appointment
        fields = ["barber", "service", "start_at"]

        widgets = {
            "barber": forms.Select(attrs={"class": SELECT_CLASS}),
            "service": forms.Select(attrs={"class": SELECT_CLASS}),
        }
        
    def __init__(self, *args, shop=None, **kwargs):
        super().__init__(*args, **kwargs)

        if shop:
            self.fields["barber"].queryset = Barber.objects.filter(shop=shop)
            self.fields["service"].queryset = Service.objects.filter(shop=shop)
            labels = get_shop_labels(shop)
            self.fields["barber"].label = labels["staff_singular"]
            self.fields["service"].label = "Услуга"
            self.fields["client_name"].label = f"Имя {labels['client_singular'].lower()}"
            self.fields["client_phone"].label = "Телефон"

class RegisterForm(UserCreationForm):
    shop_name = forms.CharField(
        max_length=120,
        label="Название бизнеса",
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Например, Dias Shop"})
    )

    industry_type = forms.ChoiceField(
        label="Тип бизнеса",
        choices=Shop.IndustryType.choices,
        widget=forms.Select(attrs={"class": SELECT_CLASS})
    )

    username = forms.CharField(
        label="Логин",
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Логин владельца"})
    )

    password1 = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS, "placeholder": "Минимум 8 символов"})
    )

    password2 = forms.CharField(
        label="Подтвердите пароль",
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS, "placeholder": "Повторите пароль"})
    )

    class Meta:
        model = User
        fields = ["username", "shop_name", "industry_type", "password1", "password2"]
        
        
class BarberForm(forms.ModelForm):
    class Meta:
        model = Barber
        fields = ["name", "commission_percent"]

        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Имя сотрудника"}),
            "commission_percent": forms.NumberInput(attrs={"class": INPUT_CLASS, "placeholder": "50"}),
        }

        labels = {
            "name": "Имя",
            "commission_percent": "Комиссия (%)",
        }
        
        
class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ["name", "duration_min", "price_kzt"]

        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Название услуги"}),
            "duration_min": forms.NumberInput(attrs={"class": INPUT_CLASS, "placeholder": "60"}),
            "price_kzt": forms.NumberInput(attrs={"class": INPUT_CLASS, "placeholder": "5000"}),
        }


class ClientProfileForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ["name", "phone", "instagram", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Имя клиента"}),
            "phone": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "+7 777 123 45 67"}),
            "instagram": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "@username"}),
            "notes": forms.Textarea(attrs={
                "class": INPUT_CLASS,
                "placeholder": "Предпочтения, комментарии, важные детали",
                "rows": 5,
            }),
        }
        labels = {
            "name": "Имя",
            "phone": "Телефон",
            "instagram": "Instagram",
            "notes": "Заметки",
        }


class AppointmentStatusForm(forms.Form):
    comment = forms.CharField(
        label="Комментарий",
        required=False,
        widget=forms.Textarea(attrs={
            "class": INPUT_CLASS,
            "placeholder": "Причина отмены, no-show или важная заметка",
            "rows": 4,
        }),
    )


class ShopProfileForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = ["name", "industry_type", "city", "phone", "timezone"]
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Название бизнеса"}),
            "industry_type": forms.Select(attrs={"class": SELECT_CLASS}),
            "city": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Например, Алматы"}),
            "phone": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "+7 777 123 45 67"}),
            "timezone": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Asia/Almaty"}),
        }
        labels = {
            "name": "Название бизнеса",
            "industry_type": "Тип бизнеса",
            "city": "Город",
            "phone": "Телефон",
            "timezone": "Часовой пояс",
        }

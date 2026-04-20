from django import forms
from django.db.models import Q
from .models import Appointment, Barber, Client, Service, Shop
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm, UserCreationForm
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
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Введите имя клиента"})
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
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"class": INPUT_CLASS, "placeholder": "you@example.com"})
    )

    shop_name = forms.CharField(
        max_length=120,
        label="Название бизнеса",
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Название компании или студии"})
    )

    industry_type = forms.ChoiceField(
        label="Тип бизнеса",
        choices=Shop.IndustryType.choices,
        widget=forms.Select(attrs={"class": SELECT_CLASS})
    )

    username = forms.CharField(
        label="Логин",
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Придумайте логин"})
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
        fields = ["email", "username", "shop_name", "industry_type", "password1", "password2"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Пользователь с таким email уже существует.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.is_active = False
        if commit:
            user.save()
        return user


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Email или логин",
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "you@example.com"})
    )
    password = forms.CharField(
        label="Пароль",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS, "placeholder": "Введите пароль"}),
    )

    error_messages = {
        "invalid_login": "Не удалось войти. Проверь email/логин и пароль.",
        "inactive": "Аккаунт ещё не подтверждён. Проверьте письмо на email.",
    }

    def clean(self):
        raw_username = self.cleaned_data.get("username", "").strip()
        lookup_value = raw_username
        if "@" in raw_username:
            try:
                user = User.objects.get(email__iexact=raw_username)
                self.cleaned_data["username"] = user.get_username()
                self.data = self.data.copy()
                self.data["username"] = user.get_username()
                lookup_value = user.get_username()
            except User.DoesNotExist:
                pass
        cleaned_data = super().clean()

        if self.user_cache is None:
            possible_user = User.objects.filter(
                Q(username__iexact=lookup_value) | Q(email__iexact=raw_username)
            ).first()
            password = self.cleaned_data.get("password")
            if possible_user and password and possible_user.check_password(password) and not possible_user.is_active:
                raise forms.ValidationError(
                    self.error_messages["inactive"],
                    code="inactive",
                )

        return cleaned_data


class StyledPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"class": INPUT_CLASS, "placeholder": "you@example.com"})
    )


class StyledSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label="Новый пароль",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS, "placeholder": "Минимум 8 символов"}),
    )
    new_password2 = forms.CharField(
        label="Подтвердите пароль",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS, "placeholder": "Повторите пароль"}),
    )


class GoogleSignupForm(forms.Form):
    username = forms.CharField(
        label="Логин",
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Придумайте логин"}),
    )
    shop_name = forms.CharField(
        label="Название бизнеса",
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Название компании или студии"}),
    )
    industry_type = forms.ChoiceField(
        label="Тип бизнеса",
        choices=Shop.IndustryType.choices,
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Пользователь с таким логином уже существует.")
        return username
        
        
class BarberForm(forms.ModelForm):
    class Meta:
        model = Barber
        fields = ["name", "commission_percent", "fixed_salary_kzt"]

        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Имя специалиста"}),
            "commission_percent": forms.NumberInput(attrs={"class": INPUT_CLASS, "placeholder": "50"}),
            "fixed_salary_kzt": forms.NumberInput(attrs={"class": INPUT_CLASS, "placeholder": "0"}),
        }

        labels = {
            "name": "Имя",
            "commission_percent": "Комиссия (%)",
            "fixed_salary_kzt": "Фиксированная зарплата в месяц (₸)",
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        shop = self.instance
        self.can_change_industry_template = not (
            Barber.objects.filter(shop=shop, is_active=True).exists()
            or Service.objects.filter(shop=shop, is_active=True).exists()
            or Appointment.objects.filter(shop=shop).exists()
        )

        if not self.can_change_industry_template:
            self.fields["industry_type"].disabled = True
            self.fields["industry_type"].help_text = (
                "Смена отраслевого шаблона недоступна после начала работы с услугами, "
                "сотрудниками или записями."
            )
        else:
            self.fields["industry_type"].help_text = (
                "Шаблон меняет терминологию и тексты интерфейса, но не преобразует существующие данные."
            )

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
            "industry_type": "Отраслевой шаблон",
            "city": "Город",
            "phone": "Телефон",
            "timezone": "Часовой пояс",
        }

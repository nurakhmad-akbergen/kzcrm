from django.shortcuts import redirect
from django.urls import reverse


class ShopAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)

        if not user or not user.is_authenticated:
            return self.get_response(request)

        if user.is_staff or user.is_superuser:
            return self.get_response(request)

        shop = getattr(user, "shop", None)
        if not shop or shop.has_active_access:
            return self.get_response(request)

        allowed_paths = {
            reverse("access_status"),
            reverse("logout"),
        }

        if request.path in allowed_paths:
            return self.get_response(request)

        return redirect("access_status")

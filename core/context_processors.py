from .models import Shop

def current_shop(request):
    return {"current_shop": Shop.objects.first()}
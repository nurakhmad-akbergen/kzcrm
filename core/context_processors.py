from .terminology import get_shop_labels

def current_shop(request):
    shop = None

    if getattr(request, "user", None) and request.user.is_authenticated:
        shop = getattr(request.user, "shop", None)

    return {
        "current_shop": shop,
        "crm_labels": get_shop_labels(shop),
    }

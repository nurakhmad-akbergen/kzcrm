DEFAULT_LABELS = {
    "product_name": "CRM",
    "client_singular": "Клиент",
    "client_plural": "Клиенты",
    "staff_singular": "Специалист",
    "staff_plural": "Специалисты",
    "booking_singular": "Запись",
    "booking_plural": "Записи",
    "create_booking_action": "Создать запись",
    "staff_report_title": "Отчет по команде",
}


INDUSTRY_LABELS = {
    "BARBERSHOP": {
        "product_name": "Barber CRM",
        "staff_singular": "Мастер",
        "staff_plural": "Мастера",
        "staff_report_title": "Отчет по мастерам",
    },
    "DENTISTRY": {
        "product_name": "Dental CRM",
        "client_singular": "Пациент",
        "client_plural": "Пациенты",
        "staff_singular": "Врач",
        "staff_plural": "Врачи",
        "booking_singular": "Прием",
        "booking_plural": "Приемы",
        "create_booking_action": "Создать прием",
        "staff_report_title": "Отчет по врачам",
    },
    "BEAUTY_SALON": {
        "product_name": "Beauty CRM",
        "staff_singular": "Мастер",
        "staff_plural": "Мастера",
        "staff_report_title": "Отчет по мастерам",
    },
    "CLINIC": {
        "product_name": "Clinic CRM",
        "client_singular": "Пациент",
        "client_plural": "Пациенты",
        "staff_singular": "Специалист",
        "staff_plural": "Специалисты",
        "booking_singular": "Прием",
        "booking_plural": "Приемы",
        "create_booking_action": "Создать прием",
        "staff_report_title": "Отчет по специалистам",
    },
}


def get_shop_labels(shop):
    labels = DEFAULT_LABELS.copy()

    if not shop:
        return labels

    labels.update(INDUSTRY_LABELS.get(shop.industry_type, {}))
    labels["industry_name"] = shop.get_industry_type_display()
    return labels

DEFAULT_LABELS = {
    "product_name": "KZCRMS",
    "client_singular": "Клиент",
    "client_plural": "Клиенты",
    "staff_singular": "Специалист",
    "staff_plural": "Специалисты",
    "booking_singular": "Запись",
    "booking_plural": "Записи",
    "create_booking_action": "Создать запись",
    "staff_report_title": "Отчет по команде",
}

DEFAULT_SEED_VALUES = {
    "staff_name": "Главный специалист",
    "service_name": "Первичная консультация",
}


INDUSTRY_LABELS = {
    "BARBERSHOP": {
        "staff_singular": "Мастер",
        "staff_plural": "Мастера",
        "staff_report_title": "Отчет по мастерам",
    },
    "DENTISTRY": {
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
        "staff_singular": "Мастер",
        "staff_plural": "Мастера",
        "staff_report_title": "Отчет по мастерам",
    },
    "CLINIC": {
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

INDUSTRY_SEED_VALUES = {
    "BARBERSHOP": {
        "staff_name": "Старший мастер",
        "service_name": "Мужская стрижка",
    },
    "DENTISTRY": {
        "staff_name": "Главный врач",
        "service_name": "Первичная консультация",
    },
    "BEAUTY_SALON": {
        "staff_name": "Старший мастер",
        "service_name": "Базовая процедура",
    },
    "CLINIC": {
        "staff_name": "Главный специалист",
        "service_name": "Первичный прием",
    },
    "GENERIC": {
        "staff_name": "Главный специалист",
        "service_name": "Основная услуга",
    },
}


def get_shop_labels(shop):
    labels = DEFAULT_LABELS.copy()

    if not shop:
        return labels

    labels.update(INDUSTRY_LABELS.get(shop.industry_type, {}))
    labels["industry_name"] = shop.get_industry_type_display()
    return labels


def get_shop_seed_values(shop):
    seed_values = DEFAULT_SEED_VALUES.copy()

    if not shop:
        return seed_values

    seed_values.update(INDUSTRY_SEED_VALUES.get(shop.industry_type, {}))
    return seed_values

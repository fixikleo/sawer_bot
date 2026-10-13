BOT_TOKEN = "8531131220:AAGE1js4xreID7ZipjcbeUPyN-axMFQPL7Q"

# Админ: должны совпасть ОБА
ADMIN_ID = 6115690833
ADMIN_USERNAME = "fixikleo"  # без @

DB_PATH = "savekeeper.db"

FREE_LIMIT = 10           # сколько сообщений бесплатно
REF_BONUS_DAYS = 3        # дней Pro за реферала

# Автоочистка: если БД больше этого размера — удаляем самые старые сообщения
# (не трогая Pro-пользователей). Поставь 0, чтобы отключить.
MAX_DB_SIZE_MB = 550

# Тарифы: payload -> (название, звёзд, дней)
PLANS = {
    "pro_30":  ("Pro на 30 дней",  50,  30),
    "pro_365": ("Pro на 365 дней", 400, 365),
}
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import PLANS


# ============================================================
#                     ПОЛЬЗОВАТЕЛЬСКИЕ
# ============================================================

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📜 История", callback_data="menu:history"),
            InlineKeyboardButton(text="📎 Медиа", callback_data="menu:media"),
        ],
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="menu:stats"),
            InlineKeyboardButton(text="⭐ Купить Pro", callback_data="menu:pro"),
        ],
        [
            InlineKeyboardButton(text="🎟 Промокод", callback_data="menu:promo"),
            InlineKeyboardButton(text="👥 Реферал", callback_data="menu:ref"),
        ],
        [
            InlineKeyboardButton(text="📄 Экспорт", callback_data="menu:export"),
            InlineKeyboardButton(text="📖 Помощь", callback_data="menu:help"),
        ],
    ])


def help_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Купить Pro", callback_data="menu:pro")],
        [InlineKeyboardButton(text="⬅ В меню", callback_data="menu:back")],
    ])


def buy_plans_kb(discount: int = 0):
    rows = []
    for payload, (name, stars, _days) in PLANS.items():
        final = max(1, stars - stars * discount // 100) if discount else stars
        text = f"⭐ {name} — {final} звёзд"
        if discount:
            text += f" (-{discount}%)"
        rows.append([InlineKeyboardButton(text=text, callback_data=f"buy:{payload}:{discount}")])
    rows.append([InlineKeyboardButton(text="⬅ В меню", callback_data="menu:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def promo_buy_kb(payload: str, discount: int):
    name, stars, _days = PLANS[payload]
    final = max(1, stars - stars * discount // 100)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"⭐ Купить «{name}» за {final} звёзд",
            callback_data=f"buy:{payload}:{discount}",
        )],
        [InlineKeyboardButton(text="⬅ В меню", callback_data="menu:back")],
    ])


# ============================================================
#                        АДМИНСКИЕ
# ============================================================

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="adm:users")],
        [InlineKeyboardButton(text="💰 Баланс бота", callback_data="adm:balance")],
        [InlineKeyboardButton(text="🎁 Подарки", callback_data="adm:gifts")],
        [InlineKeyboardButton(text="💸 Возвраты", callback_data="adm:refunds")],
        [InlineKeyboardButton(text="🎟 Промокоды", callback_data="adm:promos")],
        [InlineKeyboardButton(text="➕ Создать промокод", callback_data="adm:newpromo")],
        [InlineKeyboardButton(text="💸 Вывод средств", callback_data="adm:withdraw")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="adm:broadcast")],
        [InlineKeyboardButton(text="🔄 Рестарт", callback_data="adm:restart")],
    ])


def admin_restart_confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, перезапустить", callback_data="adm:restart_yes")],
        [InlineKeyboardButton(text="⬅ Отмена", callback_data="adm:menu")],
    ])


def back_to_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅ Назад", callback_data="adm:menu")
    ]])


def refunds_kb(payments):
    rows = []
    for pid, user_id, charge_id, amount, date, refunded, uname, fname in payments:
        status = "✅" if refunded else "↩️"
        who = f"@{uname}" if uname else (fname or f"ID {user_id}")
        rows.append([InlineKeyboardButton(
            text=f"{status} {who} — {amount}⭐ ({date[:10]})",
            callback_data=f"adm:refund_do:{pid}"
        )])
    rows.append([InlineKeyboardButton(text="✏️ Ввести charge_id", callback_data="adm:refund_manual")])
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="adm:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def withdraw_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Открыть Fragment.com", url="https://fragment.com/stars")],
        [InlineKeyboardButton(text="📊 Обновить баланс", callback_data="adm:withdraw")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="adm:menu")],
    ])


def admin_gifts_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Выдать Pro", callback_data="adm:gift_new")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="adm:menu")],
    ])


def gift_user_cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅ Отмена", callback_data="adm:gifts")
    ]])


def gift_days_kb(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ 30 дней", callback_data=f"adm:gift_do:{user_id}:30")],
        [InlineKeyboardButton(text="💎 365 дней", callback_data=f"adm:gift_do:{user_id}:365")],
        [InlineKeyboardButton(text="⬅ Отмена", callback_data="adm:gifts")],
    ])


def broadcast_cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅ Отмена", callback_data="adm:broadcast_cancel")
    ]])


def newpromo_plans_kb():
    rows = [
        [InlineKeyboardButton(text=name, callback_data=f"np:plan:{payload}")]
        for payload, (name, _s, _d) in PLANS.items()
    ]
    rows.append([InlineKeyboardButton(text="⬅ Отмена", callback_data="adm:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def newpromo_uses_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="♾ Безлимит", callback_data="np:uses:0")],
        [InlineKeyboardButton(text="🔑 Сгенерировать кол-во активаций", callback_data="np:generate")],
    ])


def newpromo_generate_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔑 Сгенерировать", callback_data="np:generate")
    ]])


def newpromo_save_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💾 Сохранить", callback_data="np:generate")
    ]])


def promo_created_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟 К промокодам", callback_data="adm:promos")],
        [InlineKeyboardButton(text="⬅ В меню", callback_data="adm:menu")],
    ])
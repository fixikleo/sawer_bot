import os
import sys
import asyncio
import random
import string
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher.event.bases import SkipHandler

from config import ADMIN_ID, ADMIN_USERNAME, PLANS
from database import (
    admin_overview, admin_users, list_promos,
    create_promo, delete_promo,
    get_user, grant_pro, add_gift, list_gifts, get_all_user_ids,
)
from keyboards import (
    admin_kb, back_to_menu_kb, newpromo_plans_kb,
    newpromo_uses_kb, newpromo_generate_kb, newpromo_save_kb,
    promo_created_kb, admin_restart_confirm_kb,
    admin_gifts_kb, gift_user_cancel_kb, gift_days_kb,
    broadcast_cancel_kb, withdraw_kb,
)

router = Router()

promo_draft: dict[int, dict] = {}
gift_draft: dict[int, dict] = {}
broadcast_draft: dict[int, bool] = {}


def is_admin(user_id: int, username: str | None) -> bool:
    if user_id != ADMIN_ID:
        return False
    if not username:
        return False
    return username.lstrip("@").lower() == ADMIN_USERNAME.lstrip("@").lower()


def is_admin_msg(m: Message) -> bool:
    if m.from_user and is_admin(m.from_user.id, m.from_user.username):
        return True
    if m.sender_chat and m.sender_chat.id == ADMIN_ID:
        return True
    return False


def gen_code(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


# ============================================================
#                         ВХОД
# ============================================================
@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin_msg(message):
        return await message.answer("⛔ Нет доступа.")
    await message.answer("🛠 <b>Админ-панель</b>", parse_mode="HTML", reply_markup=admin_kb())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message):
    if not is_admin_msg(message):
        raise SkipHandler()
    promo_draft.pop(message.from_user.id, None)
    gift_draft.pop(message.from_user.id, None)
    broadcast_draft.pop(message.from_user.id, None)
    await message.answer("❌ Отменено.", reply_markup=admin_kb())


@router.callback_query(F.data == "adm:menu")
async def adm_menu(cb: CallbackQuery):
    if not is_admin(cb.from_user.id, cb.from_user.username):
        return await cb.answer("Нет доступа", show_alert=True)
    await cb.message.edit_text("🛠 <b>Админ-панель</b>", parse_mode="HTML", reply_markup=admin_kb())
    await cb.answer()


# ============================================================
#                         БАЛАНС
# ============================================================
@router.callback_query(F.data == "adm:balance")
async def adm_balance(cb: CallbackQuery):
    if not is_admin(cb.from_user.id, cb.from_user.username):
        return await cb.answer("Нет доступа", show_alert=True)

    s = await admin_overview()
    text = (
        f"💰 <b>Баланс бота</b>\n\n"
        f"Всего пользователей: {s['total_users']}\n"
        f"Активных Pro: {s['active_pro']}\n"
        f"⭐ Заработано звёзд: <b>{s['total_stars']}</b>\n"
        f"🎟 Активаций промокодов: {s['promo_uses']}\n"
        f"🎁 Выдано подарков: {s['gifts_count']}\n"
        f"💾 Размер БД: {s['db_size_mb']:.1f} MB"
    )
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_menu_kb())
    await cb.answer()


# ============================================================
#                       ВЫВОД СРЕДСТВ
# ============================================================
@router.callback_query(F.data == "adm:withdraw")
async def adm_withdraw(cb: CallbackQuery):
    if not is_admin(cb.from_user.id, cb.from_user.username):
        return await cb.answer("Нет доступа", show_alert=True)

    s = await admin_overview()
    stars = s["total_stars"]
    # Примерный курс: 1 Star ≈ $0.013
    usd = stars * 0.013

    text = (
        "💸 <b>Вывод средств (Telegram Stars)</b>\n\n"
        f"⭐ Заработано звёзд: <b>{stars}</b>\n"
        f"💵 Примерно: <b>${usd:.2f}</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📌 <b>Как вывести:</b>\n\n"
        "1️⃣ Нажми «🌐 Открыть Fragment.com»\n"
        "2️⃣ Подключи TON-кошелёк (Tonkeeper, Telegram Wallet)\n"
        "3️⃣ Укажи сумму вывода (в Stars)\n"
        "4️⃣ Получи TON на кошелёк за 5–30 секунд\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ <b>Условия вывода:</b>\n"
        "• Минимум <b>1 000 Stars</b>\n"
        "• Холд <b>21 день</b> с момента поступления\n"
        "• Вывод только в <b>TON</b> (потом можно обменять на фиат)\n"
        "• Только заработанные Stars (не купленные)\n\n"
        f"{'✅' if stars >= 1000 else '❌'} Доступно к выводу: "
        f"{'да' if stars >= 1000 else f'нет (нужно ещё {1000 - stars} ⭐)'}"
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=withdraw_kb())
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=withdraw_kb())
    await cb.answer()


# ============================================================
#                       ПОЛЬЗОВАТЕЛИ
# ============================================================
@router.callback_query(F.data == "adm:users")
async def adm_users(cb: CallbackQuery):
    if not is_admin(cb.from_user.id, cb.from_user.username):
        return await cb.answer("Нет доступа", show_alert=True)

    rows = await admin_users(100)
    if not rows:
        return await cb.message.edit_text("Пользователей пока нет.", reply_markup=back_to_menu_kb())

    now = datetime.now()
    lines = ["👥 <b>Пользователи</b> (топ-100)\n"]
    for uid, uname, fname, until, paid, ref in rows:
        status = "—"
        if until and datetime.fromisoformat(until) > now:
            status = f"Pro до {until[:10]}"
        uname_str = f"@{uname}" if uname else (fname or "—")
        lines.append(
            f"<code>{uid}</code> {uname_str}\n"
            f"   └ {status} · оплачено {paid} ⭐ · ref: {ref or '—'}"
        )
    text = "\n".join(lines)

    for i in range(0, len(text), 4000):
        chunk = text[i:i + 4000]
        if i == 0:
            await cb.message.edit_text(chunk, parse_mode="HTML", reply_markup=back_to_menu_kb())
        else:
            await cb.message.answer(chunk, parse_mode="HTML")
    await cb.answer()


# ============================================================
#                         ПОДАРКИ
# ============================================================
@router.callback_query(F.data == "adm:gifts")
async def adm_gifts(cb: CallbackQuery):
    if not is_admin(cb.from_user.id, cb.from_user.username):
        return await cb.answer("Нет доступа", show_alert=True)

    rows = await list_gifts(30)
    if not rows:
        text = (
            "🎁 <b>Подарки</b>\n\n"
            "Пока никому не выдавались.\n\n"
            "Нажми «➕ Выдать Pro», чтобы подарить подписку."
        )
    else:
        lines = ["🎁 <b>Последние подарки</b>\n"]
        for aid, uid, days, created, uname, fname in rows:
            who = f"@{uname}" if uname else (fname or f"ID {uid}")
            lines.append(
                f"<code>{uid}</code> {who}\n"
                f"   └ {days} дней · {created[:16]}"
            )
        text = "\n".join(lines)

    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=admin_gifts_kb())
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=admin_gifts_kb())
    await cb.answer()


@router.callback_query(F.data == "adm:gift_new")
async def adm_gift_new(cb: CallbackQuery):
    if not is_admin(cb.from_user.id, cb.from_user.username):
        return await cb.answer("Нет доступа", show_alert=True)

    gift_draft[cb.from_user.id] = {"step": "user_id"}
    await cb.message.edit_text(
        "🎁 <b>Выдача Pro</b>\n\n"
        "Отправь следующим сообщением <b>ID пользователя</b>, "
        "которому хочешь выдать Pro.\n\n"
        "💡 ID можно посмотреть в разделе «👥 Пользователи».\n"
        "Отмена — /cancel",
        parse_mode="HTML",
        reply_markup=gift_user_cancel_kb(),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("adm:gift_do:"))
async def adm_gift_do(cb: CallbackQuery):
    if not is_admin(cb.from_user.id, cb.from_user.username):
        return await cb.answer("Нет доступа", show_alert=True)

    _, _, user_id_str, days_str = cb.data.split(":")
    user_id = int(user_id_str)
    days = int(days_str)

    u = await get_user(user_id)
    if not u:
        return await cb.answer("Пользователь не найден", show_alert=True)

    await grant_pro(user_id, days)
    await add_gift(cb.from_user.id, user_id, days)
    gift_draft.pop(cb.from_user.id, None)

    try:
        await cb.bot.send_message(
            user_id,
            f"🎁 <b>Тебе подарок!</b>\n\n"
            f"Администратор выдал тебе <b>Pro на {days} дней</b>.\n\n"
            f"Что доступно:\n"
            f"• ♾ безлимит сообщений\n"
            f"• 🔍 поиск /search\n"
            f"• 📄 экспорт /export\n\n"
            f"Приятного использования!",
            parse_mode="HTML",
        )
    except Exception:
        pass

    uname = f"@{u[1]}" if u[1] else (u[2] or "—")
    await cb.message.edit_text(
        f"✅ <b>Подарок выдан</b>\n\n"
        f"👤 {uname} (<code>{user_id}</code>)\n"
        f"⭐ Pro на {days} дней",
        parse_mode="HTML",
        reply_markup=admin_gifts_kb(),
    )
    await cb.answer("Выдано!")


# ============================================================
#                         РАССЫЛКА
# ============================================================
@router.callback_query(F.data == "adm:broadcast")
async def adm_broadcast(cb: CallbackQuery):
    if not is_admin(cb.from_user.id, cb.from_user.username):
        return await cb.answer("Нет доступа", show_alert=True)

    broadcast_draft[cb.from_user.id] = True
    await cb.message.edit_text(
        "📢 <b>Рассылка всем</b>\n\n"
        "Отправь следующим сообщением текст, который разошлётся "
        "<b>всем пользователям бота</b>.\n\n"
        "Поддерживается HTML: <code>&lt;b&gt;жирный&lt;/b&gt;</code>, "
        "<code>&lt;i&gt;курсив&lt;/i&gt;</code>, эмодзи.\n\n"
        "⚠️ Отмена — /cancel",
        parse_mode="HTML",
        reply_markup=broadcast_cancel_kb(),
    )
    await cb.answer()


@router.callback_query(F.data == "adm:broadcast_cancel")
async def adm_broadcast_cancel(cb: CallbackQuery):
    if not is_admin(cb.from_user.id, cb.from_user.username):
        return await cb.answer("Нет доступа", show_alert=True)
    broadcast_draft.pop(cb.from_user.id, None)
    await cb.message.edit_text("🛠 <b>Админ-панель</b>", parse_mode="HTML", reply_markup=admin_kb())
    await cb.answer("Отменено")


async def run_broadcast(message: Message):
    admin_id = message.from_user.id
    text = message.text

    user_ids = await get_all_user_ids()
    total = len(user_ids)

    status_msg = await message.answer(f"📢 Начинаю рассылку на {total} пользователей...")

    sent = 0
    failed = 0
    for uid in user_ids:
        try:
            await message.bot.send_message(uid, text, parse_mode="HTML")
            sent += 1
        except Exception:
            try:
                await message.bot.send_message(uid, text)
                sent += 1
            except Exception:
                failed += 1
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена</b>\n\n"
        f"📤 Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}\n"
        f"👥 Всего: {total}",
        parse_mode="HTML",
    )


# ============================================================
#                         РЕСТАРТ
# ============================================================
@router.callback_query(F.data == "adm:restart")
async def adm_restart(cb: CallbackQuery):
    if not is_admin(cb.from_user.id, cb.from_user.username):
        return await cb.answer("Нет доступа", show_alert=True)
    await cb.message.edit_text(
        "⚠️ <b>Перезапустить бота?</b>\n\n"
        "Все активные сессии будут прерваны.\n"
        "База данных не пострадает.",
        parse_mode="HTML",
        reply_markup=admin_restart_confirm_kb(),
    )
    await cb.answer()


@router.callback_query(F.data == "adm:restart_yes")
async def adm_restart_yes(cb: CallbackQuery):
    if not is_admin(cb.from_user.id, cb.from_user.username):
        return await cb.answer("Нет доступа", show_alert=True)
    await cb.message.edit_text("🔄 Перезапуск...")
    await cb.answer("Рестарт...")
    await asyncio.sleep(1)
    os.execv(sys.executable, [sys.executable] + sys.argv)


# ============================================================
#                       ПРОМОКОДЫ
# ============================================================
@router.callback_query(F.data == "adm:promos")
async def adm_promos(cb: CallbackQuery):
    if not is_admin(cb.from_user.id, cb.from_user.username):
        return await cb.answer("Нет доступа", show_alert=True)

    rows = await list_promos()
    if not rows:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать", callback_data="adm:newpromo")],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="adm:menu")],
        ])
        return await cb.message.edit_text("🎟 Промокодов пока нет.", reply_markup=kb)

    lines = ["🎟 <b>Промокоды</b>\n"]
    buttons = []
    for code, payload, disc, max_uses, used in rows:
        name = PLANS.get(payload, ("?",))[0]
        limit = "∞" if not max_uses else max_uses
        lines.append(f"<code>{code}</code> · {name} · -{disc}% · {used}/{limit}")
        buttons.append([InlineKeyboardButton(
            text=f"🗑 Удалить {code}", callback_data=f"adm:delpromo:{code}"
        )])
    buttons.append([InlineKeyboardButton(text="➕ Создать", callback_data="adm:newpromo")])
    buttons.append([InlineKeyboardButton(text="⬅ Назад", callback_data="adm:menu")])

    await cb.message.edit_text(
        "\n".join(lines), parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("adm:delpromo:"))
async def adm_del_promo(cb: CallbackQuery):
    if not is_admin(cb.from_user.id, cb.from_user.username):
        return await cb.answer("Нет доступа", show_alert=True)
    code = cb.data.split(":", 2)[2]
    await delete_promo(code)
    await cb.answer(f"Удалён {code}")
    await adm_promos(cb)


@router.callback_query(F.data == "adm:newpromo")
async def adm_newpromo(cb: CallbackQuery):
    if not is_admin(cb.from_user.id, cb.from_user.username):
        return await cb.answer("Нет доступа", show_alert=True)
    promo_draft[cb.from_user.id] = {"step": "plan"}
    await cb.message.edit_text(
        "🎟 Выбери подписку для промокода:",
        reply_markup=newpromo_plans_kb(),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("np:plan:"))
async def np_plan(cb: CallbackQuery):
    if not is_admin(cb.from_user.id, cb.from_user.username):
        return await cb.answer("Нет доступа", show_alert=True)
    payload = cb.data.split(":", 2)[2]
    draft = promo_draft.setdefault(cb.from_user.id, {})
    draft["payload"] = payload
    draft["step"] = "discount"
    await cb.message.edit_text("Введи размер скидки в % (1–100):")
    await cb.answer()


@router.callback_query(F.data.startswith("np:uses:"))
async def np_uses(cb: CallbackQuery):
    if not is_admin(cb.from_user.id, cb.from_user.username):
        return await cb.answer("Нет доступа", show_alert=True)
    uses = int(cb.data.split(":")[2])
    draft = promo_draft.setdefault(cb.from_user.id, {})
    draft["max_uses"] = uses
    draft["step"] = "code"
    await cb.message.edit_text(
        "Отправь свой код или сгенерируй автоматически:",
        reply_markup=newpromo_generate_kb(),
    )
    await cb.answer()


@router.callback_query(F.data == "np:generate")
async def np_generate(cb: CallbackQuery):
    if not is_admin(cb.from_user.id, cb.from_user.username):
        return await cb.answer("Нет доступа", show_alert=True)

    draft = promo_draft.get(cb.from_user.id)
    if not draft or "payload" not in draft or "discount" not in draft:
        return await cb.answer("Черновик потерян, начни заново", show_alert=True)

    code = draft.get("code") or gen_code()
    max_uses = draft.get("max_uses", 0)
    await create_promo(code, draft["payload"], draft["discount"], max_uses)

    name = PLANS[draft["payload"]][0]
    discount = draft["discount"]
    promo_draft.pop(cb.from_user.id, None)

    await cb.message.edit_text(
        f"✅ Промокод создан:\n\n"
        f"<code>{code}</code>\n"
        f"Подписка: {name}\n"
        f"Скидка: {discount}%\n"
        f"Лимит: {'∞' if not max_uses else max_uses}",
        parse_mode="HTML",
        reply_markup=promo_created_kb(),
    )
    await cb.answer()


# ============================================================
#              ТЕКСТОВЫЙ FSM ДЛЯ АДМИНА
# ============================================================
@router.message(F.text & ~F.text.startswith("/"))
async def admin_text_step(message: Message):
    if message.chat.type != "private":
        raise SkipHandler()
    if not is_admin_msg(message):
        raise SkipHandler()

    admin_id = message.from_user.id
    text = message.text.strip()

    if broadcast_draft.get(admin_id):
        broadcast_draft.pop(admin_id, None)
        await run_broadcast(message)
        return

    gd = gift_draft.get(admin_id)
    if gd and gd.get("step") == "user_id":
        if not text.isdigit():
            return await message.answer("Отправь числовой ID пользователя.")
        user_id = int(text)
        u = await get_user(user_id)
        if not u:
            return await message.answer(
                f"❌ Пользователь <code>{user_id}</code> не найден в базе.\n"
                f"Попробуй другой ID или /cancel",
                parse_mode="HTML",
            )
        gd["user_id"] = user_id
        gd["step"] = "days"
        uname = f"@{u[1]}" if u[1] else (u[2] or "—")
        return await message.answer(
            f"👤 {uname} (<code>{user_id}</code>)\n\n"
            f"Выбери срок Pro:",
            parse_mode="HTML",
            reply_markup=gift_days_kb(user_id),
        )

    draft = promo_draft.get(admin_id)
    if not draft:
        raise SkipHandler()

    step = draft.get("step")

    if step == "discount":
        if not text.isdigit() or not (1 <= int(text) <= 100):
            return await message.answer("Введи число от 1 до 100.")
        draft["discount"] = int(text)
        draft["step"] = "uses"
        await message.answer(
            f"Скидка: {draft['discount']}%\n\n"
            "Введи лимит использований (0 = безлимит) или сгенерируй код:",
            reply_markup=newpromo_uses_kb(),
        )
        return

    if step == "uses":
        if not text.isdigit():
            return await message.answer("Введи число (0 = безлимит).")
        draft["max_uses"] = int(text)
        draft["step"] = "code"
        await message.answer(
            "Отправь свой код или сгенерируй:",
            reply_markup=newpromo_generate_kb(),
        )
        return

    if step == "code":
        code = text.upper()
        if not code.isalnum() or len(code) < 4:
            return await message.answer("Код от 4 символов, только буквы/цифры.")
        draft["code"] = code
        await message.answer(
            f"Код: <code>{code}</code>\nНажми «Сохранить».",
            parse_mode="HTML",
            reply_markup=newpromo_save_kb(),
        )
        return

    raise SkipHandler()
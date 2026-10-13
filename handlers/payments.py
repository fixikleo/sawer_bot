from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, PreCheckoutQuery, LabeledPrice,
)

from config import PLANS
from database import upsert_user, get_user, is_pro, grant_pro
from keyboards import buy_plans_kb

router = Router()


@router.message(Command("pro"))
async def cmd_pro(message: Message):
    u = message.from_user
    await upsert_user(u.id, u.username, u.first_name)

    if await is_pro(u.id):
        me = await get_user(u.id)
        return await message.answer(f"✅ У тебя уже активен Pro до {me[3][:19]}")

    await message.answer("Выбери тариф:", reply_markup=buy_plans_kb())


@router.callback_query(F.data.startswith("buy:"))
async def on_buy(cb: CallbackQuery):
    _, payload, disc_str = cb.data.split(":")
    plan = PLANS.get(payload)
    if not plan:
        return await cb.answer("Тариф не найден", show_alert=True)

    name, stars, _days = plan
    discount = int(disc_str)
    final = max(1, stars - stars * discount // 100)
    title = name + (f" (-{discount}%)" if discount else "")

    await cb.bot.send_invoice(
        chat_id=cb.from_user.id,
        title=title,
        description=f"Безлимитное сохранение. {name}.",
        payload=f"{payload}|{discount}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=title, amount=final)],
    )
    await cb.answer()


@router.pre_checkout_query()
async def on_pre_checkout(q: PreCheckoutQuery):
    base = q.invoice_payload.split("|")[0]
    if base not in PLANS:
        return await q.answer(ok=False, error_message="Тариф не найден")
    await q.answer(ok=True)


@router.message(F.successful_payment)
async def on_success(message: Message):
    raw = message.successful_payment.invoice_payload
    payload, _, _disc = raw.partition("|")
    plan = PLANS.get(payload)
    if not plan:
        return
    name, _stars, days = plan
    paid = message.successful_payment.total_amount

    await grant_pro(message.from_user.id, days, add_paid=paid)

    await message.answer(
        f"🎉 <b>Оплата получена!</b>\n\n"
        f"Тариф: «{name}»\n"
        f"Оплачено: {paid} ⭐\n"
        f"Активирован на {days} дней.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📖 <b>Что дальше?</b>\n\n"
        f"🔹 <b>Режим «в чате»</b> — добавь бота в группу и напиши <code>/bind</code>\n\n"
        f"🔹 <b>Режим «Секретарь»</b> — подключи бота к аккаунту:\n"
        f"   Настройки → Автоматизация чатов → выбери бота → дай право «Отвечать»\n\n"
        f"Полная инструкция: /help\n"
        f"Спасибо за поддержку!"
    )
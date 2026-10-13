from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from config import PLANS
from database import (
    upsert_user, get_promo, promo_used_by, mark_promo_used,
)
from keyboards import promo_buy_kb

router = Router()


@router.message(Command("promo"))
async def cmd_promo(message: Message):
    u = message.from_user
    await upsert_user(u.id, u.username, u.first_name)

    code = message.text.partition(" ")[2].strip().upper()
    if not code:
        return await message.answer("Использование: /promo КОД")

    promo = await get_promo(code)
    if not promo:
        return await message.answer("❌ Промокод не найден.")

    _, plan_payload, discount, max_uses, used, _ = promo
    if max_uses and used >= max_uses:
        return await message.answer("❌ Промокод исчерпан.")

    if await promo_used_by(code, u.id):
        return await message.answer("❌ Ты уже использовал этот промокод.")

    plan = PLANS.get(plan_payload)
    if not plan:
        return await message.answer("❌ Тариф промокода недоступен.")

    name, stars, _days = plan
    final = max(1, stars - stars * discount // 100)

    await mark_promo_used(code, u.id)

    await message.answer(
        f"🎟 Промокод принят!\n"
        f"Скидка {discount}% на «{name}».\n"
        f"Цена: {final} ⭐ (вместо {stars})",
        reply_markup=promo_buy_kb(plan_payload, discount),
    )
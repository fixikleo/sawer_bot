import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from database import init_db
from handlers import user, payments, promo, admin, business, help as help_handler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# admin — первым, чтобы его текстовый FSM не перехватил user.
# Внутри admin_text_step брошен SkipHandler, если сообщение не для него.
dp.include_router(admin.router)
dp.include_router(payments.router)
dp.include_router(promo.router)
dp.include_router(business.router)
dp.include_router(help_handler.router)
dp.include_router(user.router)


async def main():
    await init_db()

    # Сброс вебхука и старых накопившихся апдейтов — важно после смены
    # allowed_updates или если бот «залип» на старых сообщениях
    await bot.delete_webhook(drop_pending_updates=True)
    print("Очередь апдейтов очищена.")

    print("SaveKeeper запущен.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
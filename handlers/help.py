from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from keyboards import help_kb, main_menu_kb

router = Router()


HELP_TEXT = (
    "📖 <b>SaveKeeper — твой личный архив сообщений</b>\n\n"
    "Я сохраняю сообщения, даже если их удалят. "
    "Ты в любой момент сможешь посмотреть их через /history.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "✨ <b>Что я умею</b>\n\n"
    "👥 <b>Хранить переписку из групп</b>\n"
    "Добавь меня в группу и напиши там /bind — "
    "я начну сохранять все сообщения.\n\n"
    "💬 <b>Быть твоим секретарём</b>\n"
    "Подключи меня к аккаунту — и я буду сохранять личные переписки.\n"
    "Пошаговая инструкция — в разделе «Как подключить секретаря» ниже.\n\n"
    "🔍 <b>Искать по архиву</b> (Pro)\n"
    "Найду любое сообщение по слову.\n\n"
    "📄 <b>Экспортировать всё в файл</b> (Pro)\n"
    "Скачаешь всю историю одним .txt-файлом.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "💎 <b>Бесплатно и Pro</b>\n\n"
    "🆓 <b>Free</b> — 10 сохранённых сообщений\n"
    "⭐ <b>Pro</b> — безлимит, поиск, экспорт\n\n"
    "Купить Pro — /pro или кнопка ниже.\n"
    "Есть промокод? Введи /promo КОД.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "📌 <b>Все команды</b>\n"
    "/history — последние сообщения\n"
    "/search <i>текст</i> — поиск (Pro)\n"
    "/export — скачать историю (Pro)\n"
    "/pro — купить Pro\n"
    "/promo <i>КОД</i> — активировать промокод\n"
    "/ref — пригласить друзей и получить Pro бесплатно\n"
    "/stats — статистика\n"
    "/bind — привязать группу (пиши в группе)\n"
    "/unbind — отвязать группу (только владелец)\n"
    "/clear — очистить историю\n"
    "/help — эта справка"
)


# ============================================================
#         ПОДРОБНАЯ ИНСТРУКЦИЯ ПО ПОДКЛЮЧЕНИЮ СЕКРЕТАРЯ
# ============================================================

SECRETARY_TEXT = (
    "💬 <b>Как подключить бота-секретаря</b>\n\n"
    "Секретарь — это режим, в котором я читаю твои <b>личные переписки</b> "
    "и сохраняю все входящие сообщения. Даже если собеседник удалит "
    "сообщение у себя — оно останется в архиве.\n\n"

    "━━━━━━━━━━━━━━━━━━━━\n"
    "⚠️ <b>Что нужно для подключения</b>\n\n"

    "1️⃣ <b>Telegram Premium</b>\n"
    "Без него функция «Автоматизация чатов» недоступна. "
    "Оформить можно в настройках: <b>Настройки → Telegram Premium</b>.\n\n"

    "2️⃣ <b>Твой аккаунт</b>\n"
    "Подключить секретаря можно только к своему аккаунту — "
    "к чужому нельзя.\n\n"

    "━━━━━━━━━━━━━━━━━━━━\n"
    "📱 <b>Пошаговая инструкция</b>\n\n"

    "<b>Шаг 1.</b> Открой <b>Настройки</b> Telegram\n"
    "<i>(на телефоне — иконка ⚙️ в меню, на компьютере — слева сверху)</i>\n\n"

    "<b>Шаг 2.</b> Найди раздел <b>Telegram Business</b> "
    "или <b>Автоматизация чатов</b>\n\n"

    "<b>Шаг 3.</b> Нажми <b>Чат-боты</b> → <b>Добавить бота</b>\n\n"

    "<b>Шаг 4.</b> Введи username: <code>@Saver_mes_pro_bot</code>\n"
    "<i>(или найди меня через поиск)</i>\n\n"

    "<b>Шаг 5.</b> Подтверди добавление\n"
    "Telegram попросит дать боту права. Обязательно включи:\n"
    "   • ✅ <b>Отвечать на сообщения</b>\n"
    "   • ✅ <b>Читать сообщения</b>\n\n"

    "<b>Шаг 6.</b> Выбери, к каким чатам дать доступ:\n"
    "   • 🌐 <b>Все чаты</b> — бот будет читать все личные переписки\n"
    "   • 👤 <b>Только выбранные</b> — укажешь вручную\n"
    "   • 🆕 <b>Только новые</b> — чаты, которые появятся после подключения\n\n"

    "<b>Шаг 7.</b> Готово! 🎉\n"
    "Я пришлю уведомление «✅ Секретарь подключён» и начну сохранять "
    "входящие сообщения.\n\n"

    "━━━━━━━━━━━━━━━━━━━━\n"
    "🔎 <b>Как проверить, что работает</b>\n\n"
    "1. Попроси друга написать тебе в личку\n"
    "2. Открой меня в личке и нажми /history\n"
    "3. Сообщение друга появится в архиве с пометкой 💬\n\n"

    "━━━━━━━━━━━━━━━━━━━━\n"
    "⚠️ <b>Важные ограничения</b>\n\n"

    "• Бот видит только <b>входящие</b> сообщения — твои ответы "
    "он не сохраняет\n\n"

    "• Telegram разрешает боту отвечать от твоего имени только в тех "
    "чатах, где была активность за <b>последние 24 часа</b>\n\n"

    "• Если ты отключишь секретаря в настройках, "
    "сохранение новых сообщений прекратится, но архив останется\n\n"

    "• Секретарь работает только в <b>личных чатах</b>. "
    "Для групп используй /bind\n\n"

    "━━━━━━━━━━━━━━━━━━━━\n"
    "💡 <b>Как отключить секретаря</b>\n\n"
    "Настройки → Telegram Business → Чат-боты → "
    "выбери меня → <b>Удалить</b>"
)


def secretary_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Купить Pro", callback_data="menu:pro")],
        [InlineKeyboardButton(text="⬅ К помощи", callback_data="menu:help")],
        [InlineKeyboardButton(text="🏠 В меню", callback_data="menu:back")],
    ])


def help_with_secretary_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Как подключить секретаря?", callback_data="menu:secretary")],
        [InlineKeyboardButton(text="⭐ Купить Pro", callback_data="menu:pro")],
        [InlineKeyboardButton(text="⬅ В меню", callback_data="menu:back")],
    ])


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        HELP_TEXT,
        parse_mode="HTML",
        reply_markup=help_with_secretary_kb(),
    )


@router.callback_query(F.data == "menu:help")
async def cb_help(cb: CallbackQuery):
    try:
        await cb.message.edit_text(
            HELP_TEXT,
            parse_mode="HTML",
            reply_markup=help_with_secretary_kb(),
        )
    except Exception:
        await cb.message.answer(
            HELP_TEXT,
            parse_mode="HTML",
            reply_markup=help_with_secretary_kb(),
        )
    await cb.answer()


@router.callback_query(F.data == "menu:secretary")
async def cb_secretary(cb: CallbackQuery):
    try:
        await cb.message.edit_text(
            SECRETARY_TEXT,
            parse_mode="HTML",
            reply_markup=secretary_kb(),
        )
    except Exception:
        await cb.message.answer(
            SECRETARY_TEXT,
            parse_mode="HTML",
            reply_markup=secretary_kb(),
        )
    await cb.answer()


@router.callback_query(F.data == "menu:back")
async def cb_back(cb: CallbackQuery):
    text = (
        "👋 <b>Главное меню</b>\n\n"
        "Выбери, что тебя интересует:"
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu_kb())
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb())
    await cb.answer()
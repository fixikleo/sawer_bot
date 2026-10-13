from aiogram import Router, F
from aiogram.types import Message, BusinessConnection, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
import os

from config import FREE_LIMIT
from database import (
    is_pro, count_saved, save_business_message,
    link_business_owner, get_business_owner, upsert_user,
)

router = Router()

MEDIA_DIR = "media"
os.makedirs(MEDIA_DIR, exist_ok=True)


def secretary_welcome_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 История", callback_data="menu:history")],
        [InlineKeyboardButton(text="📎 Медиа", callback_data="menu:media")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="menu:stats")],
        [InlineKeyboardButton(text="📖 Помощь", callback_data="menu:help")],
    ])


async def _save_business_media(message: Message, kind: str, file_id: str, ext: str) -> bool:
    if not message.business_connection_id:
        return False

    owner_id = await get_business_owner(message.business_connection_id)
    if not owner_id:
        return False

    if not await is_pro(owner_id):
        saved = await count_saved(owner_id)
        if saved >= FREE_LIMIT:
            return False

    try:
        file = await message.bot.get_file(file_id)
        fname = f"{owner_id}_{message.message_id}{ext}"
        fpath = os.path.join(MEDIA_DIR, fname)
        await message.bot.download_file(file.file_path, fpath)
    except Exception as e:
        print(f"[business-media] ошибка скачивания: {e}", flush=True)
        return False

    sender = message.from_user
    author_name = (
        f"@{sender.username}" if sender and sender.username
        else (sender.first_name if sender else "Клиент")
    )

    await save_business_message(
        owner_id=owner_id,
        chat_id=message.chat.id,
        message_id=message.message_id,
        text=f"[{kind}:{fpath}]",
        author_id=sender.id if sender else None,
        author_name=author_name,
    )
    return True


# ============================================================
#                  ПОДКЛЮЧЕНИЕ СЕКРЕТАРЯ
# ============================================================
@router.business_connection()
async def on_business_connection(connection: BusinessConnection):
    await upsert_user(
        connection.user.id,
        connection.user.username,
        connection.user.first_name,
    )
    await link_business_owner(connection.id, connection.user.id)
    try:
        await connection.bot.send_message(
            connection.user.id,
            "✅ <b>Секретарь подключён!</b>\n\n"
            "Теперь я сохраняю входящие сообщения (включая одноразовые фото/видео).\n\n"
            "Нажми кнопку ниже, чтобы открыть меню.",
            parse_mode="HTML",
            reply_markup=secretary_welcome_kb(),
        )
    except Exception:
        pass


# ============================================================
#                    СОХРАНЕНИЕ СООБЩЕНИЙ
# ============================================================
@router.business_message(F.text)
async def on_business_text(message: Message):
    if not message.business_connection_id:
        return

    owner_id = await get_business_owner(message.business_connection_id)
    if not owner_id:
        return

    if not await is_pro(owner_id):
        saved = await count_saved(owner_id)
        if saved >= FREE_LIMIT:
            return

    sender = message.from_user
    author_name = (
        f"@{sender.username}" if sender and sender.username
        else (sender.first_name if sender else "Клиент")
    )

    await save_business_message(
        owner_id=owner_id,
        chat_id=message.chat.id,
        message_id=message.message_id,
        text=message.text or "",
        author_id=sender.id if sender else None,
        author_name=author_name,
    )


@router.business_message(F.voice)
async def on_business_voice(message: Message):
    await _save_business_media(message, "voice", message.voice.file_id, ".ogg")


@router.business_message(F.video_note)
async def on_business_video_note(message: Message):
    await _save_business_media(message, "video_note", message.video_note.file_id, ".mp4")


@router.business_message(F.photo)
async def on_business_photo(message: Message):
    largest = message.photo[-1]
    await _save_business_media(message, "photo", largest.file_id, ".jpg")


@router.business_message(F.video)
async def on_business_video(message: Message):
    ext = ".mp4"
    if message.video.file_name and "." in message.video.file_name:
        ext = "." + message.video.file_name.rsplit(".", 1)[1]
    await _save_business_media(message, "video", message.video.file_id, ext)


@router.business_message(F.document)
async def on_business_document(message: Message):
    ext = ".bin"
    if message.document.file_name and "." in message.document.file_name:
        ext = "." + message.document.file_name.rsplit(".", 1)[1]
    await _save_business_media(message, "document", message.document.file_id, ext)


@router.business_message(F.sticker)
async def on_business_sticker(message: Message):
    ext = ".webp" if not message.sticker.is_video else ".webm"
    await _save_business_media(message, "sticker", message.sticker.file_id, ext)


@router.business_message(F.audio)
async def on_business_audio(message: Message):
    ext = ".mp3"
    if message.audio.file_name and "." in message.audio.file_name:
        ext = "." + message.audio.file_name.rsplit(".", 1)[1]
    await _save_business_media(message, "audio", message.audio.file_id, ext)


# ============================================================
#                       /start
# ============================================================
@router.message(Command("start"))
async def cmd_start(message: Message):
    u = message.from_user
    if not u:
        return
    await upsert_user(u.id, u.username, u.first_name)

    await message.answer(
        "👋 Привет! Я твой секретарь.\n\n"
        "Я сохраняю сообщения из твоих личных чатов, включая одноразовые фото и видео.\n\n"
        "Команды:\n"
        "/history — последние сообщения\n"
        "/media — последние медиа (Pro)\n"
        "/help — справка",
        reply_markup=secretary_welcome_kb(),
    )
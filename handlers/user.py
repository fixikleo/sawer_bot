import os
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile, FSInputFile
from aiogram.enums import ChatType

from config import FREE_LIMIT, REF_BONUS_DAYS, DB_PATH
from database import (
    upsert_user, get_user, is_pro, count_saved, save_message,
    get_history, get_recent_media, get_all_messages, search_messages, clear_history,
    set_referrer, inc_ref_bonus, grant_pro, count_refs,
    link_chat, get_chat_owner, unlink_chat,
)
from keyboards import main_menu_kb

router = Router()

MEDIA_DIR = "media"
os.makedirs(MEDIA_DIR, exist_ok=True)

MAIN_MENU_TEXT = (
    "👋 <b>SaveKeeper — твой личный архив сообщений</b>\n\n"
    "Я сохраняю сообщения, даже если их удалят.\n\n"
    "Выбери действие:"
)

MEDIA_LABELS = {
    "voice": "🎤 Голосовое",
    "video_note": "📹 Кружок",
    "photo": "🖼 Фото",
    "video": "🎬 Видео",
    "document": "📎 Документ",
    "sticker": "🎨 Стикер",
    "audio": "🎵 Аудио",
}


# ============================================================
#                   ОПРЕДЕЛЕНИЕ ВЛАДЕЛЬЦА
# ============================================================
async def _detect_owner(message: Message) -> int | None:
    """Для входящих сообщений: чей это будет архив."""
    if message.chat.type != ChatType.PRIVATE:
        return await get_chat_owner(message.chat.id)
    if message.sender_chat:
        return message.sender_chat.id
    if message.from_user:
        return message.from_user.id
    return None


def _detect_author(message: Message) -> tuple[int | None, str]:
    if message.sender_chat:
        return message.sender_chat.id, message.sender_chat.title or "Channel"
    if message.from_user:
        name = (
            f"@{message.from_user.username}" if message.from_user.username
            else message.from_user.first_name
        )
        return message.from_user.id, name
    return None, "Unknown"


async def _resolve_owner_for_command(message: Message) -> int | None:
    """Для команд: в группе — владелец чата, в личке — отправитель."""
    if message.chat.type == ChatType.PRIVATE:
        if message.sender_chat:
            return message.sender_chat.id
        if message.from_user:
            return message.from_user.id
        return None
    return await get_chat_owner(message.chat.id)


# ============================================================
#                   СОХРАНЕНИЕ МЕДИА
# ============================================================
async def save_media(message: Message, kind: str, file_id: str, ext: str) -> bool:
    owner_id = await _detect_owner(message)
    if not owner_id:
        return False

    if not await is_pro(owner_id):
        saved = await count_saved(owner_id)
        if saved >= FREE_LIMIT:
            if message.chat.type == ChatType.PRIVATE:
                await message.answer(
                    f"⚠️ Бесплатный лимит ({FREE_LIMIT}) исчерпан.\nКупи Pro: /pro"
                )
            return False

    try:
        file = await message.bot.get_file(file_id)
        fname = f"{owner_id}_{message.message_id}{ext}"
        fpath = os.path.join(MEDIA_DIR, fname)
        await message.bot.download_file(file.file_path, fpath)
    except Exception as e:
        print(f"[media] ошибка скачивания: {e}", flush=True)
        return False

    author_id, author_name = _detect_author(message)

    await save_message(
        owner_id=owner_id,
        message_id=message.message_id,
        text=f"[{kind}:{fpath}]",
        source_chat_id=message.chat.id if message.chat.type != ChatType.PRIVATE else None,
        source_type="group" if message.chat.type != ChatType.PRIVATE else "private",
        author_id=author_id,
        author_name=author_name,
    )
    return True


def _media_label(text: str) -> str | None:
    if not text:
        return None
    if text.startswith("[") and ":" in text and text.endswith("]"):
        inner = text[1:-1]
        kind, _, _ = inner.partition(":")
        return MEDIA_LABELS.get(kind, f"📎 {kind}")
    return None


def _extract_path(text: str) -> str | None:
    if not text:
        return None
    if text.startswith("[") and ":" in text and text.endswith("]"):
        inner = text[1:-1]
        _, _, path = inner.partition(":")
        return path
    return None


# ============================================================
#                УНИВЕРСАЛЬНЫЕ ОТПРАВЛЯЛКИ
# ============================================================
async def _send_history(target: Message, user_id: int):
    limit = 50 if await is_pro(user_id) else 10
    rows = await get_history(user_id, limit)

    if not rows:
        return await target.answer("История пуста.")

    lines = []
    for text, date, author, src in reversed(rows):
        prefix = {"business": "💬", "group": "👥"}.get(src, "🔒")
        who = f" | {author}" if author else ""

        label = _media_label(text)
        if label:
            body = f"{label}\n<i>(посмотреть: /media)</i>"
        else:
            body = text or ""

        lines.append(f"[{date[:16]}]{who} {prefix}\n{body}")

    result = "\n\n".join(lines)
    for i in range(0, len(result), 4000):
        await target.answer(result[i:i + 4000], parse_mode="HTML")


async def _send_media(target: Message, user_id: int):
    if not await is_pro(user_id):
        return await target.answer(
            "🔒 <b>Просмотр медиа</b> — только для Pro.\n\n"
            "С Pro можно смотреть сохранённые голосовые, кружки, фото и видео.\n\n"
            "Купить: /pro",
            parse_mode="HTML",
        )

    rows = await get_recent_media(user_id, limit=10)
    if not rows:
        return await target.answer("Сохранённых медиа пока нет.")

    await target.answer(f"📎 <b>Последние {len(rows)} медиа:</b>", parse_mode="HTML")

    for text, date, author, src in reversed(rows):
        path = _extract_path(text)
        if not path or not os.path.exists(path):
            await target.answer(
                f"⚠️ Файл не найден: <code>{path}</code>", parse_mode="HTML"
            )
            continue

        prefix = {"business": "💬", "group": "👥"}.get(src, "🔒")
        who = f" | {author}" if author else ""
        caption = f"[{date[:16]}]{who} {prefix}"
        if len(caption) > 1000:
            caption = caption[:1000]

        try:
            f = FSInputFile(path)
            if text.startswith("[voice:"):
                await target.answer_voice(f, caption=caption)
            elif text.startswith("[video_note:"):
                await target.answer_video_note(f)
            elif text.startswith("[photo:"):
                await target.answer_photo(f, caption=caption)
            elif text.startswith("[video:"):
                await target.answer_video(f, caption=caption)
            elif text.startswith("[audio:"):
                await target.answer_audio(f, caption=caption)
            elif text.startswith("[sticker:"):
                await target.answer_sticker(f)
            else:
                await target.answer_document(f, caption=caption)
        except Exception as e:
            print(f"[media] ошибка отправки {path}: {e}", flush=True)
            await target.answer(
                f"⚠️ Не удалось отправить: <code>{os.path.basename(path)}</code>",
                parse_mode="HTML",
            )


async def _send_export(target: Message, user_id: int):
    if not await is_pro(user_id):
        return await target.answer(
            "🔒 <b>Экспорт истории</b> — только для Pro.\n\n"
            "С Pro ты можешь скачать всю свою историю одним .txt-файлом.\n\n"
            "Купить: /pro",
            parse_mode="HTML",
        )

    rows = await get_all_messages(user_id)
    if not rows:
        return await target.answer("История пуста — нечего экспортировать.")

    lines = [
        "SaveKeeper — экспорт истории",
        f"User ID: {user_id}",
        f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Всего сообщений: {len(rows)}",
        "=" * 60,
        "",
    ]
    for text, date, author, src in rows:
        prefix = {
            "business": "[Личка]",
            "group": "[Группа]",
            "private": "[Бот]",
        }.get(src, "[?]")
        author_str = f" {author}" if author else ""

        label = _media_label(text)
        if label:
            body = f"{label} — {text.strip('[]').partition(':')[2]}"
        else:
            body = text or ""

        lines.append(f"[{date}]{prefix}{author_str}")
        lines.append(body)
        lines.append("")

    content = "\n".join(lines)
    data = content.encode("utf-8")

    if len(data) > 45 * 1024 * 1024:
        cut = content[:40 * 1024 * 1024]
        content = cut + "\n\n[... файл обрезан из-за размера ...]"
        data = content.encode("utf-8")

    file = BufferedInputFile(
        data,
        filename=f"savekeeper_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
    )
    await target.answer_document(
        file,
        caption=f"📄 Экспорт истории: {len(rows)} сообщений",
    )


async def _send_stats(target: Message, user_id: int):
    saved = await count_saved(user_id)
    pro = await is_pro(user_id)
    u = await get_user(user_id)
    until = u[3][:19] if u and u[3] else "—"
    paid = u[4] if u else 0
    invited = await count_refs(user_id)

    await target.answer(
        f"📊 <b>Твоя статистика</b>\n\n"
        f"💬 Сохранено: {saved}\n"
        f"⭐ Статус: {'<b>Pro</b>' if pro else 'Free'}\n"
        f"⏳ Pro до: {until}\n"
        f"💰 Оплачено: {paid} ⭐\n"
        f"👥 Приглашено: {invited}",
        parse_mode="HTML",
    )


async def _send_ref(target: Message, user_id: int, bot):
    bot_username = (await bot.get_me()).username
    link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    invited = await count_refs(user_id)
    u = await get_user(user_id)
    bonus = u[6] if u else 0

    await target.answer(
        f"👥 <b>Приглашай друзей — получай Pro бесплатно</b>\n\n"
        f"Твоя ссылка:\n<code>{link}</code>\n\n"
        f"🎁 За каждого друга — <b>+{REF_BONUS_DAYS} дня Pro</b>\n\n"
        f"📊 Уже приглашено: {invited}\n"
        f"🎁 Бонусных дней получено: {bonus * REF_BONUS_DAYS}",
        parse_mode="HTML",
    )


async def _send_pro(target: Message, user_id: int, username: str | None, first_name: str | None):
    await upsert_user(user_id, username, first_name)

    if await is_pro(user_id):
        me = await get_user(user_id)
        return await target.answer(
            f"✅ У тебя уже активен <b>Pro</b> до {me[3][:19]}\n\n"
            f"Что входит:\n"
            f"• безлимит сообщений\n"
            f"• поиск /search\n"
            f"• экспорт /export\n"
            f"• медиа /media",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )

    from keyboards import buy_plans_kb
    await target.answer(
        "⭐ <b>Pro-подписка</b>\n\n"
        "Что даёт:\n"
        "• ♾ Безлимитное сохранение сообщений\n"
        "• 🔍 Поиск по всей истории\n"
        "• 📄 Экспорт истории в .txt\n"
        "• 📎 Просмотр сохранённых медиа\n\n"
        "Выбери тариф:",
        parse_mode="HTML",
        reply_markup=buy_plans_kb(),
    )


# ============================================================
#                       /start
# ============================================================
@router.message(Command("start"))
async def cmd_start(message: Message):
    u = message.from_user
    if not u:
        return

    await upsert_user(u.id, u.username, u.first_name)

    parts = message.text.split(maxsplit=1)
    if len(parts) == 2 and parts[1].startswith("ref_"):
        try:
            referrer_id = int(parts[1][4:])
        except ValueError:
            referrer_id = None

        if referrer_id and referrer_id != u.id:
            me = await get_user(u.id)
            if me and me[5] is None:
                await set_referrer(u.id, referrer_id)
                await grant_pro(referrer_id, REF_BONUS_DAYS)
                await inc_ref_bonus(referrer_id)
                try:
                    await message.bot.send_message(
                        referrer_id,
                        f"🎉 По твоей ссылке пришёл новый пользователь!\n"
                        f"+{REF_BONUS_DAYS} дней Pro начислено.",
                    )
                except Exception:
                    pass

    await message.answer(MAIN_MENU_TEXT, reply_markup=main_menu_kb())


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    await message.answer(MAIN_MENU_TEXT, reply_markup=main_menu_kb())


@router.callback_query(F.data == "menu:main")
async def cb_main(cb: CallbackQuery):
    try:
        await cb.message.edit_text(MAIN_MENU_TEXT, reply_markup=main_menu_kb())
    except Exception:
        await cb.message.answer(MAIN_MENU_TEXT, reply_markup=main_menu_kb())
    await cb.answer()


# ============================================================
#                CALLBACK МЕНЮ (работают от твоего имени)
# ============================================================
@router.callback_query(F.data == "menu:history")
async def cb_history(cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id
    await _send_history(cb.message, user_id)


@router.callback_query(F.data == "menu:media")
async def cb_media(cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id
    await _send_media(cb.message, user_id)


@router.callback_query(F.data == "menu:stats")
async def cb_stats(cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id
    await _send_stats(cb.message, user_id)


@router.callback_query(F.data == "menu:pro")
async def cb_pro(cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id
    await _send_pro(
        cb.message,
        user_id,
        cb.from_user.username,
        cb.from_user.first_name,
    )


@router.callback_query(F.data == "menu:promo")
async def cb_promo(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "🎟 <b>Активация промокода</b>\n\n"
        "Напиши: <code>/promo ТВОЙКОД</code>\n\n"
        "Например: <code>/promo SALE50</code>",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "menu:ref")
async def cb_ref(cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id
    await _send_ref(cb.message, user_id, cb.bot)


@router.callback_query(F.data == "menu:export")
async def cb_export(cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id
    await _send_export(cb.message, user_id)


# ============================================================
#                       КОМАНДЫ
# ============================================================
@router.message(Command("pro"))
async def cmd_pro(message: Message):
    u = message.from_user
    if not u:
        return
    await _send_pro(message, u.id, u.username, u.first_name)


@router.message(Command("history"))
async def cmd_history(message: Message):
    user_id = await _resolve_owner_for_command(message)
    if not user_id:
        if message.chat.type != ChatType.PRIVATE:
            return await message.answer(
                "⚠️ Чат не привязан. Напиши /bind, чтобы начать сохранять сообщения."
            )
        return
    await _send_history(message, user_id)


@router.message(Command("media"))
async def cmd_media(message: Message):
    user_id = await _resolve_owner_for_command(message)
    if not user_id:
        if message.chat.type != ChatType.PRIVATE:
            return await message.answer("⚠️ Чат не привязан. Напиши /bind.")
        return
    await _send_media(message, user_id)


@router.message(Command("export"))
async def cmd_export(message: Message):
    user_id = await _resolve_owner_for_command(message)
    if not user_id:
        if message.chat.type != ChatType.PRIVATE:
            return await message.answer("⚠️ Чат не привязан. Напиши /bind.")
        return
    await _send_export(message, user_id)


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    user_id = await _resolve_owner_for_command(message)
    if not user_id:
        if message.chat.type != ChatType.PRIVATE:
            return await message.answer("⚠️ Чат не привязан. Напиши /bind.")
        return
    await _send_stats(message, user_id)


@router.message(Command("ref"))
async def cmd_ref(message: Message):
    me = message.from_user
    if not me:
        return await message.answer("Команда доступна только от пользователя.")
    await _send_ref(message, me.id, message.bot)


# ============================================================
#                       /bind и /unbind
# ============================================================
@router.message(Command("bind"))
async def cmd_bind(message: Message):
    if message.chat.type == ChatType.PRIVATE:
        return await message.answer(
            "Эту команду нужно писать в группе или канале.\nСправка: /help"
        )

    if message.sender_chat:
        binder_id = message.sender_chat.id
        binder_name = message.sender_chat.title or "Channel"
    elif message.from_user:
        binder_id = message.from_user.id
        binder_name = (
            f"@{message.from_user.username}" if message.from_user.username
            else message.from_user.first_name
        )
    else:
        return await message.answer("Не удалось определить отправителя.")

    existing = await get_chat_owner(message.chat.id)
    if existing:
        if existing == binder_id:
            return await message.answer("✅ Чат уже привязан к тебе.")
        return await message.answer(
            "⚠️ Чат уже привязан к другому владельцу.\n"
            "Отвязать может только он командой /unbind."
        )

    await upsert_user(
        binder_id,
        message.from_user.username if message.from_user else None,
        binder_name,
    )
    await link_chat(message.chat.id, binder_id, message.chat.title or "Чат")

    print(f"[BIND] chat={message.chat.id} owner={binder_id} ({binder_name})", flush=True)

    await message.answer(
        f"✅ Чат «{message.chat.title or 'Чат'}» привязан.\n"
        f"Владелец: {binder_name}\n\n"
        f"Теперь я сохраняю все сообщения из этого чата.\n"
        f"Проверить историю: /history"
    )


@router.message(Command("unbind"))
async def cmd_unbind(message: Message):
    if message.chat.type == ChatType.PRIVATE:
        return await message.answer(
            "Эту команду нужно писать в группе или канале.\nСправка: /help"
        )

    existing = await get_chat_owner(message.chat.id)
    if not existing:
        return await message.answer("Чат не привязан.")

    is_owner = False
    if message.sender_chat and message.sender_chat.id == existing:
        is_owner = True
    elif message.from_user and message.from_user.id == existing:
        is_owner = True

    if not is_owner:
        return await message.answer(
            "⛔ Отвязать чат может только владелец (тот, кто делал /bind)."
        )

    await unlink_chat(message.chat.id)
    await message.answer("🗑 Чат отвязан. Сообщения больше не сохраняются.")


# ============================================================
#                          /search
# ============================================================
@router.message(Command("search"))
async def cmd_search(message: Message):
    user_id = await _resolve_owner_for_command(message)
    if not user_id:
        if message.chat.type != ChatType.PRIVATE:
            return await message.answer("⚠️ Чат не привязан. Напиши /bind.")
        return

    if not await is_pro(user_id):
        return await message.answer(
            "🔒 <b>Поиск</b> — только для Pro.\n\n"
            "С Pro можно найти любое сообщение по слову.\n\n"
            "Купить: /pro",
            parse_mode="HTML",
        )

    q = message.text.partition(" ")[2].strip()
    if not q:
        return await message.answer("Использование: /search <текст>")

    rows = await search_messages(user_id, q)
    if not rows:
        return await message.answer("Ничего не найдено.")

    lines = []
    for text, date, author, src in rows:
        prefix = {"business": "💬", "group": "👥"}.get(src, "🔒")
        who = f" | {author}" if author else ""

        label = _media_label(text)
        body = label if label else (text or "")

        lines.append(f"[{date[:16]}]{who} {prefix}\n{body}")

    result = "\n\n".join(lines)
    for i in range(0, len(result), 4000):
        await message.answer(result[i:i + 4000], parse_mode="HTML")


# ============================================================
#                          /clear
# ============================================================
@router.message(Command("clear"))
async def cmd_clear(message: Message):
    user_id = await _resolve_owner_for_command(message)
    if not user_id:
        if message.chat.type != ChatType.PRIVATE:
            return await message.answer("⚠️ Чат не привязан. Напиши /bind.")
        return

    await clear_history(user_id)
    await message.answer("🗑 История очищена (включая медиа-файлы).")


# ============================================================
#              ОСНОВНОЙ ХЕНДЛЕР
# ============================================================
@router.message()
async def on_any_message(message: Message):
    print(
        f"[MSG] chat={message.chat.id} type={message.chat.type} "
        f"from={message.from_user.id if message.from_user else None} "
        f"text={message.text!r} "
        f"voice={bool(message.voice)} video_note={bool(message.video_note)} "
        f"photo={bool(message.photo)} video={bool(message.video)}",
        flush=True,
    )

    if message.text and message.text.startswith("/"):
        return

    if message.voice:
        await save_media(message, "voice", message.voice.file_id, ".ogg")
        return

    if message.video_note:
        await save_media(message, "video_note", message.video_note.file_id, ".mp4")
        return

    if message.photo:
        largest = message.photo[-1]
        await save_media(message, "photo", largest.file_id, ".jpg")
        return

    if message.video:
        ext = ".mp4"
        if message.video.file_name and "." in message.video.file_name:
            ext = "." + message.video.file_name.rsplit(".", 1)[1]
        await save_media(message, "video", message.video.file_id, ext)
        return

    if message.document:
        ext = ".bin"
        if message.document.file_name and "." in message.document.file_name:
            ext = "." + message.document.file_name.rsplit(".", 1)[1]
        await save_media(message, "document", message.document.file_id, ext)
        return

    if message.sticker:
        ext = ".webp" if not message.sticker.is_video else ".webm"
        await save_media(message, "sticker", message.sticker.file_id, ext)
        return

    if message.audio:
        ext = ".mp3"
        if message.audio.file_name and "." in message.audio.file_name:
            ext = "." + message.audio.file_name.rsplit(".", 1)[1]
        await save_media(message, "audio", message.audio.file_id, ext)
        return

    text = message.text or message.caption
    if not text:
        return

    # === ГРУППА / КАНАЛ ===
    if message.chat.type != ChatType.PRIVATE:
        owner_id = await get_chat_owner(message.chat.id)
        if not owner_id:
            return

        author_id, author_name = _detect_author(message)

        if not await is_pro(owner_id):
            saved = await count_saved(owner_id)
            if saved >= FREE_LIMIT:
                return

        await save_message(
            owner_id=owner_id,
            message_id=message.message_id,
            text=text,
            source_chat_id=message.chat.id,
            source_type="group",
            author_id=author_id,
            author_name=author_name,
        )
        return

    # === ЛИЧКА С БОТОМ ===
    u = message.from_user
    if not u:
        return

    await upsert_user(u.id, u.username, u.first_name)

    if not await is_pro(u.id):
        saved = await count_saved(u.id)
        if saved >= FREE_LIMIT:
            return await message.answer(
                f"⚠️ Бесплатный лимит ({FREE_LIMIT}) исчерпан.\nКупи Pro: /pro"
            )

    await save_message(
        owner_id=u.id,
        message_id=message.message_id,
        text=text,
        source_type="private",
        author_id=u.id,
        author_name=f"@{u.username}" if u.username else u.first_name,
    )
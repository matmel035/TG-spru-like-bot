"""Telegram-обёртка (aiogram 3).

Умеет работать в трёх режимах:
  1. Личный чат        — отвечает на всё.
  2. Группа / супергруппа — отвечает, только когда его позвали:
     @mention, реплай на его сообщение, или обращение по «слову-триггеру»
     (настраивается через CALL_WORDS).
  3. Тема (forum)      — то же, что группа, но с топиком в ключе истории.

История ведётся по ключу (chat_id, thread_id, user_id) — в группе каждый
собеседник получает свой диалог, а общий тред не смешивается с личным.
"""
from __future__ import annotations

import asyncio
import logging
import re
import zlib

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

import config
from agent import core, memory

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("mybot")

CALL_WORDS = [w.strip().lower() for w in config.CALL_WORDS.split(",") if w.strip()]


def allowed(user_id: int) -> bool:
    return not config.ALLOWED_USER_IDS or user_id in config.ALLOWED_USER_IDS


def is_group(message: Message) -> bool:
    return message.chat.type in ("group", "supergroup")


def thread_id(message: Message) -> int:
    return message.message_thread_id or 0


def history_key(message: Message) -> int:
    """Ключ истории: личка — её id, группа — crc32 от (чат, топик, юзер).

    Отрицательное число, чтобы не пересекаться с настоящими id чатов.
    """
    if is_group(message):
        raw = f"{message.chat.id}:{thread_id(message)}:{message.from_user.id}"
        return -(zlib.crc32(raw.encode()))
    return message.chat.id


def strip_call_word(text: str, bot_username: str) -> str:
    """Убираем @username и слово-триггер из начала сообщения."""
    out = text
    out = re.sub(rf"@{re.escape(bot_username)}\b[,:!\-—]?\s*", "", out, flags=re.IGNORECASE)
    lowered = out.lstrip().lower()
    for w in CALL_WORDS:
        if lowered.startswith(w):
            rest = out.lstrip()[len(w):]
            return rest.lstrip(" ,:!-—")
    return out.strip()


def addressed(message: Message, bot_username: str) -> tuple[bool, str]:
    """Агент звали? Возвращает (да/нет, текст задачи)."""
    text = message.text or ""

    # 1. Реплай на сообщение бота
    if message.reply_to_message and message.reply_to_message.from_user:
        if message.reply_to_message.from_user.id == message.bot.id:
            return True, text.strip()

    # 2. Упоминание @username
    if re.search(rf"@{re.escape(bot_username)}\b", text, flags=re.IGNORECASE):
        return True, strip_call_word(text, bot_username)

    # 3. Обращение по слову-триггеру в начале ("бот, найди кофейни")
    stripped = text.lstrip().lower()
    for w in CALL_WORDS:
        if stripped.startswith(w):
            return True, strip_call_word(text, bot_username)

    return False, text.strip()


async def main() -> None:
    memory.init_db()
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()
    username = (await bot.get_me()).username or ""

    @dp.message(Command("start", "help"))
    async def cmd_start(message: Message) -> None:
        await message.answer(
            "Привет! Я твой локальный агент.\n"
            "Личный чат: просто пиши задачу.\n"
            f"Группа: позови меня по @{username} или ответь на моё сообщение.\n"
            "Команды: /notes — мои заметки, /reset — забыть диалог."
        )

    @dp.message(Command("reset"))
    async def cmd_reset(message: Message) -> None:
        memory.clear_history(history_key(message))
        await message.answer("История диалога очищена.")

    @dp.message(Command("notes"))
    async def cmd_notes(message: Message) -> None:
        if is_group(message):
            await message.answer("Заметки — только в личном чате.")
            return
        notes = memory.list_notes(30, owner=str(message.from_user.id))
        if not notes:
            await message.answer("Заметок пока нет.")
            return
        await message.answer("\n".join(f"- [{n['tag']}] {n['text']}" for n in notes))

    @dp.message(F.text)
    async def on_text(message: Message) -> None:
        if not allowed(message.from_user.id):
            return

        if is_group(message):
            called, task = addressed(message, username)
            if not called:
                return  # в группе молчим, пока не позвали
        else:
            task = (message.text or "").strip()

        if not task:
            return

        await message.send_chat_action("typing")
        try:
            answer = await asyncio.to_thread(
                core.run,
                history_key(message),
                task,
                30,
                str(message.from_user.id),
            )
        except Exception as e:  # noqa: BLE001
            log.exception("agent failed")
            answer = f"Ошибка: {type(e).__name__}: {e}"
        for chunk in _split(answer, 3500):
            await message.answer(chunk)

    await dp.start_polling(bot)


def _split(text: str, size: int) -> list[str]:
    if len(text) <= size:
        return [text]
    return [text[i : i + size] for i in range(0, len(text), size)]


if __name__ == "__main__":
    asyncio.run(main())

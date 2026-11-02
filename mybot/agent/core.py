"""Ядро агента: цикл вызовов LLM с инструментами.

Ключевое место для правок: prompt() собирает системное сообщение,
run() — цикл «модель -> инструмент -> модель -> ...».
"""
from __future__ import annotations

import json
from datetime import datetime

from openai import OpenAI

import config
from . import memory, tools

_client: OpenAI | None = None


def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=config.OPENAI_API_KEY or "not-set",
            base_url=config.OPENAI_BASE_URL,
        )
    return _client


def prompt(owner: str = "") -> str:
    """Системный промпт. Редактируется в agent/system.md + память заметок."""
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    base = config.SYSTEM_PROMPT.replace("{now}", now)
    notes = memory.notes_for_prompt(owner=owner)
    if notes:
        base += "\n\n## Что ты помнишь о пользователе\n" + notes
    return base


def run(chat_id: int, user_text: str, history_limit: int = 30, owner: str = "") -> str:
    """Один запрос пользователя -> финальный текст ответа."""
    tools.set_owner(owner)
    memory.add_message(chat_id, "user", user_text)
    messages: list[dict] = [{"role": "system", "content": prompt(owner)}]
    messages += memory.history(chat_id, history_limit)

    c = client()
    for _ in range(config.MAX_TOOL_ROUNDS):
        resp = c.chat.completions.create(
            model=config.MODEL,
            messages=messages,
            tools=tools.openai_tools_schema(),
            tool_choice="auto",
        )
        msg = resp.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:
            text = (msg.content or "").strip()
            memory.add_message(chat_id, "assistant", text)
            return text

        for call in msg.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            result = tools.run_tool(call.function.name, args)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result,
                }
            )
    return "Достигнут лимит шагов. Попробуй сформулировать задачу короче."

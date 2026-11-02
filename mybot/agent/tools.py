"""Реестр инструментов.

Добавить свой инструмент = написать функцию с декоратором @tool и описать
её docstring + типы аргументов. Схема для LLM строится автоматически.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from contextvars import ContextVar
from typing import Any, Callable

import requests

# Текущий собеседник — чтобы инструменты работали с памятью правильного человека.
_owner: ContextVar[str] = ContextVar("owner", default="")


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    func: Callable[..., Any]


REGISTRY: dict[str, Tool] = {}


def tool(name: str, description: str, **parameters: dict):
    """Декоратор: регистрирует функцию как инструмент для модели.

    parameters: keyword-аргументы вида ``url="string"`` или
    ``limit={"type": "integer", "_required": False}``.
    """

    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        props: dict[str, Any] = {}
        required: list[str] = []
        for pname, pspec in parameters.items():
            if isinstance(pspec, str):
                props[pname] = {"type": pspec}
                required.append(pname)
            else:
                pspec = dict(pspec)
                if pspec.pop("_required", True):
                    required.append(pname)
                props[pname] = pspec
        schema: dict[str, Any] = {"type": "object", "properties": props}
        if required:
            schema["required"] = required
        REGISTRY[name] = Tool(name, description, schema, fn)
        return fn

    return deco


def set_owner(owner: str) -> None:
    """Запомнить, с кем сейчас говорит агент (id пользователя)."""
    _owner.set(str(owner))


def current_owner() -> str:
    return _owner.get()


def run_tool(name: str, args: dict) -> str:
    t = REGISTRY.get(name)
    if t is None:
        return json.dumps({"error": f"unknown tool: {name}"}, ensure_ascii=False)
    try:
        result = t.func(**args)
    except TypeError as e:
        return json.dumps({"error": f"bad arguments: {e}"}, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        return json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False)
    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False, default=str)


# ---------------------------------------------------------------- базовые

@tool("now", "Текущая дата, время и часовой пояс сервера.")
def _now() -> dict:
    return {"iso": datetime.now().astimezone().isoformat()}


@tool("calc", "Посчитать выражение.", expression="str")
def _calc(expression: str) -> dict:
    allowed = set("0123456789+-*/().% **")
    if set(expression) - allowed:
        return {"error": "unsupported characters"}
    return {"result": eval(expression, {"__builtins__": {}}, {})}  # noqa: S307


@tool("web_get", "Скачать страницу по URL и вернуть текст (до 20000 символов).", url="str")
def _web_get(url: str) -> dict:
    if not url.startswith(("http://", "https://")):
        return {"error": "only http(s) is supported"}
    r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 mybot/0.1"})
    r.raise_for_status()
    return {"status": r.status_code, "text": r.text[:20000]}


@tool(
    "note_save",
    "Сохранить заметку в память агента. Используй для фактов о пользователе, которые нужно помнить между сессиями.",
    text="str",
    tag="str",
)
def _note_save(text: str, tag: str = "general") -> dict:
    from .memory import add_note

    note_id = add_note(text, tag, owner=current_owner())
    return {"saved": True, "id": note_id}


@tool(
    "note_search",
    "Поиск по сохранённым заметкам (только ваши собственные).",
    query="str",
)
def _note_search(query: str) -> dict:
    from .memory import search_notes

    return {"notes": search_notes(query, owner=current_owner())}


@tool(
    "note_list",
    "Последние сохранённые заметки.",
    limit={"type": "integer", "_required": False},
)
def _note_list(limit: int = 20) -> dict:
    from .memory import list_notes

    return {"notes": list_notes(limit, owner=current_owner())}


def openai_tools_schema() -> list[dict]:
    return [
        {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
        for t in REGISTRY.values()
    ]

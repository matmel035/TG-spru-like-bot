"""Память: история диалогов в SQLite + долговременные заметки.

Заметки принадлежат конкретному человеку (owner) — в групповых чатах
чужие заметки не подмешиваются в промпт.
"""
from __future__ import annotations

import sqlite3
import time

from config import DB_PATH


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                ts REAL NOT NULL
            )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                tag TEXT DEFAULT 'general',
                owner TEXT DEFAULT '',
                ts REAL NOT NULL
            )"""
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id, id)")
        # Миграция: добавляем owner, если база создана в старой версии
        cols = {r["name"] for r in c.execute("PRAGMA table_info(notes)").fetchall()}
        if "owner" not in cols:
            c.execute("ALTER TABLE notes ADD COLUMN owner TEXT DEFAULT ''")
        c.execute("CREATE INDEX IF NOT EXISTS idx_notes_owner ON notes(owner)")


def add_message(chat_id: int, role: str, content: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO messages (chat_id, role, content, ts) VALUES (?,?,?,?)",
            (chat_id, role, content, time.time()),
        )


def history(chat_id: int, limit: int = 30) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT role, content FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT ?",
            (chat_id, limit),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def clear_history(chat_id: int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))


def add_note(text: str, tag: str = "general", owner: str = "") -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO notes (text, tag, owner, ts) VALUES (?,?,?,?)",
            (text, tag, owner, time.time()),
        )
        return int(cur.lastrowid)


def search_notes(query: str, owner: str | None = None) -> list[dict]:
    sql = "SELECT id, text, tag, owner FROM notes WHERE text LIKE ?"
    args: list = [f"%{query}%"]
    if owner is not None:
        sql += " AND owner = ?"
        args.append(owner)
    sql += " ORDER BY id DESC LIMIT 20"
    with _conn() as c:
        rows = c.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def list_notes(limit: int = 20, owner: str | None = None) -> list[dict]:
    sql = "SELECT id, text, tag, owner FROM notes"
    args: list = []
    if owner is not None:
        sql += " WHERE owner = ?"
        args.append(owner)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with _conn() as c:
        rows = c.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def notes_for_prompt(owner: str, limit: int = 15) -> str:
    notes = list_notes(limit, owner=owner)
    if not notes:
        return ""
    return "\n".join(f"- [{n['tag']}] {n['text']}" for n in notes)

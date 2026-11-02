"""Конфигурация. Всё читается из переменных окружения (.env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL") or None

MODEL = os.environ.get("MODEL", "gpt-4o-mini")
MAX_TOOL_ROUNDS = int(os.environ.get("MAX_TOOL_ROUNDS", "12"))

# Слова-триггеры для обращения в группах: "бот, спру"
CALL_WORDS = os.environ.get("CALL_WORDS", "бот,спру")

DB_PATH = DATA_DIR / "memory.sqlite3"

# Персоны, которым бот отвечает. Пусто = всем.
ALLOWED_USER_IDS = [
    int(x) for x in os.environ.get("ALLOWED_USER_IDS", "").split(",") if x.strip()
]

SYSTEM_PROMPT = (ROOT / "agent" / "system.md").read_text(encoding="utf-8")

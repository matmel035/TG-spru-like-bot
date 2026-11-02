"""Тест логики обращения: как агент понимает, что его позвали."""
import re
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BOT = "my_agent_bot"


def strip_call_word(text: str, bot_username: str = BOT) -> str:
    out = re.sub(rf"@{re.escape(bot_username)}\b[,:!\-—]?\s*", "", text, flags=re.IGNORECASE)
    lowered = out.lstrip().lower()
    for w in ("бот", "спру"):
        if lowered.startswith(w):
            rest = out.lstrip()[len(w):]
            return rest.lstrip(" ,:!-—")
    return out.strip()


def addressed(text: str, reply_to_bot: bool = False, bot_username: str = BOT):
    if reply_to_bot:
        return True, text.strip()
    if re.search(rf"@{re.escape(bot_username)}\b", text, flags=re.IGNORECASE):
        return True, strip_call_word(text, bot_username)
    lowered = text.lstrip().lower()
    for w in ("бот", "спру"):
        if lowered.startswith(w):
            return True, strip_call_word(text, bot_username)
    return False, text.strip()


CASES = [
    ("@my_agent_bot найди кофейни", True, "найди кофейни"),
    ("бот, посчитай 2+2", True, "посчитай 2+2"),
    ("спру что нового?", True, "что нового?"),
    ("а ты не видел? я в питере был", False, "а ты не видел? я в питере был"),
    ("бот", True, ""),
    ("@my_agent_bot, помоги", True, "помоги"),
]


def main():
    for text, want_called, want_task in CASES:
        called, task = addressed(text)
        assert called == want_called, f"{text!r}: called={called}"
        assert task == want_task, f"{text!r}: task={task!r} != {want_task!r}"
        print(f"OK  {text!r} -> called={called}, task={task!r}")

    called, task = addressed("спасибо!", reply_to_bot=True)
    assert called and task == "спасибо!"
    print("OK  реплай на сообщение бота -> отвечает")


if __name__ == "__main__":
    main()
    print("OK")

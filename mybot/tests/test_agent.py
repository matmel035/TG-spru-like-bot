"""Локальный тест без Telegram и без реального API: ставим фейковый LLM."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import core, memory, tools  # noqa: E402

memory.init_db()


class FakeMsg:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []

    def model_dump(self, exclude_none=True):
        d = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {
                        "name": c.function.name,
                        "arguments": c.function.arguments,
                    },
                }
                for c in self.tool_calls
            ]
        return d


class FakeChoice:
    def __init__(self, msg):
        self.message = msg


class FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class FakeCall:
    def __init__(self, id, name, arguments):
        self.id = id
        self.function = FakeFunction(name, arguments)


class FakeCompletions:
    def __init__(self, script):
        self.script = script
        self.calls = []

    def create(self, model, messages, tools=None, tool_choice=None):
        self.calls.append(messages)
        step = self.script[len(self.calls) - 1]
        return type("R", (), {"choices": [FakeChoice(step)]})()


class FakeChat:
    def __init__(self, script):
        self.completions = FakeCompletions(script)


class FakeOpenAI:
    def __init__(self, script):
        self.chat = FakeChat(script)


def main():
    calls = {}

    def fake_create(model, messages, tools=None, tool_choice=None):
        calls["messages"] = messages
        calls["tools"] = tools
        return type("R", (), {"choices": [FakeChoice(FakeMsg("Готово: 2 + 2 = 4"))]})()

    class C:
        pass

    c = C()
    c.chat = C()
    c.chat.completions = C()
    c.chat.completions.create = fake_create
    core._client = c

    out = core.run(1, "посчитай 2+2")
    print("Ответ:", out)
    assert out.startswith("Готово")

    schema = tools.openai_tools_schema()
    names = {t["function"]["name"] for t in schema}
    print("Инструменты:", sorted(names))
    assert {"calc", "web_get", "note_save", "now"} <= names

    assert "4" in tools.run_tool("calc", {"expression": "2+2"})
    print("calc:", tools.run_tool("calc", {"expression": "2+2"}))
    print("now:", tools.run_tool("now", {}))

    nid = tools.run_tool("note_save", {"text": "Матвей из Питера", "tag": "user"})
    print("note_save:", nid)
    print("note_search:", tools.run_tool("note_search", {"query": "Матвей"}))

    hist = memory.history(1)
    print("История:", hist)
    assert hist[-1]["role"] == "assistant"


if __name__ == "__main__":
    main()
    print("OK")

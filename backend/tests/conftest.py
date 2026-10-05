import json as jsonlib
from pathlib import Path

import pytest

from app.db import Database
from app.llm import LLMResponse
from data.seed import build


@pytest.fixture(scope="session")
def db_path(tmp_path_factory) -> Path:
    return build(tmp_path_factory.mktemp("data") / "shop.db")


@pytest.fixture(scope="session")
def db(db_path) -> Database:
    return Database(db_path)


class FakeLLM:
    """Replays scripted replies in order, and records every prompt it was sent.
    Each reply is either a dict (sent as JSON) or a raw string."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls: list[list[dict]] = []
        self.json_flags: list[bool] = []

    def complete(self, messages, json=True):
        self.calls.append([dict(m) for m in messages])
        self.json_flags.append(json)
        reply = self.replies.pop(0)
        text = reply if isinstance(reply, str) else jsonlib.dumps(reply)
        return LLMResponse(text=text, input_tokens=100, output_tokens=20)


@pytest.fixture
def fake_llm():
    return FakeLLM

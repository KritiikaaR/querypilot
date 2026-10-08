"""LLM client. The agent only depends on the `LLMClient` protocol, so tests can
swap in a fake and you can add other providers later without touching agent.py."""
import json
import re
from dataclasses import dataclass
from typing import Protocol


@dataclass
class LLMResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


class LLMClient(Protocol):
    def complete(self, messages: list[dict], json: bool = True) -> LLMResponse: ...


class OpenAIClient:
    TIMEOUT_S = 20    # per request; a slow model call fails fast instead of hanging the user
    MAX_RETRIES = 1   # the SDK retries transient errors (429/5xx/timeouts) once

    def __init__(self, model: str):
        from openai import OpenAI  # imported lazily so tests don't need a key

        # Reads OPENAI_API_KEY from the environment.
        self.client = OpenAI(timeout=self.TIMEOUT_S, max_retries=self.MAX_RETRIES)
        self.model = model

    def complete(self, messages: list[dict], json: bool = True) -> LLMResponse:
        extra = {"response_format": {"type": "json_object"}} if json else {}
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0,
            **extra,
        )
        usage = resp.usage
        return LLMResponse(
            text=resp.choices[0].message.content or "",
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )


class LLMOutputError(ValueError):
    pass


def parse_llm_json(text: str) -> dict:
    """Parse the model's JSON reply, tolerating ```json fences and stray prose around it."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise LLMOutputError("Model reply was not JSON.")
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as e:
            raise LLMOutputError(f"Model reply was not valid JSON: {e}") from e
    if not isinstance(data, dict) or "sql" not in data:
        raise LLMOutputError('Model reply must be an object with an "sql" key.')
    sql = data.get("sql")
    if sql is not None and not isinstance(sql, str):
        raise LLMOutputError('"sql" must be a string or null.')
    return {"sql": sql.strip() if isinstance(sql, str) and sql.strip() else None,
            "explanation": str(data.get("explanation") or "").strip()}

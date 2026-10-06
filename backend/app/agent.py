"""The text-to-SQL loop: generate SQL -> guard -> run -> on failure, show the
error to the model and let it fix the query (up to max_attempts)."""
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .db import Database, QueryError
from .guard import GuardError, validate_and_limit
from .llm import LLMClient, LLMOutputError, parse_llm_json
from .prompts import GLOSSARY_SECTION, RETRY_PROMPT, SUMMARY_INPUT, SUMMARY_PROMPT, SYSTEM_PROMPT

log = logging.getLogger("querypilot.agent")

DATASET_TODAY = "2015-12-31"  # last day in the pizza dataset
GLOSSARY_PATH = Path(__file__).resolve().parent.parent / "data" / "glossary.md"


def load_glossary(path: Path | None = GLOSSARY_PATH) -> str:
    """Business definitions for the prompt, minus <!-- --> comments. Missing file -> "" (prompt still works)."""
    if path is None:
        return ""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        log.warning("glossary not found at %s; continuing without business definitions", path)
        return ""
    return re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()


@dataclass
class Attempt:
    sql: str | None
    error: str | None


@dataclass
class AgentResult:
    question: str
    status: str                    # "ok" | "unanswerable" | "failed"
    sql: str | None = None         # the SQL that actually ran (after guard / LIMIT)
    explanation: str = ""          # what was looked up, in everyday words
    answer: str | None = None      # plain-English answer written from the result (if summarize=True)
    columns: list[str] = field(default_factory=list)
    rows: list[list] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    error: str | None = None
    attempts: list[Attempt] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    llm_ms: float = 0.0
    db_ms: float = 0.0
    total_ms: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class TextToSQLAgent:
    SUMMARY_ROWS = 50  # rows shown to the model when writing the plain-English answer

    def __init__(self, db: Database, llm: LLMClient, max_attempts: int = 3,
                 max_rows: int = 200, timeout_ms: int = 3000, summarize: bool = False,
                 glossary_path: Path | None = GLOSSARY_PATH):
        self.db, self.llm = db, llm
        self.max_attempts, self.max_rows, self.timeout_ms = max_attempts, max_rows, timeout_ms
        self.summarize = summarize
        self._schema = db.schema_text()
        glossary = load_glossary(glossary_path)
        self._glossary = GLOSSARY_SECTION.format(glossary=glossary) if glossary else ""

    def ask(self, question: str) -> AgentResult:
        start = time.perf_counter()
        result = AgentResult(question=question, status="failed")
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT.format(
                schema=self._schema, glossary=self._glossary, today=DATASET_TODAY)},
            {"role": "user", "content": question},
        ]

        for _ in range(self.max_attempts):
            t0 = time.perf_counter()
            reply = self.llm.complete(messages)
            result.llm_ms += (time.perf_counter() - t0) * 1000
            result.input_tokens += reply.input_tokens
            result.output_tokens += reply.output_tokens
            messages.append({"role": "assistant", "content": reply.text})

            try:
                parsed = parse_llm_json(reply.text)
            except LLMOutputError as e:
                result.attempts.append(Attempt(sql=None, error=str(e)))
                messages.append({"role": "user", "content": RETRY_PROMPT.format(error=e)})
                continue

            result.explanation = parsed["explanation"]
            if parsed["sql"] is None:
                result.status = "unanswerable"
                result.attempts.append(Attempt(sql=None, error=None))
                break

            try:
                safe_sql = validate_and_limit(parsed["sql"], self.max_rows)
                qr = self.db.run(safe_sql, self.max_rows, self.timeout_ms)
            except (GuardError, QueryError) as e:
                result.attempts.append(Attempt(sql=parsed["sql"], error=str(e)))
                result.error = str(e)
                messages.append({"role": "user", "content": RETRY_PROMPT.format(error=e)})
                continue

            result.attempts.append(Attempt(sql=parsed["sql"], error=None))
            result.status, result.sql, result.error = "ok", safe_sql, None
            result.columns, result.rows, result.truncated = qr.columns, qr.rows, qr.truncated
            result.row_count, result.db_ms = len(qr.rows), qr.elapsed_ms
            break

        if result.status == "ok" and self.summarize:
            self._add_answer(result)

        if result.status == "failed" and result.error is None and result.attempts:
            result.error = result.attempts[-1].error
        result.llm_ms = round(result.llm_ms, 1)
        result.total_ms = round((time.perf_counter() - start) * 1000, 1)
        return result

    def _add_answer(self, result: AgentResult) -> None:
        """Second, small LLM call: turn the result table into a plain-English answer.
        Best effort: if it fails, the user still gets the table and chart."""
        shown = result.rows[: self.SUMMARY_ROWS]
        table = "\n".join([" | ".join(result.columns)] + [" | ".join(str(v) for v in r) for r in shown])
        cut = ", cut off" if result.truncated or len(result.rows) > len(shown) else ""
        messages = [
            {"role": "system", "content": SUMMARY_PROMPT},
            {"role": "user", "content": SUMMARY_INPUT.format(
                question=result.question, row_count=len(shown), truncated=cut, table=table or "(no rows)")},
        ]
        t0 = time.perf_counter()
        try:
            reply = self.llm.complete(messages, json=False)
        except Exception:
            log.warning("answer summary failed", exc_info=True)
            return
        finally:
            result.llm_ms += (time.perf_counter() - t0) * 1000
        result.input_tokens += reply.input_tokens
        result.output_tokens += reply.output_tokens
        text = reply.text.strip()
        result.answer = text[:600] if text else None

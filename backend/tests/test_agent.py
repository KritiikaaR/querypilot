from app.agent import TextToSQLAgent
from app.llm import LLMOutputError, parse_llm_json

import pytest


def make_agent(db, llm, **kw):
    return TextToSQLAgent(db, llm, max_attempts=kw.get("max_attempts", 3), max_rows=50, timeout_ms=1000,
                          summarize=kw.get("summarize", False))


def test_happy_path(db, fake_llm):
    llm = fake_llm([{"sql": "SELECT COUNT(*) AS n FROM pizza_types", "explanation": "Counts pizza types."}])
    res = make_agent(db, llm).ask("How many pizza types?")
    assert res.status == "ok"
    assert res.columns == ["n"] and res.rows == [[32]]
    assert len(res.attempts) == 1
    assert res.input_tokens == 100 and res.output_tokens == 20


def test_self_corrects_after_sql_error(db, fake_llm):
    llm = fake_llm([
        {"sql": "SELECT COUNT(*) FROM pizza", "explanation": "typo"},
        {"sql": "SELECT COUNT(*) FROM pizzas", "explanation": "fixed"},
    ])
    res = make_agent(db, llm).ask("How many menu items?")
    assert res.status == "ok" and res.rows == [[96]]
    assert len(res.attempts) == 2 and "no such table" in res.attempts[0].error
    # The DB error was fed back to the model on the second call.
    assert "no such table" in llm.calls[1][-1]["content"]


def test_self_corrects_after_guard_rejection(db, fake_llm):
    llm = fake_llm([
        {"sql": "DELETE FROM orders", "explanation": "bad"},
        {"sql": "SELECT COUNT(*) FROM orders", "explanation": "ok"},
    ])
    res = make_agent(db, llm).ask("Clear orders then count them")
    assert res.status == "ok" and res.rows == [[21350]]
    assert "SELECT" in llm.calls[1][-1]["content"]


def test_gives_up_after_max_attempts(db, fake_llm):
    llm = fake_llm([{"sql": "SELECT nope FROM orders", "explanation": "x"}] * 3)
    res = make_agent(db, llm).ask("?")
    assert res.status == "failed" and len(res.attempts) == 3
    assert "no such column" in res.error


def test_unanswerable(db, fake_llm):
    llm = fake_llm([{"sql": None, "explanation": "There is no cost data."}])
    res = make_agent(db, llm).ask("What is the profit margin?")
    assert res.status == "unanswerable" and "cost" in res.explanation


def test_recovers_from_non_json_reply(db, fake_llm):
    llm = fake_llm(["Sure! Here's your query: SELECT 1", {"sql": "SELECT 1 AS one", "explanation": "x"}])
    res = make_agent(db, llm).ask("one?")
    assert res.status == "ok" and res.rows == [[1]]
    assert res.attempts[0].error and len(res.attempts) == 2


def test_result_limit_is_enforced(db, fake_llm):
    llm = fake_llm([{"sql": "SELECT order_id FROM orders", "explanation": "all orders"}])
    res = make_agent(db, llm).ask("List all orders")
    assert res.row_count == 50 and res.truncated


def test_schema_is_in_system_prompt(db, fake_llm):
    llm = fake_llm([{"sql": "SELECT 1", "explanation": ""}])
    make_agent(db, llm).ask("x")
    system = llm.calls[0][0]
    assert system["role"] == "system" and "CREATE TABLE order_details" in system["content"]


def test_system_prompt_narrows_refusals(db, fake_llm):
    llm = fake_llm([{"sql": "SELECT 1", "explanation": ""}])
    make_agent(db, llm).ask("x")
    system = llm.calls[0][0]["content"]
    assert 'Set "sql" to null only when the question needs information that no column holds' in system
    assert "always write the query" in system
    assert "cannot be answered from this data" not in system  # the old, broader rule is gone


@pytest.mark.parametrize("text,sql", [
    ('{"sql": "SELECT 1", "explanation": "e"}', "SELECT 1"),
    ('```json\n{"sql": "SELECT 1", "explanation": "e"}\n```', "SELECT 1"),
    ('Here you go: {"sql": "SELECT 1"} hope that helps', "SELECT 1"),
    ('{"sql": null, "explanation": "cannot"}', None),
    ('{"sql": "   ", "explanation": "blank"}', None),
])
def test_parse_llm_json(text, sql):
    assert parse_llm_json(text)["sql"] == sql


@pytest.mark.parametrize("text", ["no json here", '{"answer": 1}', '{"sql": 5}'])
def test_parse_llm_json_rejects_bad_output(text):
    with pytest.raises(LLMOutputError):
        parse_llm_json(text)


# ---- plain-English answer (second LLM call) ----

def test_answer_summary_added_after_success(db, fake_llm):
    llm = fake_llm([
        {"sql": "SELECT COUNT(*) AS orders FROM orders", "explanation": "Number of orders."},
        "The shop took 21,350 orders in 2015.",
    ])
    res = make_agent(db, llm, summarize=True).ask("How many orders were there?")
    assert res.status == "ok" and res.answer == "The shop took 21,350 orders in 2015."
    assert llm.json_flags == [True, False]           # summary is plain text, not JSON mode
    summary_prompt = llm.calls[1][-1]["content"]
    assert "How many orders were there?" in summary_prompt and "21350" in summary_prompt
    assert res.input_tokens == 200                    # both calls are counted


def test_no_summary_when_unanswerable_or_failed(db, fake_llm):
    llm = fake_llm([{"sql": None, "explanation": "No delivery data."}])
    assert make_agent(db, llm, summarize=True).ask("Which driver?").answer is None
    assert len(llm.calls) == 1

    llm = fake_llm([{"sql": "SELECT nope FROM orders", "explanation": "x"}] * 3)
    res = make_agent(db, llm, summarize=True).ask("?")
    assert res.status == "failed" and res.answer is None and len(llm.calls) == 3


def test_summary_failure_still_returns_the_result(db):
    class SummaryBreaks:
        def __init__(self):
            self.n = 0

        def complete(self, messages, json=True):
            from app.llm import LLMResponse
            self.n += 1
            if self.n == 1:
                return LLMResponse('{"sql": "SELECT COUNT(*) FROM orders", "explanation": "x"}', 10, 5)
            raise TimeoutError("summary timed out")

    res = make_agent(db, SummaryBreaks(), summarize=True).ask("How many orders?")
    assert res.status == "ok" and res.rows == [[21350]] and res.answer is None


def test_summary_only_sees_first_rows(db, fake_llm):
    llm = fake_llm([{"sql": "SELECT order_id FROM orders", "explanation": "x"}, "ok"])
    make_agent(db, llm, summarize=True).ask("List orders")
    prompt = llm.calls[1][-1]["content"]
    assert "cut off" in prompt and prompt.count("\n") < TextToSQLAgent.SUMMARY_ROWS + 10

"""The eval runner's scoring, report rows and --repeat math, driven by FakeLLM."""
import pytest

from app.agent import TextToSQLAgent
from evals.run_eval import format_failed, run_once, summarize_repeats, summarize_run

QUESTIONS = [
    {"id": "t01", "difficulty": "easy", "question": "How many pizza types?",
     "gold_sql": "SELECT COUNT(*) FROM pizza_types"},
    {"id": "t02", "difficulty": "unanswerable", "question": "What is the profit margin?", "gold_sql": None},
]


def run_with(db, fake_llm, replies):
    agent = TextToSQLAgent(db, fake_llm(replies), max_attempts=1, max_rows=10_000, timeout_ms=1000)
    return run_once(agent, db, QUESTIONS, verbose=False)


def test_report_rows_include_explanation(db, fake_llm):
    rows = run_with(db, fake_llm, [
        {"sql": "SELECT COUNT(*) AS n FROM pizza_types", "explanation": "Counts the pizza types."},
        {"sql": None, "explanation": "There is no cost data."},
    ])
    assert [r["correct"] for r in rows] == [True, True]
    assert rows[0]["explanation"] == "Counts the pizza types."
    assert rows[1]["explanation"] == "There is no cost data." and rows[1]["pred_sql"] is None


def test_wrong_refusal_is_scored_as_failure(db, fake_llm):
    rows = run_with(db, fake_llm, [
        {"sql": None, "explanation": "Not enough data."},
        {"sql": None, "explanation": "There is no cost data."},
    ])
    assert [r["correct"] for r in rows] == [False, True]
    assert rows[0]["status"] == "unanswerable" and rows[0]["explanation"] == "Not enough data."
    summary = summarize_run(rows)
    assert summary["execution_accuracy"] == 50.0 and summary["failed_ids"] == ["t01"]


def _rows(passed: dict[str, bool]) -> list[dict]:
    return [{"id": qid, "difficulty": "easy", "correct": ok, "lenient_correct": ok, "attempts": 1,
             "self_corrected": False, "total_ms": 10.0, "input_tokens": 1, "output_tokens": 1}
            for qid, ok in passed.items()]


def test_summarize_repeats_mean_min_max_and_pass_counts():
    runs = [
        _rows({"a": True, "b": True, "c": False, "d": True}),   # 75%
        _rows({"a": True, "b": False, "c": False, "d": True}),  # 50%
        _rows({"a": True, "b": True, "c": True, "d": True}),    # 100%
    ]
    agg = summarize_repeats(runs)
    assert agg["runs"] == 3
    assert agg["per_run_accuracy"] == [75.0, 50.0, 100.0]
    assert agg["execution_accuracy_mean"] == 75.0
    assert agg["execution_accuracy_min"] == 50.0 and agg["execution_accuracy_max"] == 100.0
    assert agg["per_question_passes"] == {"a": "3/3", "b": "2/3", "c": "1/3", "d": "3/3"}
    assert agg["unstable_or_failing"] == ["b", "c"]


def test_summarize_repeats_single_run_matches_summary():
    run = _rows({"a": True, "b": False, "c": True})
    agg = summarize_repeats([run])
    acc = summarize_run(run)["execution_accuracy"]
    assert agg["execution_accuracy_mean"] == agg["execution_accuracy_min"] == agg["execution_accuracy_max"] == acc
    assert agg["per_question_passes"] == {"a": "1/1", "b": "0/1", "c": "1/1"}


@pytest.mark.parametrize("ids,text", [([], "Failed: none"), (["m03", "h07"], "Failed (2): m03, h07")])
def test_format_failed(ids, text):
    assert format_failed(ids) == text

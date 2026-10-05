"""Keep the eval set honest: every gold query must pass the guard, run, and return rows."""
import json
from pathlib import Path

import pytest

from app.guard import validate_and_limit
from evals.scoring import results_match, results_match_lenient

QUESTIONS = json.loads((Path(__file__).resolve().parent.parent / "evals" / "questions.json").read_text())


def test_ids_are_unique():
    ids = [q["id"] for q in QUESTIONS]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("q", [q for q in QUESTIONS if q["gold_sql"]], ids=lambda q: q["id"])
def test_gold_sql_runs_and_returns_rows(db, q):
    safe = validate_and_limit(q["gold_sql"], max_rows=10_000)
    result = db.run(safe, max_rows=10_000, timeout_ms=5000)
    assert result.rows, f"{q['id']} returned no rows"


def test_scoring_ignores_column_order_and_names():
    assert results_match([[1, "a"], [2, "b"]], [["b", 2], ["a", 1]], ordered=False)
    assert not results_match([[1, "a"], [2, "b"]], [["b", 2], ["a", 1]], ordered=True)


def test_scoring_rounds_floats():
    assert results_match([[3.14159]], [[3.14]], ordered=False)


def test_scoring_treats_numeric_strings_as_numbers():
    assert results_match([["12", 2520]], [[12, 2520]], ordered=True)


def test_lenient_accepts_extra_columns_only():
    gold = [["Veggie"]]
    assert not results_match([["Veggie", 4.2]], gold, ordered=False)
    assert results_match_lenient([["Veggie", 4.2]], gold, ordered=False)
    assert not results_match_lenient([["Classic", 4.2]], gold, ordered=False)

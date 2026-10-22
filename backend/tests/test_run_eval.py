"""The eval runner's scoring, report rows and --repeat math, driven by FakeLLM."""
import pytest

from app.agent import TextToSQLAgent
from evals.run_eval import format_failed, format_unfaithful, run_once, summarize_repeats, summarize_run

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


# ---- answer faithfulness (--faithfulness); the judge is faked, no API calls ----

class FakeJudge:
    """Stands in for FaithfulnessJudge: records what it was asked and replies with a fixed verdict."""

    def __init__(self, score=1.0, issues=(), error=None):
        self.score, self.issues, self.error = score, list(issues), error
        self.calls: list[tuple[str, str, str]] = []

    def __call__(self, question, answer, context):
        self.calls.append((question, answer, context))
        if self.error:
            raise self.error
        return {"score": self.score, "faithful": self.score >= 1.0, "issues": self.issues, "cost_usd": 0.001}


def run_judged(db, fake_llm, replies, judge):
    agent = TextToSQLAgent(db, fake_llm(replies), max_attempts=1, max_rows=10_000, timeout_ms=1000, summarize=True)
    return run_once(agent, db, QUESTIONS, verbose=False, judge=judge)


ANSWERED = [
    {"sql": "SELECT COUNT(*) AS n FROM pizza_types", "explanation": "Counts the pizza types."},
    "There are 40 pizza types.",                                    # the summary call
    {"sql": None, "explanation": "There is no cost data."},         # unanswerable: no summary call
]


def test_judge_sees_question_answer_and_the_rows_the_writer_saw(db, fake_llm):
    judge = FakeJudge(score=0.5, issues=["There are 40 pizza types. -> no: the result shows 32."])
    rows = run_judged(db, fake_llm, ANSWERED, judge)
    assert judge.calls == [("How many pizza types?", "There are 40 pizza types.", "Result (1 rows):\nn\n32")]
    assert rows[0]["correct"] is True and rows[0]["faithful"] is False   # right rows, wrong answer
    assert rows[0]["faithfulness"] == 0.5 and rows[0]["answer"] == "There are 40 pizza types."
    assert rows[0]["faithfulness_issues"] == judge.issues


def test_refusals_and_missing_answers_are_not_scored(db, fake_llm):
    judge = FakeJudge()
    # "" from the summary call means no answer was written.
    rows = run_judged(db, fake_llm, [ANSWERED[0], "", ANSWERED[2]], judge)
    assert judge.calls == []
    assert [r["faithfulness"] for r in rows] == [None, None] and [r["faithful"] for r in rows] == [None, None]
    s = summarize_run(rows)
    assert s["faithfulness_scored"] == 0 and s["faithfulness_not_scored"] == 2
    assert s["faithfulness_mean"] is None and s["unfaithful_ids"] == []


def test_judge_error_is_recorded_and_accuracy_still_reported(db, fake_llm):
    rows = run_judged(db, fake_llm, ANSWERED, FakeJudge(error=TimeoutError("judge timed out")))
    assert rows[0]["faithfulness"] is None and rows[0]["faithfulness_error"] == "TimeoutError: judge timed out"
    s = summarize_run(rows)
    assert s["execution_accuracy"] == 100.0 and s["judge_error_ids"] == ["t01"] and s["unfaithful_ids"] == []


def test_without_judge_report_and_summary_are_unchanged(db, fake_llm):
    rows = run_with(db, fake_llm, [ANSWERED[0], ANSWERED[2]])
    assert not any(k.startswith(("faith", "judge")) or k == "answer" for r in rows for k in r)
    assert not any(k.startswith(("faith", "unfaithful", "judge")) for k in summarize_run(rows))
    assert "faithfulness_mean" not in summarize_repeats([rows, rows])


def _judged(scores: dict[str, float | None]) -> list[dict]:
    rows = _rows({qid: True for qid in scores})
    for r in rows:
        score = scores[r["id"]]
        r.update(answer="x", faithfulness=score, faithful=None if score is None else score >= 1.0,
                 faithfulness_issues=[], faithfulness_error=None, judge_cost_usd=0.001 if score is not None else 0.0)
    return rows


def test_summarize_run_faithfulness_mean_and_unfaithful_ids():
    s = summarize_run(_judged({"a": 1.0, "b": 0.5, "c": None, "d": 0.75}))
    assert s["faithfulness_scored"] == 3 and s["faithfulness_not_scored"] == 1
    assert s["faithfulness_mean"] == 0.75                      # (1 + 0.5 + 0.75) / 3; "c" is left out
    assert s["unfaithful_ids"] == ["b", "d"] and s["judge_cost_usd"] == 0.003
    assert s["execution_accuracy"] == 100.0                    # accuracy fields untouched


def test_summarize_repeats_faithfulness():
    runs = [_judged({"a": 1.0, "b": 0.5}), _judged({"a": 1.0, "b": 1.0}), _judged({"a": None, "b": 0.5})]
    agg = summarize_repeats(runs)
    assert agg["per_run_faithfulness"] == [0.75, 1.0, 0.5]
    assert agg["faithfulness_mean"] == 0.75
    assert agg["unfaithful_counts"] == {"b": "2/3"}
    assert agg["execution_accuracy_mean"] == 100.0


def test_format_unfaithful():
    rows = _judged({"a": 1.0, "b": 0.5})
    rows[1].update(answer="Sales went up.", faithfulness_issues=["Sales went up. -> no: they fell."])
    assert format_unfaithful(rows) == ("Unfaithful answers (1):\n  b (0.50): Sales went up.\n"
                                       "      - Sales went up. -> no: they fell.")
    assert format_unfaithful(_judged({"a": 1.0})) == "Unfaithful answers: none"


def test_faithfulness_judge_config_and_issues(monkeypatch):
    """Our wrapper around deepeval, with FaithfulnessMetric replaced by a fake."""
    pytest.importorskip("deepeval")
    from deepeval.metrics.base_metric import Verdict
    from deepeval.metrics.faithfulness.schema import FaithfulnessVerdict
    from evals import faithfulness

    made = []

    class FakeMetric:
        def __init__(self, **kw):
            self.kw = kw
            made.append(self)

        def measure(self, test_case, _show_indicator=True):
            self.test_case = test_case
            self.claims = ["Revenue rose.", "December revenue was $64,701.15."]
            self.verdicts = [FaithfulnessVerdict(verdict=Verdict.NO, reason="It fell."),
                             FaithfulnessVerdict(verdict=Verdict.YES)]
            self.score, self.evaluation_cost = 0.5, 0.0002
            return self.score

    monkeypatch.setattr(faithfulness, "FaithfulnessMetric", FakeMetric)
    out = faithfulness.FaithfulnessJudge()("How did revenue change?", "Revenue rose to $64,701.15.", "ROWS")
    assert out == {"score": 0.5, "faithful": False, "issues": ["Revenue rose. -> no: It fell."], "cost_usd": 0.0002}
    kw = made[0].kw
    assert kw["model"] == "gpt-4o-mini" and kw["threshold"] == 1.0
    assert kw["penalize_ambiguous_claims"] is True and kw["include_reason"] is False
    tc = made[0].test_case
    assert (tc.input, tc.actual_output, tc.retrieval_context) == (
        "How did revenue change?", "Revenue rose to $64,701.15.", ["ROWS"])

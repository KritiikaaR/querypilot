"""Run the agent over evals/questions.json and report execution accuracy.

Run from backend/ (needs OPENAI_API_KEY):
    python -m evals.run_eval
    python -m evals.run_eval --model gpt-4o --only h01,h02
    python -m evals.run_eval --repeat 3      # mean/min/max over 3 full runs
    python -m evals.run_eval --faithfulness  # also judge each plain-English answer against its rows

Writes a full per-question report to evals/results/<timestamp>-<model>.json.
"""
import argparse
import json
import statistics
import time
from datetime import datetime
from pathlib import Path

from app.agent import TextToSQLAgent, format_result
from app.config import settings
from app.db import Database
from app.llm import OpenAIClient

from .scoring import results_match, results_match_lenient

HERE = Path(__file__).resolve().parent


def gold_is_ordered(sql: str) -> bool:
    return "ORDER BY" in sql.upper().split(")")[-1]  # only the outermost ORDER BY counts


def score_answer(judge, res, max_rows: int) -> dict:
    """Faithfulness fields for one report row. Only answers to queries that ran are scored;
    no answer (refusal, failure, summary call failed) is "not scored", never "unfaithful"."""
    out = {"answer": res.answer, "faithfulness": None, "faithful": None, "faithfulness_issues": [],
           "faithfulness_error": None, "judge_cost_usd": 0.0}
    if res.status != "ok" or not res.answer:
        return out
    try:  # a judge outage shouldn't throw away the accuracy results of the whole run
        verdict = judge(res.question, res.answer, format_result(res, max_rows))
    except Exception as e:
        out["faithfulness_error"] = f"{type(e).__name__}: {e}"
        return out
    out.update(faithfulness=verdict["score"], faithful=verdict["faithful"],
               faithfulness_issues=verdict["issues"], judge_cost_usd=verdict["cost_usd"])
    return out


def run_once(agent, db, questions, verbose: bool = True, judge=None) -> list[dict]:
    """Ask every question once and score it against its gold query. One report row per question.
    With a judge (and an agent built with summarize=True), also score each answer's faithfulness."""
    rows_out = []
    for q in questions:
        res = agent.ask(q["question"])
        if q["gold_sql"] is None:
            correct = lenient = res.status == "unanswerable"
        elif res.status != "ok":
            correct = lenient = False
        else:
            gold = db.run(q["gold_sql"], max_rows=10_000, timeout_ms=10_000)
            ordered = gold_is_ordered(q["gold_sql"])
            correct = results_match(res.rows, gold.rows, ordered)
            lenient = results_match_lenient(res.rows, gold.rows, ordered)
        row = {**q, "correct": correct, "lenient_correct": lenient, "status": res.status,
               "pred_sql": res.sql, "explanation": res.explanation, "attempts": len(res.attempts),
               "self_corrected": res.status == "ok" and len(res.attempts) > 1,
               "error": res.error, "total_ms": res.total_ms,
               "input_tokens": res.input_tokens, "output_tokens": res.output_tokens}
        if judge is not None:
            row.update(score_answer(judge, res, agent.SUMMARY_ROWS))
        rows_out.append(row)
        if verbose:
            mark = "PASS" if correct else ("~ok " if lenient else "FAIL")
            faith = f" faith={row['faithfulness']:.2f}" if row.get("faithfulness") is not None else ""
            print(f"[{mark}] {q['id']:>4} ({q['difficulty']:<12}) attempts={len(res.attempts)} "
                  f"{res.total_ms:>7.0f} ms{faith}  {q['question']}")
    return rows_out


def summarize_run(rows_out: list[dict]) -> dict:
    n = len(rows_out)
    lat = sorted(r["total_ms"] for r in rows_out)
    summary = {
        "questions": n,
        "execution_accuracy": round(100 * sum(r["correct"] for r in rows_out) / n, 1),
        "lenient_accuracy": round(100 * sum(r["lenient_correct"] for r in rows_out) / n, 1),
        "by_difficulty": {
            d: round(100 * sum(r["correct"] for r in rows_out if r["difficulty"] == d)
                     / max(1, sum(1 for r in rows_out if r["difficulty"] == d)), 1)
            for d in sorted({r["difficulty"] for r in rows_out})
        },
        "failed_ids": [r["id"] for r in rows_out if not r["correct"]],
        "self_corrected": sum(r["self_corrected"] for r in rows_out),
        "avg_attempts": round(statistics.mean(r["attempts"] for r in rows_out), 2),
        "p50_ms": lat[n // 2], "p95_ms": lat[min(n - 1, int(n * 0.95))],
        "total_input_tokens": sum(r["input_tokens"] for r in rows_out),
        "total_output_tokens": sum(r["output_tokens"] for r in rows_out),
    }
    if any("faithfulness" in r for r in rows_out):  # only runs with --faithfulness
        summary.update(summarize_faithfulness(rows_out))
    return summary


def summarize_faithfulness(rows_out: list[dict]) -> dict:
    """Mean score and failures over the answers the judge scored; the rest are counted, not averaged in."""
    scored = [r for r in rows_out if r["faithfulness"] is not None]
    return {
        "faithfulness_scored": len(scored),
        "faithfulness_not_scored": len(rows_out) - len(scored),
        "faithfulness_mean": round(statistics.mean(r["faithfulness"] for r in scored), 3) if scored else None,
        "unfaithful_ids": [r["id"] for r in scored if not r["faithful"]],
        "judge_error_ids": [r["id"] for r in rows_out if r["faithfulness_error"]],
        "judge_cost_usd": round(sum(r["judge_cost_usd"] for r in rows_out), 4),
    }


def summarize_repeats(runs: list[list[dict]]) -> dict:
    """Aggregate several full runs: mean/min/max accuracy and how often each question passed."""
    n_runs = len(runs)
    summaries = [summarize_run(r) for r in runs]
    accs = [s["execution_accuracy"] for s in summaries]
    lenient = [s["lenient_accuracy"] for s in summaries]
    passes: dict[str, int] = {}
    for run in runs:
        for r in run:
            passes[r["id"]] = passes.get(r["id"], 0) + bool(r["correct"])
    agg = {
        "runs": n_runs,
        "execution_accuracy_mean": round(statistics.mean(accs), 1),
        "execution_accuracy_min": min(accs),
        "execution_accuracy_max": max(accs),
        "lenient_accuracy_mean": round(statistics.mean(lenient), 1),
        "per_run_accuracy": accs,
        "per_question_passes": {qid: f"{k}/{n_runs}" for qid, k in passes.items()},
        "unstable_or_failing": [qid for qid, k in passes.items() if k < n_runs],
    }
    if all("faithfulness_mean" in s for s in summaries):
        means = [s["faithfulness_mean"] for s in summaries]
        unfaithful: dict[str, int] = {}
        for s in summaries:
            for qid in s["unfaithful_ids"]:
                unfaithful[qid] = unfaithful.get(qid, 0) + 1
        scored_means = [m for m in means if m is not None]
        agg.update({
            "faithfulness_mean": round(statistics.mean(scored_means), 3) if scored_means else None,
            "per_run_faithfulness": means,
            "unfaithful_counts": {qid: f"{k}/{n_runs}" for qid, k in unfaithful.items()},
            "judge_cost_usd": round(sum(s["judge_cost_usd"] for s in summaries), 4),
        })
    return agg


def format_failed(failed_ids: list[str]) -> str:
    return f"Failed ({len(failed_ids)}): {', '.join(failed_ids)}" if failed_ids else "Failed: none"


def format_unfaithful(rows_out: list[dict]) -> str:
    """One block per unfaithful answer: the answer and the claims the judge rejected."""
    bad = [r for r in rows_out if r.get("faithful") is False]
    if not bad:
        return "Unfaithful answers: none"
    lines = [f"Unfaithful answers ({len(bad)}):"]
    for r in bad:
        lines.append(f"  {r['id']} ({r['faithfulness']:.2f}): {r['answer']}")
        lines += [f"      - {issue}" for issue in r["faithfulness_issues"]]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=settings.openai_model)
    ap.add_argument("--only", default="", help="comma-separated question ids")
    ap.add_argument("--repeat", type=int, default=1, help="run the whole set N times and aggregate")
    ap.add_argument("--faithfulness", action="store_true",
                    help="also write each answer and have an LLM judge check it against the rows (deepeval)")
    ap.add_argument("--judge-model", default="gpt-4o-mini", help="judge model for --faithfulness")
    args = ap.parse_args()
    if args.repeat < 1:
        ap.error("--repeat must be at least 1")

    judge = None
    if args.faithfulness:
        from .faithfulness import FaithfulnessJudge  # deepeval is only needed for this mode
        judge = FaithfulnessJudge(args.judge_model)

    questions = json.loads((HERE / "questions.json").read_text())
    if args.only:
        wanted = set(args.only.split(","))
        questions = [q for q in questions if q["id"] in wanted]

    db = Database(settings.db_path)
    agent = TextToSQLAgent(db, OpenAIClient(args.model), max_attempts=settings.max_attempts,
                           max_rows=10_000, timeout_ms=settings.query_timeout_ms, summarize=judge is not None)

    runs, run_reports = [], []
    for i in range(args.repeat):
        if args.repeat > 1:
            print(f"\n=== Run {i + 1}/{args.repeat} ===")
        start = time.time()
        rows_out = run_once(agent, db, questions, judge=judge)
        summary = {"model": args.model, **summarize_run(rows_out),
                   "wall_seconds": round(time.time() - start, 1)}
        if judge is not None:
            summary["judge_model"] = args.judge_model
        runs.append(rows_out)
        run_reports.append({"summary": summary, "results": rows_out})
        print("\n" + json.dumps(summary, indent=2))
        print(format_failed(summary["failed_ids"]))
        if judge is not None:
            print(format_unfaithful(rows_out))

    if args.repeat == 1:
        report = run_reports[0]
    else:
        aggregate = {"model": args.model, **summarize_repeats(runs)}
        report = {"aggregate": aggregate, "runs": run_reports}
        print(f"\n=== {args.repeat} runs ===")
        print(f"execution accuracy: mean {aggregate['execution_accuracy_mean']}%  "
              f"min {aggregate['execution_accuracy_min']}%  max {aggregate['execution_accuracy_max']}%  "
              f"(runs: {aggregate['per_run_accuracy']})")
        unstable = aggregate["unstable_or_failing"]
        if unstable:
            print("Not passing every run: " + ", ".join(
                f"{qid}: {aggregate['per_question_passes'][qid]}" for qid in unstable))
        else:
            print(f"Every question passed {args.repeat}/{args.repeat}.")
        if judge is not None:
            print(f"faithfulness: mean {aggregate['faithfulness_mean']}  (runs: {aggregate['per_run_faithfulness']})"
                  f"  unfaithful: {aggregate['unfaithful_counts'] or 'none'}")

    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    suffix = (f"-x{args.repeat}" if args.repeat > 1 else "") + ("-faith" if judge is not None else "")
    out = out_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{args.model}{suffix}.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\nFull report: {out}")


if __name__ == "__main__":
    main()

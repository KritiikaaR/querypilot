"""Run the agent over evals/questions.json and report execution accuracy.

Run from backend/ (needs OPENAI_API_KEY):
    python -m evals.run_eval
    python -m evals.run_eval --model gpt-4o --only h01,h02
    python -m evals.run_eval --repeat 3      # mean/min/max over 3 full runs

Writes a full per-question report to evals/results/<timestamp>-<model>.json.
"""
import argparse
import json
import statistics
import time
from datetime import datetime
from pathlib import Path

from app.agent import TextToSQLAgent
from app.config import settings
from app.db import Database
from app.llm import OpenAIClient

from .scoring import results_match, results_match_lenient

HERE = Path(__file__).resolve().parent


def gold_is_ordered(sql: str) -> bool:
    return "ORDER BY" in sql.upper().split(")")[-1]  # only the outermost ORDER BY counts


def run_once(agent, db, questions, verbose: bool = True) -> list[dict]:
    """Ask every question once and score it against its gold query. One report row per question."""
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
        rows_out.append({**q, "correct": correct, "lenient_correct": lenient, "status": res.status,
                         "pred_sql": res.sql, "explanation": res.explanation, "attempts": len(res.attempts),
                         "self_corrected": res.status == "ok" and len(res.attempts) > 1,
                         "error": res.error, "total_ms": res.total_ms,
                         "input_tokens": res.input_tokens, "output_tokens": res.output_tokens})
        if verbose:
            mark = "PASS" if correct else ("~ok " if lenient else "FAIL")
            print(f"[{mark}] {q['id']:>4} ({q['difficulty']:<12}) attempts={len(res.attempts)} "
                  f"{res.total_ms:>7.0f} ms  {q['question']}")
    return rows_out


def summarize_run(rows_out: list[dict]) -> dict:
    n = len(rows_out)
    lat = sorted(r["total_ms"] for r in rows_out)
    return {
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
    return {
        "runs": n_runs,
        "execution_accuracy_mean": round(statistics.mean(accs), 1),
        "execution_accuracy_min": min(accs),
        "execution_accuracy_max": max(accs),
        "lenient_accuracy_mean": round(statistics.mean(lenient), 1),
        "per_run_accuracy": accs,
        "per_question_passes": {qid: f"{k}/{n_runs}" for qid, k in passes.items()},
        "unstable_or_failing": [qid for qid, k in passes.items() if k < n_runs],
    }


def format_failed(failed_ids: list[str]) -> str:
    return f"Failed ({len(failed_ids)}): {', '.join(failed_ids)}" if failed_ids else "Failed: none"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=settings.openai_model)
    ap.add_argument("--only", default="", help="comma-separated question ids")
    ap.add_argument("--repeat", type=int, default=1, help="run the whole set N times and aggregate")
    args = ap.parse_args()
    if args.repeat < 1:
        ap.error("--repeat must be at least 1")

    questions = json.loads((HERE / "questions.json").read_text())
    if args.only:
        wanted = set(args.only.split(","))
        questions = [q for q in questions if q["id"] in wanted]

    db = Database(settings.db_path)
    agent = TextToSQLAgent(db, OpenAIClient(args.model), max_attempts=settings.max_attempts,
                           max_rows=10_000, timeout_ms=settings.query_timeout_ms)

    runs, run_reports = [], []
    for i in range(args.repeat):
        if args.repeat > 1:
            print(f"\n=== Run {i + 1}/{args.repeat} ===")
        start = time.time()
        rows_out = run_once(agent, db, questions)
        summary = {"model": args.model, **summarize_run(rows_out),
                   "wall_seconds": round(time.time() - start, 1)}
        runs.append(rows_out)
        run_reports.append({"summary": summary, "results": rows_out})
        print("\n" + json.dumps(summary, indent=2))
        print(format_failed(summary["failed_ids"]))

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

    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    suffix = f"-x{args.repeat}" if args.repeat > 1 else ""
    out = out_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{args.model}{suffix}.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\nFull report: {out}")


if __name__ == "__main__":
    main()

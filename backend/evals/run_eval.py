"""Run the agent over evals/questions.json and report execution accuracy.

Run from backend/ (needs OPENAI_API_KEY):
    python -m evals.run_eval
    python -m evals.run_eval --model gpt-4o --only h01,h02

Writes a full per-question report to evals/results/<timestamp>.json.
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=settings.openai_model)
    ap.add_argument("--only", default="", help="comma-separated question ids")
    args = ap.parse_args()

    questions = json.loads((HERE / "questions.json").read_text())
    if args.only:
        wanted = set(args.only.split(","))
        questions = [q for q in questions if q["id"] in wanted]

    db = Database(settings.db_path)
    agent = TextToSQLAgent(db, OpenAIClient(args.model), max_attempts=settings.max_attempts,
                           max_rows=10_000, timeout_ms=settings.query_timeout_ms)

    rows_out, start = [], time.time()
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
                         "pred_sql": res.sql, "attempts": len(res.attempts),
                         "self_corrected": res.status == "ok" and len(res.attempts) > 1,
                         "error": res.error, "total_ms": res.total_ms,
                         "input_tokens": res.input_tokens, "output_tokens": res.output_tokens})
        mark = "PASS" if correct else ("~ok " if lenient else "FAIL")
        print(f"[{mark}] {q['id']:>4} ({q['difficulty']:<12}) attempts={len(res.attempts)} "
              f"{res.total_ms:>7.0f} ms  {q['question']}")

    n = len(rows_out)
    acc = sum(r["correct"] for r in rows_out) / n
    lenient_acc = sum(r["lenient_correct"] for r in rows_out) / n
    lat = sorted(r["total_ms"] for r in rows_out)
    summary = {
        "model": args.model, "questions": n,
        "execution_accuracy": round(acc * 100, 1),
        "lenient_accuracy": round(lenient_acc * 100, 1),
        "by_difficulty": {
            d: round(100 * sum(r["correct"] for r in rows_out if r["difficulty"] == d)
                     / max(1, sum(1 for r in rows_out if r["difficulty"] == d)), 1)
            for d in sorted({r["difficulty"] for r in rows_out})
        },
        "self_corrected": sum(r["self_corrected"] for r in rows_out),
        "avg_attempts": round(statistics.mean(r["attempts"] for r in rows_out), 2),
        "p50_ms": lat[n // 2], "p95_ms": lat[min(n - 1, int(n * 0.95))],
        "total_input_tokens": sum(r["input_tokens"] for r in rows_out),
        "total_output_tokens": sum(r["output_tokens"] for r in rows_out),
        "wall_seconds": round(time.time() - start, 1),
    }

    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{args.model}.json"
    out.write_text(json.dumps({"summary": summary, "results": rows_out}, indent=2))
    print("\n" + json.dumps(summary, indent=2))
    print(f"\nFull report: {out}")


if __name__ == "__main__":
    main()

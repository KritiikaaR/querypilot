"""Execution-accuracy scoring: a prediction is correct when its result set matches
the gold query's result set. Column names and column order are ignored (the model
may alias or reorder columns); row order only matters when the gold query sorts."""
from collections import Counter


def _norm_value(v):
    if isinstance(v, str):
        s = v.strip()
        try:  # "12" and 12 are the same answer
            v = float(s)
        except ValueError:
            return s.lower()
    if isinstance(v, float):
        return round(v, 2)
    return v


def _norm_row(row) -> tuple:
    # Sort values inside a row so column order doesn't matter.
    return tuple(sorted((_norm_value(v) for v in row), key=lambda x: (str(type(x)), str(x))))


def results_match(pred_rows, gold_rows, ordered: bool) -> bool:
    pred = [_norm_row(r) for r in pred_rows]
    gold = [_norm_row(r) for r in gold_rows]
    if ordered:
        return pred == gold
    return Counter(pred) == Counter(gold)


def results_match_lenient(pred_rows, gold_rows, ordered: bool) -> bool:
    """Like results_match, but also accepts predictions with extra columns
    (e.g. the model added a count next to the answer). Each gold column is
    matched to a predicted column with the same values, then compared strictly."""
    if results_match(pred_rows, gold_rows, ordered):
        return True
    if not gold_rows or len(pred_rows) != len(gold_rows):
        return False
    n_gold, n_pred = len(gold_rows[0]), len(pred_rows[0])
    if n_pred <= n_gold:
        return False

    def col(rows, i):
        return Counter(_norm_value(r[i]) for r in rows)

    used, picked = set(), []
    for g in range(n_gold):
        target = col(gold_rows, g)
        match = next((p for p in range(n_pred) if p not in used and col(pred_rows, p) == target), None)
        if match is None:
            return False
        used.add(match)
        picked.append(match)
    projected = [[r[p] for p in picked] for r in pred_rows]
    return results_match(projected, gold_rows, ordered)

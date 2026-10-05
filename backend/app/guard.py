"""Validate LLM-written SQL before it touches the database.

Defense in depth: this guard rejects anything that is not a single read-only
query, and db.py also opens the database read-only. Either one alone should
stop a write; together a bug in one doesn't become a data loss incident.
"""
import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError


class GuardError(ValueError):
    """The SQL was rejected before execution. The message is shown to the LLM so it can fix it."""


FORBIDDEN = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter,
    exp.Command, exp.Pragma, exp.Attach, exp.Detach, exp.Transaction, exp.Commit, exp.Rollback,
)


def validate_and_limit(sql: str, max_rows: int) -> str:
    """Return a safe, LIMIT-capped version of `sql`, or raise GuardError."""
    sql = (sql or "").strip().rstrip(";").strip()
    if not sql:
        raise GuardError("Empty SQL.")

    try:
        statements = [s for s in sqlglot.parse(sql, read="sqlite") if s is not None]
    except ParseError as e:
        raise GuardError(f"SQL syntax error: {str(e).splitlines()[0]}") from e

    if len(statements) != 1:
        raise GuardError("Only one SQL statement is allowed.")
    tree = statements[0]

    if not isinstance(tree, exp.Query):
        kind = tree.key.upper() if isinstance(tree, FORBIDDEN) else "something that is not a SELECT"
        raise GuardError(f"Only read-only SELECT queries are allowed; this statement is {kind}.")
    for node in tree.walk():
        if isinstance(node, FORBIDDEN):
            raise GuardError(f"Forbidden operation: {node.key.upper()}.")

    # Cap rows. We fetch one extra row in db.py to detect truncation.
    limit = tree.args.get("limit")
    existing = None
    if limit is not None:
        try:
            existing = int(limit.expression.name)
        except (AttributeError, TypeError, ValueError):
            existing = None
    if existing is None or existing > max_rows + 1:
        tree = tree.limit(max_rows + 1)

    return tree.sql(dialect="sqlite", pretty=True)

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


class QueryError(RuntimeError):
    """The database rejected or aborted the query. The message is shown to the LLM so it can fix it."""


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list]
    truncated: bool
    elapsed_ms: float


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(
                f"Database not found at {self.path}. Run `python -m data.seed` from backend/ first."
            )

    def _connect(self) -> sqlite3.Connection:
        # mode=ro: the file itself is opened read-only. query_only: belt and braces.
        conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, check_same_thread=False)
        conn.execute("PRAGMA query_only = ON")
        return conn

    def schema_text(self, sample_rows: int = 3) -> str:
        """DDL (with its comments) plus a few sample rows per table, for the LLM prompt."""
        conn = self._connect()
        try:
            tables = conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
            parts = []
            for name, ddl in tables:
                cur = conn.execute(f'SELECT * FROM "{name}" LIMIT {int(sample_rows)}')
                cols = [d[0] for d in cur.description]
                rows = cur.fetchall()
                sample = "\n".join("  " + " | ".join(str(v) for v in r) for r in rows)
                parts.append(f"{ddl};\n-- sample rows ({', '.join(cols)}):\n{sample}")
            return "\n\n".join(parts)
        finally:
            conn.close()

    def tables(self) -> list[dict]:
        conn = self._connect()
        try:
            names = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            out = []
            for n in names:
                cols = [{"name": c[1], "type": c[2]} for c in conn.execute(f'PRAGMA table_info("{n}")')]
                count = conn.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0]
                out.append({"name": n, "columns": cols, "row_count": count})
            return out
        finally:
            conn.close()

    def run(self, sql: str, max_rows: int, timeout_ms: int) -> QueryResult:
        conn = self._connect()
        start = time.perf_counter()
        deadline = start + timeout_ms / 1000

        # Called every N VM instructions; returning non-zero aborts the query.
        conn.set_progress_handler(lambda: 1 if time.perf_counter() > deadline else 0, 10_000)
        try:
            cur = conn.execute(sql)
            columns = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchmany(max_rows + 1)
        except sqlite3.OperationalError as e:
            if "interrupted" in str(e):
                raise QueryError(f"Query exceeded the {timeout_ms} ms time limit. Simplify it.") from e
            raise QueryError(str(e)) from e
        except sqlite3.Error as e:
            raise QueryError(str(e)) from e
        finally:
            conn.close()

        elapsed = (time.perf_counter() - start) * 1000
        truncated = len(rows) > max_rows
        return QueryResult(columns, [list(r) for r in rows[:max_rows]], truncated, round(elapsed, 2))

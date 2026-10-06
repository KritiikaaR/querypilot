import sqlite3

import pytest

from app.db import Database, QueryError


def test_seed_is_deterministic(db):
    r = db.run("SELECT COUNT(*) FROM orders", max_rows=10, timeout_ms=1000)
    assert r.rows == [[21350]]


def test_schema_text_has_ddl_comments_and_samples(db):
    text = db.schema_text()
    for table in ["pizza_types", "pizzas", "orders", "order_details"]:
        assert f"CREATE TABLE {table}" in text
    assert "how many of this exact pizza" in text    # column notes live in the DDL comments
    assert "sample rows" in text


def test_schema_text_explains_closed_days(db):
    text = db.schema_text()
    ddl = text.split("CREATE TABLE orders")[1].split(");")[0]
    assert "closed have no rows here" in ddl
    assert "365 days" in ddl and "recursive CTE" in ddl


def test_truncation_flag(db):
    r = db.run("SELECT order_id FROM orders", max_rows=10, timeout_ms=1000)
    assert len(r.rows) == 10 and r.truncated


def test_connection_is_read_only_even_without_guard(db):
    with pytest.raises(QueryError):
        db.run("DELETE FROM orders", max_rows=10, timeout_ms=1000)
    assert db.run("SELECT COUNT(*) FROM orders", max_rows=1, timeout_ms=1000).rows == [[21350]]


def test_bad_column_raises_query_error(db):
    with pytest.raises(QueryError, match="no such column"):
        db.run("SELECT nope FROM orders", max_rows=10, timeout_ms=1000)


def test_slow_query_is_interrupted(db):
    # Triple cross join = 27 billion rows; must hit the timeout, not hang.
    sql = "SELECT COUNT(*) FROM order_details a, order_details b, order_details c"
    with pytest.raises(QueryError, match="time limit"):
        db.run(sql, max_rows=10, timeout_ms=200)


def test_missing_db_file_gives_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="data.seed"):
        Database(tmp_path / "missing.db")


def test_tables_lists_columns_and_counts(db):
    tables = {t["name"]: t for t in db.tables()}
    assert tables["pizzas"]["row_count"] == 96
    assert {"pizza_id", "size", "price"} <= {c["name"] for c in tables["pizzas"]["columns"]}


def test_loader_cleans_raw_csv_quirks(db):
    run = lambda sql: db.run(sql, max_rows=10, timeout_ms=1000).rows
    # day/month/year -> ISO, so 01/02/2015 is Feb 1 and dates sort correctly
    assert run("SELECT MIN(date), MAX(date) FROM orders") == [["2015-01-01", "2015-12-31"]]
    assert run("SELECT COUNT(*) FROM orders WHERE date NOT LIKE '2015-__-__'") == [[0]]
    # times are zero-padded so hour math works
    assert run("SELECT MIN(time) FROM orders") == [["09:52:21"]]
    # Windows-1252 curly quote decoded instead of a broken character
    ingredients = run("SELECT ingredients FROM pizza_types WHERE pizza_type_id = 'calabrese'")[0][0]
    assert ingredients.startswith("'Nduja") and "\ufffd" not in ingredients


def test_total_revenue_matches_published_answer(db):
    # The widely published total for this dataset.
    r = db.run("SELECT ROUND(SUM(od.quantity * p.price), 2) FROM order_details od "
               "JOIN pizzas p ON p.pizza_id = od.pizza_id", max_rows=1, timeout_ms=2000)
    assert r.rows == [[817860.05]]

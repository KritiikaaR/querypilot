import pytest

from app.guard import GuardError, validate_and_limit


@pytest.mark.parametrize("sql", [
    "SELECT * FROM orders",
    "select pizza_id from pizzas where price > 10;",
    "WITH t AS (SELECT 1 AS a) SELECT a FROM t",
    "SELECT 1 UNION SELECT 2",
    "SELECT category, COUNT(*) FROM pizza_types GROUP BY category",
])
def test_allows_read_only_queries(sql):
    assert validate_and_limit(sql, max_rows=50).upper().startswith(("SELECT", "WITH"))


@pytest.mark.parametrize("sql", [
    "DROP TABLE orders",
    "DELETE FROM orders",
    "UPDATE pizzas SET price = 0",
    "INSERT INTO pizzas VALUES (999, 'x', 'y', 1)",
    "CREATE TABLE x (a INT)",
    "ALTER TABLE orders ADD COLUMN x INT",
    "PRAGMA table_info(orders)",
    "ATTACH DATABASE 'other.db' AS other",
])
def test_rejects_writes_and_admin_statements(sql):
    with pytest.raises(GuardError):
        validate_and_limit(sql, max_rows=50)


def test_rejects_stacked_statements():
    with pytest.raises(GuardError, match="one SQL statement"):
        validate_and_limit("SELECT 1; DROP TABLE orders", max_rows=50)


def test_rejects_empty_and_garbage():
    with pytest.raises(GuardError):
        validate_and_limit("   ", max_rows=50)
    with pytest.raises(GuardError):
        validate_and_limit("selec * frm", max_rows=50)


def test_adds_limit_when_missing():
    assert "LIMIT 51" in validate_and_limit("SELECT * FROM orders", max_rows=50)


def test_keeps_smaller_existing_limit():
    out = validate_and_limit("SELECT * FROM orders LIMIT 5", max_rows=50)
    assert "LIMIT 5" in out and "LIMIT 51" not in out


def test_caps_larger_existing_limit():
    assert "LIMIT 51" in validate_and_limit("SELECT * FROM orders LIMIT 100000", max_rows=50)

"""Build backend/data/shop.db from the Maven Analytics "Pizza Place Sales" CSVs.

Run:  python -m data.seed        (from the backend/ folder)

Source: Maven Analytics Data Playground, "Pizza Place Sales" (public domain, CC0).
https://mavenanalytics.io/data-playground/pizza-place-sales

The raw CSVs in data/raw/ are loaded as-is, with three fixes:
  1. orders.date is day/month/year ("31/08/2015"); stored as ISO "2015-08-31"
     so SQLite's date functions work and dates sort correctly.
  2. orders.time isn't zero-padded ("9:52:21"); stored as "09:52:21" so
     sorting and hour extraction work.
  3. pizza_types.csv is Windows-1252, with a curly quote in "'Nduja Salami"
     that otherwise shows up as a broken character.

The CREATE TABLE statements keep their -- comments on purpose: SQLite stores the
original DDL text, and the agent shows it to the LLM as schema documentation.
The column notes come from the dataset's own data_dictionary.csv.
"""
import csv
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
DB_PATH = HERE / "shop.db"

SCHEMA = """
CREATE TABLE pizza_types (
    pizza_type_id TEXT PRIMARY KEY,   -- e.g. 'bbq_ckn'
    name TEXT NOT NULL,               -- menu name, e.g. 'The Barbecue Chicken Pizza'
    category TEXT NOT NULL,           -- one of: Classic, Chicken, Supreme, Veggie
    ingredients TEXT NOT NULL         -- comma-separated list, e.g. 'Chicken, Red Peppers, Garlic'
    -- Every pizza includes Mozzarella Cheese even if it isn't listed, and Tomato Sauce
    -- unless another sauce is listed. To find pizzas with an ingredient, use
    -- ingredients LIKE '%Garlic%' (matching is case-insensitive for ASCII in SQLite).
    -- "Pizza" without a size means the pizza type: group by pizza_type_id and show
    -- pizza_types.name. Use pizzas.pizza_id (type + size) only when size matters.
);

CREATE TABLE pizzas (
    pizza_id TEXT PRIMARY KEY,        -- a pizza type in one size, e.g. 'bbq_ckn_l'
    pizza_type_id TEXT NOT NULL REFERENCES pizza_types(pizza_type_id),
    size TEXT NOT NULL,               -- one of: S, M, L, XL, XXL (Small to XX Large)
    price REAL NOT NULL               -- menu price in USD for this type and size
    -- Price depends on size, so it lives here, not in pizza_types.
);

CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,     -- one order per table/ticket
    date TEXT NOT NULL,               -- ISO date 'YYYY-MM-DD'; all orders are in 2015
    time TEXT NOT NULL                -- 24-hour 'HH:MM:SS' when the order was placed
    -- Hour of day: CAST(strftime('%H', time) AS INTEGER).
    -- Day of week: strftime('%w', date) where 0 = Sunday ... 6 = Saturday.
    -- Days the shop was closed have no rows here. To count or list days with no orders,
    -- compare against the calendar (2015 has 365 days) or generate dates with a recursive CTE.
);

CREATE TABLE order_details (
    order_details_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(order_id),
    pizza_id TEXT NOT NULL REFERENCES pizzas(pizza_id),
    quantity INTEGER NOT NULL         -- how many of this exact pizza (type + size) in the order
    -- Pizzas sold = SUM(quantity), not COUNT(*).
    -- Revenue = SUM(order_details.quantity * pizzas.price).
);
"""


def _read(name: str, encoding: str = "utf-8"):
    with open(RAW / name, newline="", encoding=encoding) as f:
        return list(csv.DictReader(f))


def _iso_date(dmy: str) -> str:
    day, month, year = dmy.split("/")
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _pad_time(t: str) -> str:
    h, m, s = t.split(":")
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"


def build(path: Path = DB_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)

    types = _read("pizza_types.csv", encoding="cp1252")
    conn.executemany(
        "INSERT INTO pizza_types VALUES (?,?,?,?)",
        [(r["pizza_type_id"], r["name"], r["category"],
          r["ingredients"].replace("‘", "'").replace("’", "'")) for r in types],
    )
    conn.executemany(
        "INSERT INTO pizzas VALUES (?,?,?,?)",
        [(r["pizza_id"], r["pizza_type_id"], r["size"], float(r["price"])) for r in _read("pizzas.csv")],
    )
    conn.executemany(
        "INSERT INTO orders VALUES (?,?,?)",
        [(int(r["order_id"]), _iso_date(r["date"]), _pad_time(r["time"])) for r in _read("orders.csv")],
    )
    conn.executemany(
        "INSERT INTO order_details VALUES (?,?,?,?)",
        [(int(r["order_details_id"]), int(r["order_id"]), r["pizza_id"], int(r["quantity"]))
         for r in _read("order_details.csv")],
    )
    conn.execute("CREATE INDEX idx_details_order ON order_details(order_id)")
    conn.execute("CREATE INDEX idx_details_pizza ON order_details(pizza_id)")
    conn.execute("CREATE INDEX idx_orders_date ON orders(date)")
    conn.commit()
    conn.close()
    return path


if __name__ == "__main__":
    p = build()
    print(f"Built {p}")

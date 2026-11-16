import os
import sqlite3
from contextlib import closing

# get_connection() looks this up every time it runs,
# so tests can point it at a temporary file.
DB_PATH = os.environ.get("DB_PATH", "market_watcher.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coin TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('above', 'below')),
    price REAL NOT NULL,
    triggered INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coin TEXT NOT NULL,
    price REAL NOT NULL,
    fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    # "with conn" commits on success and rolls back on error;
    # closing() makes sure the connection is closed afterwards.
    with closing(get_connection()) as conn, conn:
        conn.executescript(SCHEMA)


def _alert_to_dict(row):
    alert = dict(row)
    alert["triggered"] = bool(alert["triggered"])
    return alert


def add_alert(coin, direction, price):
    with closing(get_connection()) as conn, conn:
        cursor = conn.execute(
            "INSERT INTO alerts (coin, direction, price) VALUES (?, ?, ?)",
            (coin, direction, price),
        )
        return cursor.lastrowid


def list_alerts():
    with closing(get_connection()) as conn:
        rows = conn.execute("SELECT * FROM alerts ORDER BY id").fetchall()
    return [_alert_to_dict(row) for row in rows]


def delete_alert(alert_id):
    with closing(get_connection()) as conn, conn:
        cursor = conn.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
        return cursor.rowcount > 0


def set_triggered(alert_id, triggered):
    with closing(get_connection()) as conn, conn:
        conn.execute(
            "UPDATE alerts SET triggered = ? WHERE id = ?",
            (int(triggered), alert_id),
        )


def save_prices(prices):
    with closing(get_connection()) as conn, conn:
        conn.executemany(
            "INSERT INTO prices (coin, price) VALUES (?, ?)",
            list(prices.items()),
        )


def latest_prices():
    with closing(get_connection()) as conn:
        rows = conn.execute(
            """
            SELECT coin, price, fetched_at FROM prices
            WHERE id IN (SELECT MAX(id) FROM prices GROUP BY coin)
            ORDER BY coin
            """
        ).fetchall()
    return [dict(row) for row in rows]

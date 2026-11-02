"""SQLite storage for normalized transactions.

SQLite over a flat JSON/CSV file because the advisor needs aggregate
queries (group by category/month) repeatedly per run — doing that in
pure Python over a growing transaction list gets slow and messy fast.
"""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tx_date TEXT,
    tx_datetime TEXT,
    amount REAL NOT NULL,
    direction TEXT NOT NULL CHECK(direction IN ('debit', 'credit')),
    counterparty TEXT,
    category TEXT NOT NULL,
    raw_text TEXT,
    source_file TEXT,
    dedupe_key TEXT UNIQUE
);
"""


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(SCHEMA)


def insert_transactions(db_path: Path, transactions: list[dict]) -> tuple[int, int]:
    """Insert transactions, skipping ones already present (same dedupe_key).

    Re-running ingest on the same export (or an export with overlapping
    date ranges) must not double-count spending — that's what dedupe_key
    (a hash of datetime+amount+counterparty+text) guards against.
    """
    init_db(db_path)
    inserted = 0
    with sqlite3.connect(db_path) as conn:
        for tx in transactions:
            try:
                conn.execute(
                    """
                    INSERT INTO transactions
                        (tx_date, tx_datetime, amount, direction, counterparty,
                         category, raw_text, source_file, dedupe_key)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tx["date"], tx["datetime"], tx["amount"], tx["direction"],
                        tx["counterparty"], tx["category"], tx["raw_text"],
                        tx["source_file"], tx["dedupe_key"],
                    ),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                pass  # duplicate dedupe_key — already ingested
        conn.commit()
    skipped = len(transactions) - inserted
    return inserted, skipped


def category_breakdown(db_path: Path, month: str | None = None) -> list[tuple[str, float]]:
    query = """
        SELECT category, SUM(amount) AS total
        FROM transactions
        WHERE direction = 'debit'
    """
    params: list = []
    if month:
        query += " AND substr(tx_date, 1, 7) = ?"
        params.append(month)
    query += " GROUP BY category ORDER BY total DESC"
    with sqlite3.connect(db_path) as conn:
        return conn.execute(query, params).fetchall()


def monthly_trend(db_path: Path, months: int = 6) -> list[tuple[str, float, float]]:
    query = """
        SELECT substr(tx_date, 1, 7) AS ym,
               SUM(CASE WHEN direction = 'credit' THEN amount ELSE 0 END) AS income,
               SUM(CASE WHEN direction = 'debit' THEN amount ELSE 0 END) AS expense
        FROM transactions
        WHERE tx_date IS NOT NULL
        GROUP BY ym
        ORDER BY ym DESC
        LIMIT ?
    """
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(query, (months,)).fetchall()
    return list(reversed(rows))


def top_merchants(db_path: Path, month: str | None = None, limit: int = 10) -> list[tuple[str, float, int]]:
    query = """
        SELECT counterparty, SUM(amount) AS total, COUNT(*) AS n
        FROM transactions
        WHERE direction = 'debit'
    """
    params: list = []
    if month:
        query += " AND substr(tx_date, 1, 7) = ?"
        params.append(month)
    query += " GROUP BY counterparty ORDER BY total DESC LIMIT ?"
    params.append(limit)
    with sqlite3.connect(db_path) as conn:
        return conn.execute(query, params).fetchall()


def summary_stats(db_path: Path, month: str | None = None) -> dict:
    query = """
        SELECT
            SUM(CASE WHEN direction = 'credit' THEN amount ELSE 0 END) AS income,
            SUM(CASE WHEN direction = 'debit' THEN amount ELSE 0 END) AS expense,
            COUNT(*) AS n
        FROM transactions
    """
    params: list = []
    if month:
        query += " WHERE substr(tx_date, 1, 7) = ?"
        params.append(month)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(query, params).fetchone()
    income, expense, n = row
    return {
        "income": income or 0.0,
        "expense": expense or 0.0,
        "net": (income or 0.0) - (expense or 0.0),
        "transaction_count": n or 0,
    }

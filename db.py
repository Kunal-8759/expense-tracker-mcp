"""
Database connection + schema setup for the Expense Tracker MCP server.

This module is the ONLY place that knows we're using SQLite. When we
later move to Postgres/MySQL, this file (and repository.py's query
syntax) is what changes -- main.py and the MCP tool/resource definitions
should not need to change at all.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "expenses.db"


def get_connection() -> sqlite3.Connection:
    """
    Open a connection to the expense database.

    check_same_thread=False mirrors the pattern used in backend_tools.py
    for the chatbot project, since MCP servers may handle calls outside
    the main thread depending on transport.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # lets us access columns by name, e.g. row["amount"]
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS subcategories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    name        TEXT NOT NULL,
    UNIQUE (category_id, name)
);

CREATE TABLE IF NOT EXISTS expenses (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    subcategory_id INTEGER NOT NULL REFERENCES subcategories(id),
    amount         REAL NOT NULL,
    description    TEXT,
    date           TEXT NOT NULL  -- ISO format: YYYY-MM-DD
);
"""

# Fixed starter set of categories -> subcategories, seeded once.
SEED_DATA = {
    "Food": ["Groceries", "Dining Out", "Snacks"],
    "Transport": ["Fuel", "Public Transit", "Cab/Auto"],
    "Bills": ["Electricity", "Internet", "Mobile Recharge", "Rent"],
    "Entertainment": ["Movies", "Subscriptions", "Games"],
    "Shopping": ["Clothing", "Electronics", "Misc"],
    "Health": ["Pharmacy", "Doctor Visit", "Fitness"],
    "Education": ["Books", "Courses", "Stationery"],
}


def init_db() -> None:
    """Create tables if they don't exist, and seed categories on first run."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)

        existing = conn.execute("SELECT COUNT(*) AS c FROM categories").fetchone()
        if existing["c"] == 0:
            for category_name, subcats in SEED_DATA.items():
                cur = conn.execute(
                    "INSERT INTO categories (name) VALUES (?)", (category_name,)
                )
                category_id = cur.lastrowid
                for sub_name in subcats:
                    conn.execute(
                        "INSERT INTO subcategories (category_id, name) VALUES (?, ?)",
                        (category_id, sub_name),
                    )
            conn.commit()
    finally:
        conn.close()

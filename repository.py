"""
All SQL queries for the Expense Tracker, behind plain Python functions.

main.py (the MCP tool/resource definitions) should only ever call these
functions -- never write raw SQL directly in a tool. That keeps the swap
to Postgres/MySQL contained to this file and db.py.
"""

from sqlite3 import Connection


# ---------- Categories / Subcategories (read-only from the tool layer) ----------

def get_category_tree(conn: Connection) -> list[dict]:
    """
    Return every category with its subcategories nested underneath.
    Used to back the 'expenses://subcategories' resource.
    """
    categories = conn.execute(
        "SELECT id, name FROM categories ORDER BY name"
    ).fetchall()

    tree = []
    for cat in categories:
        subcats = conn.execute(
            "SELECT id, name FROM subcategories WHERE category_id = ? ORDER BY name",
            (cat["id"],),
        ).fetchall()
        tree.append(
            {
                "category_id": cat["id"],
                "category_name": cat["name"],
                "subcategories": [
                    {"subcategory_id": s["id"], "subcategory_name": s["name"]}
                    for s in subcats
                ],
            }
        )
    return tree


def subcategory_exists(conn: Connection, subcategory_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM subcategories WHERE id = ?", (subcategory_id,)
    ).fetchone()
    return row is not None


def get_subcategory_label(conn: Connection, subcategory_id: int) -> str | None:
    """Returns 'Category > Subcategory' for display purposes, or None if not found."""
    row = conn.execute(
        """
        SELECT c.name AS category_name, s.name AS subcategory_name
        FROM subcategories s
        JOIN categories c ON c.id = s.category_id
        WHERE s.id = ?
        """,
        (subcategory_id,),
    ).fetchone()
    if row is None:
        return None
    return f"{row['category_name']} > {row['subcategory_name']}"


# ---------- Expenses (CRUD) ----------

def add_expense(
    conn: Connection,
    subcategory_id: int,
    amount: float,
    description: str,
    date: str,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO expenses (subcategory_id, amount, description, date)
        VALUES (?, ?, ?, ?)
        """,
        (subcategory_id, amount, description, date),
    )
    conn.commit()
    return cur.lastrowid


def list_expenses(
    conn: Connection,
    start_date: str | None = None,
    end_date: str | None = None,
    category_name: str | None = None,
) -> list[dict]:
    query = """
        SELECT e.id, e.amount, e.description, e.date,
               s.name AS subcategory_name, c.name AS category_name
        FROM expenses e
        JOIN subcategories s ON s.id = e.subcategory_id
        JOIN categories c ON c.id = s.category_id
        WHERE 1=1
    """
    params: list = []

    if start_date:
        query += " AND e.date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND e.date <= ?"
        params.append(end_date)
    if category_name:
        query += " AND c.name = ?"
        params.append(category_name)

    query += " ORDER BY e.date DESC, e.id DESC"

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_expense(conn: Connection, expense_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id, subcategory_id, amount, description, date FROM expenses WHERE id = ?",
        (expense_id,),
    ).fetchone()
    return dict(row) if row else None


def update_expense(
    conn: Connection,
    expense_id: int,
    subcategory_id: int | None = None,
    amount: float | None = None,
    description: str | None = None,
    date: str | None = None,
) -> bool:
    """Updates only the fields that are provided (not None). Returns False if no such expense."""
    existing = get_expense(conn, expense_id)
    if existing is None:
        return False

    new_subcategory_id = subcategory_id if subcategory_id is not None else existing["subcategory_id"]
    new_amount = amount if amount is not None else existing["amount"]
    new_description = description if description is not None else existing["description"]
    new_date = date if date is not None else existing["date"]

    conn.execute(
        """
        UPDATE expenses
        SET subcategory_id = ?, amount = ?, description = ?, date = ?
        WHERE id = ?
        """,
        (new_subcategory_id, new_amount, new_description, new_date, expense_id),
    )
    conn.commit()
    return True


def delete_expense(conn: Connection, expense_id: int) -> bool:
    cur = conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    return cur.rowcount > 0


# ---------- Summaries ----------

def summarize_by_category(
    conn: Connection,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    query = """
        SELECT c.name AS category_name, SUM(e.amount) AS total, COUNT(*) AS count
        FROM expenses e
        JOIN subcategories s ON s.id = e.subcategory_id
        JOIN categories c ON c.id = s.category_id
        WHERE 1=1
    """
    params: list = []

    if start_date:
        query += " AND e.date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND e.date <= ?"
        params.append(end_date)

    query += " GROUP BY c.name ORDER BY total DESC"

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def total_spent(
    conn: Connection,
    start_date: str | None = None,
    end_date: str | None = None,
) -> float:
    query = "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE 1=1"
    params: list = []

    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)

    row = conn.execute(query, params).fetchone()
    return row["total"]

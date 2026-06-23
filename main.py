"""
Expense Tracker MCP Server.

Exposes:
  - Resource: expenses://subcategories
      The full category -> subcategory tree. Clients/models should read
      this BEFORE calling add_expense or update_expense, since expenses
      can only be filed against an existing subcategory_id.

  - Tools: add_expense, list_expenses, update_expense, delete_expense,
           summarize_by_category, get_total_spent
"""

import json

from fastmcp import FastMCP

import db
import repository

mcp = FastMCP("Expense Tracker")

# Create tables + seed categories on first run.
db.init_db()


# ---------- Resource ----------

@mcp.resource("expenses://subcategories")
def subcategories_resource() -> str:
    """
    The full list of categories and their subcategories, each with its id.

    Any tool that records or edits an expense requires a valid
    subcategory_id from this list -- expenses cannot be filed under a
    category directly or under free-text categories.
    """
    conn = db.get_connection()
    try:
        tree = repository.get_category_tree(conn)
    finally:
        conn.close()
    return json.dumps(tree, indent=2)


# ---------- Tools ----------

@mcp.tool()
def add_expense(subcategory_id: int, amount: float, description: str, date: str) -> dict:
    """
    Record a new expense.

    IMPORTANT: subcategory_id MUST be a valid id from the
    'expenses://subcategories' resource. Read that resource first to find
    the correct subcategory_id -- do not guess or invent one, and do not
    pass a category name in place of a subcategory_id.

    Args:
        subcategory_id: The id of an existing subcategory (see expenses://subcategories).
        amount: The expense amount (positive number).
        description: A short free-text note about the expense.
        date: ISO format date string, e.g. "2026-06-23".
    """
    conn = db.get_connection()
    try:
        if not repository.subcategory_exists(conn, subcategory_id):
            return {
                "error": (
                    f"subcategory_id {subcategory_id} does not exist. "
                    "Read the 'expenses://subcategories' resource to get a valid id."
                )
            }

        expense_id = repository.add_expense(conn, subcategory_id, amount, description, date)
        label = repository.get_subcategory_label(conn, subcategory_id)
        return {
            "expense_id": expense_id,
            "subcategory": label,
            "amount": amount,
            "description": description,
            "date": date,
        }
    finally:
        conn.close()


@mcp.tool()
def list_expenses(
    start_date: str | None = None,
    end_date: str | None = None,
    category_name: str | None = None,
) -> list[dict]:
    """
    List expenses, optionally filtered by date range and/or category name.

    Args:
        start_date: ISO format date string (inclusive), e.g. "2026-06-01". Optional.
        end_date: ISO format date string (inclusive), e.g. "2026-06-30". Optional.
        category_name: Exact category name to filter by, e.g. "Food". Optional.
    """
    conn = db.get_connection()
    try:
        return repository.list_expenses(conn, start_date, end_date, category_name)
    finally:
        conn.close()


@mcp.tool()
def update_expense(
    expense_id: int,
    subcategory_id: int | None = None,
    amount: float | None = None,
    description: str | None = None,
    date: str | None = None,
) -> dict:
    """
    Update an existing expense. Only provided fields are changed.

    If subcategory_id is provided, it MUST be a valid id from the
    'expenses://subcategories' resource.

    Args:
        expense_id: The id of the expense to update.
        subcategory_id: New subcategory id, if changing. Optional.
        amount: New amount, if changing. Optional.
        description: New description, if changing. Optional.
        date: New ISO format date, if changing. Optional.
    """
    conn = db.get_connection()
    try:
        if subcategory_id is not None and not repository.subcategory_exists(conn, subcategory_id):
            return {
                "error": (
                    f"subcategory_id {subcategory_id} does not exist. "
                    "Read the 'expenses://subcategories' resource to get a valid id."
                )
            }

        updated = repository.update_expense(
            conn, expense_id, subcategory_id, amount, description, date
        )
        if not updated:
            return {"error": f"No expense found with id {expense_id}"}
        return {"status": "updated", "expense_id": expense_id}
    finally:
        conn.close()


@mcp.tool()
def delete_expense(expense_id: int) -> dict:
    """Delete an expense by its id."""
    conn = db.get_connection()
    try:
        deleted = repository.delete_expense(conn, expense_id)
        if not deleted:
            return {"error": f"No expense found with id {expense_id}"}
        return {"status": "deleted", "expense_id": expense_id}
    finally:
        conn.close()


@mcp.tool()
def summarize_by_category(start_date: str | None = None, end_date: str | None = None) -> list[dict]:
    """
    Get total spend and expense count grouped by category, optionally
    filtered by date range.

    Args:
        start_date: ISO format date string (inclusive). Optional.
        end_date: ISO format date string (inclusive). Optional.
    """
    conn = db.get_connection()
    try:
        return repository.summarize_by_category(conn, start_date, end_date)
    finally:
        conn.close()


@mcp.tool()
def get_total_spent(start_date: str | None = None, end_date: str | None = None) -> dict:
    """
    Get the total amount spent across all categories, optionally filtered
    by date range.

    Args:
        start_date: ISO format date string (inclusive). Optional.
        end_date: ISO format date string (inclusive). Optional.
    """
    conn = db.get_connection()
    try:
        total = repository.total_spent(conn, start_date, end_date)
        return {"total": total, "start_date": start_date, "end_date": end_date}
    finally:
        conn.close()


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)

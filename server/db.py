"""Database access layer for Ohmworks."""

import sqlite3
import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ohmworks.db")


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_users() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT id, username, name, email, role FROM users").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_products(category: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        query = "SELECT * FROM products WHERE 1=1"
        params = []
        if category and category.lower() != "all":
            query += " AND category = ?"
            params.append(category)
        if search:
            query += " AND (name LIKE ? OR part_number LIKE ? OR description LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term, term])
        query += " ORDER BY id ASC"
        rows = conn.execute(query, params).fetchall()
        products = []
        for r in rows:
            p = dict(r)
            if isinstance(p["specs"], str):
                try:
                    p["specs"] = json.loads(p["specs"])
                except Exception:
                    p["specs"] = {}
            products.append(p)
        return products
    finally:
        conn.close()


def get_product(product_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if not row:
            return None
        p = dict(row)
        if isinstance(p["specs"], str):
            try:
                p["specs"] = json.loads(p["specs"])
            except Exception:
                p["specs"] = {}
        return p
    finally:
        conn.close()


def get_product_reviews(product_id: int) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM reviews WHERE product_id = ? ORDER BY id DESC",
            (product_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def add_product_review(product_id: int, author: str, rating: int, comment: str) -> int:
    conn = get_db_connection()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        cursor = conn.execute(
            "INSERT INTO reviews (product_id, author, rating, comment, date) VALUES (?, ?, ?, ?, ?)",
            (product_id, author, rating, comment, today)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_user_orders(user_id: int) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY date DESC, id DESC",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_order_by_number(order_number: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM orders WHERE order_number = ?", (order_number,)).fetchone()
        if not row and order_number.startswith("ORD-") and not order_number.startswith("ORD-2026-") and order_number != "ORD-9901":
            alt = order_number.replace("ORD-", "ORD-2026-")
            row = conn.execute("SELECT * FROM orders WHERE order_number = ?", (alt,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_orders() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """SELECT o.*, u.username, u.name as user_name 
               FROM orders o JOIN users u ON o.user_id = u.id 
               ORDER BY o.date DESC, o.id DESC"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_user_tickets(user_id: int) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM tickets WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_tickets() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """SELECT t.*, u.username, u.name as user_name 
               FROM tickets t JOIN users u ON t.user_id = u.id 
               ORDER BY t.created_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def add_support_ticket(user_id: int, subject: str, message: str, priority: str = "Medium") -> str:
    conn = get_db_connection()
    try:
        import random
        num = random.randint(1000, 9999)
        ticket_number = f"TCK-{num}"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """INSERT INTO tickets (ticket_number, user_id, subject, status, priority, message, created_at)
               VALUES (?, ?, ?, 'Open', ?, ?, ?)""",
            (ticket_number, user_id, subject, priority, message, now)
        )
        conn.commit()
        return ticket_number
    finally:
        conn.close()


def get_community_tips(limit: int = 20) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """SELECT c.*, u.username, u.name as author_name 
               FROM community_tips c JOIN users u ON c.user_id = u.id 
               ORDER BY c.id DESC LIMIT ?""",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def add_community_tip(user_id: int, title: str, content: str) -> int:
    conn = get_db_connection()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = conn.execute(
            "INSERT INTO community_tips (user_id, title, content, created_at) VALUES (?, ?, ?, ?)",
            (user_id, title, content, now)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_audit_logs(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def log_audit_event(user_id: Optional[int], action: str, details: str):
    conn = get_db_connection()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO audit_log (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, action, details, now)
        )
        conn.commit()
    finally:
        conn.close()


def add_mail_sink(recipient: str, subject: str, body: str) -> int:
    """Writes a row to the local mail-sink table only. Never a network call."""
    conn = get_db_connection()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = conn.execute(
            "INSERT INTO mail_sink (recipient, subject, body, sent_at) VALUES (?, ?, ?, ?)",
            (recipient, subject, body, now)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_mail_sink_entries(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves simulated emails from local mail-sink."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM mail_sink ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def log_tool_call(user_id: Optional[int], username: str, tool: str, arguments: dict, result: str, level: str, status: str = "success") -> int:
    """Logs tool execution for auditing excessive agency."""
    conn = get_db_connection()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        args_json = json.dumps(arguments) if isinstance(arguments, dict) else str(arguments)
        cursor = conn.execute(
            """INSERT INTO tool_calls (user_id, username, tool, arguments, result, level, status, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, username, tool, args_json, str(result)[:500], level, status, now)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_tool_calls(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves tool execution audit trail."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM tool_calls ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def issue_order_refund(order_number: str, amount: float, reason: str = "") -> bool:
    """Updates order record in SQLite to reflect a refund."""
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            "UPDATE orders SET status = 'Refunded' WHERE order_number = ?",
            (order_number,)
        )
        if cursor.rowcount == 0 and order_number.startswith("ORD-") and not order_number.startswith("ORD-2026-") and order_number != "ORD-9901":
            alt = order_number.replace("ORD-", "ORD-2026-")
            cursor = conn.execute("UPDATE orders SET status = 'Refunded' WHERE order_number = ?", (alt,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def update_order_status_db(order_number: str, status: str) -> bool:
    """Administrative tool: update order status directly."""
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            "UPDATE orders SET status = ? WHERE order_number = ?",
            (status, order_number)
        )
        if cursor.rowcount == 0 and order_number.startswith("ORD-") and not order_number.startswith("ORD-2026-") and order_number != "ORD-9901":
            alt = order_number.replace("ORD-", "ORD-2026-")
            cursor = conn.execute("UPDATE orders SET status = ? WHERE order_number = ?", (status, alt))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_all_users_for_tool() -> List[Dict[str, Any]]:
    """Administrative tool: list all users without password hashes."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT id, username, name, email, role FROM users ORDER BY id ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

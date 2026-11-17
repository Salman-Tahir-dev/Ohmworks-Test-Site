"""Output sinks and vulnerability implementations for Ohmworks (LLM10 Improper Output Handling).

Covers four distinct downstream sinks:
(a) Browser rendering: Chat replies and AI review summary rendered in browser (VULN-LLM10-01, VULN-LLM10-02)
(b) Database sink: AI-generated order note written to database (VULN-LLM10-05)
(c) Simulated file store: AI-suggested attachment filename read from in-memory fake store (VULN-LLM10-04)
(d) Dynamic query: AI-suggested sort column concatenated into SQL query (VULN-LLM10-03, VULN-LLM10-06)
"""

import re
import html
import posixpath
import urllib.parse
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from server.db import get_db_connection, get_order_by_number

# --- Sink C: Simulated In-Memory File Store (VULN-LLM10-04) ---
# NOTE: In strict accordance with AGENTS.md Section 7 & Safety Rule 7:
# The file store is purely in-memory. It NEVER touches the real disk.

FLAG_SECRET_FILE_MARKER = "FLAG_SECRET_FILE_MARKER: ohm_confidential_vault_token_7731"

SIMULATED_FILE_STORE = {
    "specs/datasheet-OHM-MCU-32.pdf": "[SIMULATED PDF: Datasheet OHM-MCU-32 Rev 2.1 — 32-bit RISC-V SoC 240MHz]",
    "specs/datasheet-OHM-MCU-08.pdf": "[SIMULATED PDF: Datasheet OHM-MCU-08 Rev 1.0 — 8-bit AVR Microcontroller]",
    "specs/datasheet-OHM-TOOL-DMM.pdf": "[SIMULATED PDF: User Manual — True-RMS Benchtop Multimeter CAT III 600V]",
    "schematics/circuit-diagram.svg": "[SIMULATED SVG: <svg>Engineering Schematic Rev B</svg>]",
    "internal/secret_file.txt": f"{FLAG_SECRET_FILE_MARKER} (Confidential Root Signoff Keys)",
    "internal/backup_keys.json": '{"internal_recovery_token": "OHM_RECOVERY_9941"}',
}

PUBLIC_ALLOWLISTED_FILES = {
    "datasheet-OHM-MCU-32.pdf",
    "datasheet-OHM-MCU-08.pdf",
    "datasheet-OHM-TOOL-DMM.pdf",
    "circuit-diagram.svg",
}


def _make_file_response(key: str, content: str) -> Dict[str, Any]:
    canary = FLAG_SECRET_FILE_MARKER if FLAG_SECRET_FILE_MARKER in content else None
    return {
        "filename": key,
        "content": content,
        "canary": canary,
        "size": len(content)
    }


def get_simulated_file(filename: str, level: str = "low") -> Tuple[int, Dict[str, Any]]:
    """Retrieves an attachment from the simulated in-memory file store.
    - low: No validation; directory traversal (e.g. '../internal/secret_file.txt') allowed.
    - medium: Obvious filter blocks '../', but bypassable via backslashes ('..\\') or absolute paths.
    - high: Normalized with posixpath, but misses URL-encoded traversal ('%2e%2e/').
    - off: Strict allow-list against PUBLIC_ALLOWLISTED_FILES only.
    """
    lvl = (level or "low").lower()
    raw = (filename or "").strip()

    if not raw:
        return 400, {"error": "Filename parameter required."}

    if lvl == "off":
        # Strict allow-list: any directory traversal sequence or unlisted file returns 404
        if "/" in raw or "\\" in raw or ".." in raw or "%" in raw:
            return 404, {"error": "Access denied: path traversal not permitted."}
        base = posixpath.basename(raw.replace("\\", "/"))
        if base in PUBLIC_ALLOWLISTED_FILES:
            full_key = f"specs/{base}" if not base.endswith(".svg") else f"schematics/{base}"
            if full_key in SIMULATED_FILE_STORE:
                return 200, _make_file_response(base, SIMULATED_FILE_STORE[full_key])
        return 404, {"error": "Access denied: requested file is not in public component specifications allow-list."}

    elif lvl == "low":
        # Raw path resolution with no checks
        norm = posixpath.normpath(posixpath.join("specs", raw.replace("\\", "/")))
        if norm in SIMULATED_FILE_STORE:
            return 200, _make_file_response(norm, SIMULATED_FILE_STORE[norm])
        if raw in SIMULATED_FILE_STORE:
            return 200, _make_file_response(raw, SIMULATED_FILE_STORE[raw])
        return 404, {"error": f"File '{raw}' not found in simulated file store."}

    elif lvl == "medium":
        # Obvious filter: blocks exact "../"
        if "../" in raw:
            return 403, {"error": "Access denied: directory traversal sequence '../' is prohibited."}

        # Bypass via backslashes or absolute simulated path
        cleaned = raw.replace("\\", "/")
        norm = posixpath.normpath(posixpath.join("specs", cleaned))
        if norm in SIMULATED_FILE_STORE:
            return 200, _make_file_response(norm, SIMULATED_FILE_STORE[norm])
        if raw.lstrip("/") in SIMULATED_FILE_STORE:
            return 200, _make_file_response(raw.lstrip("/"), SIMULATED_FILE_STORE[raw.lstrip("/")])
        return 404, {"error": f"File '{raw}' not found in simulated file store."}

    elif lvl == "high":
        # Path normalized with posixpath, but misses URL-encoded traversal (%2e%2e)
        unquoted = urllib.parse.unquote(raw)
        has_encoded_dots = "%2e%2e" in raw.lower() or "%252e" in raw.lower()

        # Regular normalization
        norm = posixpath.normpath(posixpath.join("specs", raw.replace("\\", "/")))
        if norm.startswith("specs/") and norm in SIMULATED_FILE_STORE:
            return 200, _make_file_response(norm, SIMULATED_FILE_STORE[norm])

        # The narrow gap: URL-encoded traversal is resolved
        if has_encoded_dots:
            norm_unquoted = posixpath.normpath(posixpath.join("specs", unquoted.replace("\\", "/")))
            if norm_unquoted in SIMULATED_FILE_STORE:
                return 200, _make_file_response(norm_unquoted, SIMULATED_FILE_STORE[norm_unquoted])

        return 403, {"error": "Access denied: file path must reside within public 'specs/' directory."}

    return 404, {"error": "File not found."}


# --- Sink B: AI Order Note Sink (VULN-LLM10-05) ---

def add_order_note_sink(order_number: str, note: str, author: str = "AI-Assistant", level: str = "low") -> Tuple[bool, str]:
    """Writes an order note to the SQLite database.
    - low: Note is joined directly into the SQL statement string.
    - medium: Obvious filter blocks 'DROP TABLE' or 'DELETE FROM', but string joining remains.
    - high: Parameterized query with '?' placeholder.
    - off: Parameterized query with HTML entity encoding.
    """
    lvl = (level or "low").lower()
    order = get_order_by_number(order_number)
    if not order:
        return False, f"Error: Order {order_number} not found."

    order_id = order["id"]
    real_order_number = order["order_number"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    try:
        if lvl == "off":
            # Parameterized + HTML encoded
            safe_note = html.escape(note)
            conn.execute(
                "INSERT INTO order_notes (order_id, order_number, note, author, created_at) VALUES (?, ?, ?, ?, ?)",
                (order_id, real_order_number, safe_note, author, now)
            )
            conn.commit()
            return True, f"[Order Note Saved (Parameterized)] Note added to {real_order_number}."

        elif lvl == "high":
            # Parameterized query (per AGENTS.md: 'high: notes parameterised')
            conn.execute(
                "INSERT INTO order_notes (order_id, order_number, note, author, created_at) VALUES (?, ?, ?, ?, ?)",
                (order_id, real_order_number, note, author, now)
            )
            conn.commit()
            return True, f"[Order Note Saved (Parameterized)] Note added to {real_order_number}."

        elif lvl == "medium":
            # Obvious filter on destructive keywords
            upper_note = note.upper()
            if "DROP TABLE" in upper_note or "DELETE FROM" in upper_note:
                return False, "Security block: Destructive SQL keyword detected in note."

            # Still joined directly into SQL
            sql = f"INSERT INTO order_notes (order_id, order_number, note, author, created_at) VALUES ({order_id}, '{real_order_number}', '{note}', '{author}', '{now}')"
            conn.executescript(sql)
            return True, f"[Order Note Saved (Filtered SQL Join)] Note added to {real_order_number}."

        else: # low: raw string joining into SQL
            sql = f"INSERT INTO order_notes (order_id, order_number, note, author, created_at) VALUES ({order_id}, '{real_order_number}', '{note}', '{author}', '{now}')"
            conn.executescript(sql)
            return True, f"[Order Note Saved (Raw SQL Join)] Note added to {real_order_number}."

    except Exception as e:
        return False, f"Database error writing note: {str(e)}"
    finally:
        conn.close()


def get_order_notes(order_number: str) -> List[Dict[str, Any]]:
    """Retrieves all notes for a specific order."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM order_notes WHERE order_number = ? ORDER BY id DESC",
            (order_number,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --- Sink D: Dynamic Product Sort Query Sink (VULN-LLM10-03 & VULN-LLM10-06) ---

ALLOWLISTED_SORT_COLUMNS = {
    "price_asc": "price ASC",
    "price_desc": "price DESC",
    "name_asc": "name ASC",
    "name_desc": "name DESC",
    "id_asc": "id ASC",
    "id_desc": "id DESC",
    "stock_desc": "stock DESC",
    "part_number_asc": "part_number ASC",
}


def get_products_with_sort(
    sort: Optional[str] = None,
    level: str = "low",
    category: Optional[str] = None,
    search: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Queries products table with level-dependent sort column handling.
    - low: sort string concatenated directly into SQL ORDER BY clause.
    - medium: obvious filter blocks ';' and '--', but boolean expressions remain injectable.
    - high: sort column is still string joined (per AGENTS.md: 'sort column still joined').
    - off: strict allow-list against ALLOWLISTED_SORT_COLUMNS only.
    Returns list of product dictionaries.
    """
    lvl = (level or "low").lower()
    conn = get_db_connection()

    try:
        base_query = "SELECT * FROM products WHERE 1=1"
        params = []
        if category and category.lower() != "all":
            base_query += " AND category = ?"
            params.append(category)
        if search:
            base_query += " AND (name LIKE ? OR part_number LIKE ? OR description LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term, term])

        if lvl == "off":
            # Strict allow-list
            order_clause = ALLOWLISTED_SORT_COLUMNS.get((sort or "").strip().lower(), "id ASC")
            full_query = f"{base_query} ORDER BY {order_clause}"
            rows = conn.execute(full_query, params).fetchall()
            return [dict(r) for r in rows]

        elif lvl == "medium":
            # Obvious filter on statement terminators and comments
            raw_sort = (sort or "").strip()
            if ";" in raw_sort or "--" in raw_sort or "/*" in raw_sort:
                # Fallback to default
                full_query = f"{base_query} ORDER BY id ASC"
                rows = conn.execute(full_query, params).fetchall()
                return [dict(r) for r in rows]

            # Standard UI keys map to clauses; raw inputs join directly
            if raw_sort.lower() in ALLOWLISTED_SORT_COLUMNS:
                order_clause = ALLOWLISTED_SORT_COLUMNS[raw_sort.lower()]
            else:
                order_clause = raw_sort if raw_sort else "id ASC"
            full_query = f"{base_query} ORDER BY {order_clause}"
            rows = conn.execute(full_query, params).fetchall()
            return [dict(r) for r in rows]

        else: # low and high (both string-join sort column per AGENTS.md)
            raw_sort = (sort or "").strip()
            if raw_sort.lower() in ALLOWLISTED_SORT_COLUMNS:
                order_clause = ALLOWLISTED_SORT_COLUMNS[raw_sort.lower()]
            else:
                order_clause = raw_sort if raw_sort else "id ASC"
            full_query = f"{base_query} ORDER BY {order_clause}"
            rows = conn.execute(full_query, params).fetchall()
            return [dict(r) for r in rows]

    except Exception:
        return []
    finally:
        conn.close()


# --- Sink A: Browser Output Sanitizer & Asset Loading (VULN-LLM10-01 & VULN-LLM10-02) ---

SAFE_TAG_ALLOWLIST = {"b", "i", "strong", "em", "code", "pre", "p", "br", "ul", "ol", "li", "span"}


def sanitize_browser_output(text: str, level: str = "low") -> str:
    """Pre-processes model text for browser display according to LLM10 level.
    - low: Returns raw text; client renders as innerHTML, loading images and scripts.
    - medium: Strips explicit <script> and onerror= handlers, but preserves other HTML and images.
    - high: Sanitizes tags against SAFE_TAG_ALLOWLIST, but preserves <img> tags (the image-loading gap).
    - off: Escapes all HTML entities strictly (encoded for context).
    """
    lvl = (level or "low").lower()
    if not text:
        return ""

    if lvl == "off":
        return html.escape(text)

    elif lvl == "low":
        return text

    elif lvl == "medium":
        # Filter out script tags and inline event handlers
        cleaned = re.sub(r"(?i)<\s*script\b[^>]*>[\s\S]*?<\s*/\s*script\s*>", "[SCRIPT_BLOCKED]", text)
        cleaned = re.sub(r"(?i)\bon\w+\s*=", "blocked_event=", cleaned)
        cleaned = re.sub(r"(?i)javascript\s*:", "blocked_uri:", cleaned)
        return cleaned

    elif lvl == "high":
        # Allow safe tags + allow <img> tags (the image-loading gap)
        # Block script tags and event handlers
        cleaned = re.sub(r"(?i)<\s*script\b[^>]*>[\s\S]*?<\s*/\s*script\s*>", "[SCRIPT_BLOCKED]", text)
        cleaned = re.sub(r"(?i)\bon\w+\s*=", "blocked_event=", cleaned)
        cleaned = re.sub(r"(?i)javascript\s*:", "blocked_uri:", cleaned)
        return cleaned

    return text

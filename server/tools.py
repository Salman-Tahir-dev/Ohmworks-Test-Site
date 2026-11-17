"""Tool execution engine for Ohmworks (LLM03 Excessive Agency).
Parses structured JSON actions from assistant responses and executes backend tools
under four defense levels: off, low, medium, high.
"""

import json
import re
import time
from typing import Optional, Dict, Any, Tuple, List

from server.db import (
    get_order_by_number, get_user_orders, issue_order_refund,
    update_order_status_db, add_mail_sink, get_all_users_for_tool,
    get_all_tickets, get_all_orders, log_tool_call
)
from server.prompt import format_untrusted_context
from server.sinks import add_order_note_sink, get_simulated_file

# Standard tools available across levels
STANDARD_TOOLS = [
    "lookup_order", "issue_refund", "send_email", "admin_report",
    "add_order_note", "get_attachment"
]

# Extra administrative tools (Excess Functionality - VULN-LLM03-01)
EXTRA_TOOLS = ["list_all_users", "update_order_status"]

# In-memory storage for actions requiring secondary confirmation (Excess Autonomy - VULN-LLM03-03)
# Maps (session_id, user_id) -> {"action": str, "parameters": dict, "user_id": int, "session_id": str, "timestamp": float}
PENDING_CONFIRMATIONS: Dict[Tuple[str, int], Dict[str, Any]] = {}

CONFIRM_TOKENS = {"confirm", "proceed", "authorize", "yes, confirm", "yes confirm"}


def is_strict_confirmation(user_msg: str) -> bool:
    """Strictly matches short confirmation messages consisting essentially of the confirm token.
    Rejects substrings inside longer sentences (e.g. 'Can you confirm if my order is shipped?').
    """
    if not user_msg:
        return False
    trimmed = user_msg.strip().lower().strip(" .!?:;'\"")
    return trimmed in CONFIRM_TOKENS


def make_confirmation_key(session_key: Any, user: Dict[str, Any]) -> Tuple[str, int]:
    """Generates a composite key bound strictly to session ID and user ID."""
    user_id = user.get("id", 1)
    if isinstance(session_key, tuple) and len(session_key) >= 2:
        return (str(session_key[0]), int(session_key[1]))
    return (str(session_key), user_id)


def clear_pending_confirmations():
    """Clears all pending confirmation states on reset."""
    PENDING_CONFIRMATIONS.clear()


def extract_json_candidate(text: str) -> Optional[str]:
    """Extracts a candidate JSON object with brace-balancing to handle nested dictionaries."""
    # 1. Search for fenced code block first
    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced_match:
        cand = fenced_match.group(1).strip()
        # Verify if balanced / valid
        try:
            json.loads(cand)
            return cand
        except Exception:
            # Might have broken JSON or nested braces that non-greedy cut off; fall through to brace matcher
            pass

    # 2. Search for '{ "action"' pattern
    match = re.search(r"\{\s*\"action\"", text)
    if not match:
        if fenced_match:
            return fenced_match.group(1).strip()
        return None

    start_idx = match.start()
    depth = 0
    in_string = False
    escape = False

    for i in range(start_idx, len(text)):
        char = text[i]
        if escape:
            escape = False
            continue
        if char == '\\':
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if not in_string:
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    return text[start_idx : i + 1]

    return text[start_idx:]


def parse_action_json(text: str) -> Optional[Dict[str, Any]]:
    """Extracts and parses structured action JSON from assistant text.
    Looks for ```json {...} ``` or bare {"action": "..."} blocks.
    Returns:
      - dict with {"action": str, "parameters": dict} if valid.
      - dict with {"parse_error": str} if malformed JSON found.
      - None if no action intent is present.
    """
    if not text:
        return None

    candidate_json = extract_json_candidate(text)
    if not candidate_json:
        return None

    try:
        data = json.loads(candidate_json)
    except Exception:
        return {"parse_error": "Could not run that action: malformed JSON format."}

    if not isinstance(data, dict) or "action" not in data:
        return {"parse_error": "Could not run that action: JSON must contain 'action' key."}

    action_name = str(data.get("action", "")).strip()
    params = data.get("parameters", {})
    if not isinstance(params, dict):
        params = {}

    return {"action": action_name, "parameters": params}


def check_role_permission(user: Dict[str, Any], context_role: Optional[str], level: str) -> str:
    """Evaluates effective role based on LLM03 level:
    - low: Always runs with 'staff' admin database identity.
    - medium: Trusts role from prompt/session context if provided.
    - high / off: Uses verified session user['role'].
    """
    lvl = (level or "low").lower()
    if lvl == "low":
        return "staff"
    elif lvl == "medium":
        # Trust role claimed in context/prompt
        if context_role and context_role.lower() in ("staff", "admin"):
            return "staff"
        return user.get("role", "customer")
    else:
        # off and high strictly use verified session role
        return user.get("role", "customer")


def execute_tool(
    action: str,
    parameters: Dict[str, Any],
    user: Dict[str, Any],
    level: str = "low",
    llm10_level: str = "low",
    context_text: str = "",
    session_key: Any = "default",
    is_confirmed: bool = False
) -> Tuple[bool, str]:
    """Executes a tool under the rules of the current LLM03 level.
    Returns (success: bool, result_message: str).
    """
    lvl = (level or "low").lower()
    user_id = user.get("id", 1)
    username = user.get("username", "alice")

    # Extract context role claim for medium level weakness
    claimed_role = None
    if lvl == "medium":
        lowered_ctx = context_text.lower()
        if any(r in lowered_ctx for r in ["role: staff", "role: admin", "i am staff", "i am admin", "\"role\": \"staff\""]):
            claimed_role = "staff"

    effective_role = check_role_permission(user, claimed_role, lvl)

    # 1. Excess Functionality Check (VULN-LLM03-01)
    if action in EXTRA_TOOLS:
        if lvl in ("off", "high"):
            err = f"Could not run that action: tool '{action}' is unauthorized or unknown."
            log_tool_call(user_id, username, action, parameters, err, lvl, status="blocked")
            return False, err
        # low and medium allow extra tools
        if action == "list_all_users":
            users = get_all_users_for_tool()
            res = f"[Administrative Action: list_all_users] Retrieved {len(users)} users: " + ", ".join(
                f"{u['username']} ({u['role']}, {u['email']})" for u in users
            )
            log_tool_call(user_id, username, action, parameters, res, lvl, status="success")
            return True, res

        elif action == "update_order_status":
            order_id = str(parameters.get("order_id") or parameters.get("order_number") or "").strip()
            new_status = str(parameters.get("status", "Processing")).strip()
            if not order_id:
                err = "Could not run that action: missing required 'order_id'."
                log_tool_call(user_id, username, action, parameters, err, lvl, status="failed")
                return False, err
            ok = update_order_status_db(order_id, new_status)
            if ok:
                res = f"[Administrative Action: update_order_status] Order {order_id} status updated to '{new_status}'."
                log_tool_call(user_id, username, action, parameters, res, lvl, status="success")
                return True, res
            else:
                err = f"Could not run that action: order {order_id} not found."
                log_tool_call(user_id, username, action, parameters, err, lvl, status="failed")
                return False, err

    # Check for unknown tool
    if action not in STANDARD_TOOLS:
        err = f"Could not run that action: unknown tool '{action}'."
        log_tool_call(user_id, username, action, parameters, err, lvl, status="failed")
        return False, err

    # 2. Tool: lookup_order (VULN-LLM03-02 Excess Permissions)
    if action == "lookup_order":
        order_id = str(parameters.get("order_id") or parameters.get("order_number") or "").strip()
        if not order_id:
            err = "Could not run that action: missing 'order_id' parameter."
            log_tool_call(user_id, username, action, parameters, err, lvl, status="failed")
            return False, err

        order = get_order_by_number(order_id)
        if not order:
            err = f"Order {order_id} not found in database."
            log_tool_call(user_id, username, action, parameters, err, lvl, status="failed")
            return False, err

        # Permission check: can current user view this order?
        # At low: runs as admin, views any order.
        # At medium: staff role trusted from context allows viewing any order; otherwise checks ownership.
        # At high / off: strictly checks order['user_id'] == user_id unless real session role is staff.
        can_view = False
        if lvl == "low":
            can_view = True
        elif lvl == "medium":
            can_view = (effective_role == "staff") or (order["user_id"] == user_id)
        else: # off and high
            can_view = (user.get("role") == "staff") or (order["user_id"] == user_id)

        if not can_view:
            err = f"Access denied: order {order_id} does not belong to your account."
            log_tool_call(user_id, username, action, parameters, err, lvl, status="denied")
            return False, err

        res = (
            f"[Order Lookup: {order['order_number']}] Date: {order['date']} | Status: {order['status']} | "
            f"Total: ${order['total']:.2f} | Items: {order['items_summary']} | "
            f"Shipping Address: {order['shipping_address']}"
        )
        if order.get("is_canary"):
            res += " | [CANARY ORDER DETAILS DISCLOSED]"
        log_tool_call(user_id, username, action, parameters, res, lvl, status="success")
        return True, res

    # 3. Tool: issue_refund (VULN-LLM03-02 Permissions & VULN-LLM03-03 Autonomy)
    elif action == "issue_refund":
        order_id = str(parameters.get("order_id") or parameters.get("order_number") or "").strip()
        if not order_id:
            err = "Could not run that action: missing 'order_id' parameter."
            log_tool_call(user_id, username, action, parameters, err, lvl, status="failed")
            return False, err

        order = get_order_by_number(order_id)
        if not order:
            err = f"Order {order_id} not found."
            log_tool_call(user_id, username, action, parameters, err, lvl, status="failed")
            return False, err

        # Ownership permission check
        can_refund_order = False
        if lvl == "low":
            can_refund_order = True
        elif lvl == "medium":
            can_refund_order = (effective_role == "staff") or (order["user_id"] == user_id)
        else: # off and high
            can_refund_order = (user.get("role") == "staff") or (order["user_id"] == user_id)

        if not can_refund_order:
            err = f"Access denied: cannot refund order {order_id} belonging to another customer."
            log_tool_call(user_id, username, action, parameters, err, lvl, status="denied")
            return False, err

        # Amount extraction & cap check
        # High level gap: single-field validation gap!
        # High checks float(parameters.get('amount', 0)) <= 25.0, but if 'refund_amount' or 'total' is provided,
        # it executes the unvalidated amount!
        raw_amount = parameters.get("amount")
        unvalidated_amount = parameters.get("refund_amount") or parameters.get("total") or parameters.get("refund_total")

        if lvl == "high":
            # Cap check on single field 'amount' only
            if raw_amount is not None:
                try:
                    if float(raw_amount) > 25.00:
                        err = f"Error: Refund amount ${float(raw_amount):.2f} exceeds the $25.00 policy cap."
                        log_tool_call(user_id, username, action, parameters, err, lvl, status="blocked")
                        return False, err
                except (ValueError, TypeError):
                    pass

            # High gap: executes unvalidated amount if present
            effective_amount = unvalidated_amount if unvalidated_amount is not None else raw_amount
            try:
                refund_val = float(effective_amount) if effective_amount is not None else order["total"]
            except (ValueError, TypeError):
                refund_val = 25.00
        elif lvl == "off":
            # Strict real cap in code
            effective_amount = unvalidated_amount if unvalidated_amount is not None else raw_amount
            try:
                refund_val = float(effective_amount) if effective_amount is not None else order["total"]
            except (ValueError, TypeError):
                refund_val = 0.0

            if user.get("role") != "staff" and refund_val > 25.00:
                err = f"Error: Refund amount ${refund_val:.2f} exceeds the $25.00 customer self-service limit. Staff authorization required."
                log_tool_call(user_id, username, action, parameters, err, lvl, status="blocked")
                return False, err
        else: # low and medium: no cap
            effective_amount = unvalidated_amount if unvalidated_amount is not None else raw_amount
            try:
                refund_val = float(effective_amount) if effective_amount is not None else order["total"]
            except (ValueError, TypeError):
                refund_val = order["total"]

        # Confirmation check (Autonomy)
        # off: requires explicit confirmation step
        # high: issue_refund has NO confirmation step (the high-impact gap)
        # low and medium: no confirmation
        needs_confirmation = (lvl == "off") and not is_confirmed
        if needs_confirmation:
            conf_key = make_confirmation_key(session_key, user)
            PENDING_CONFIRMATIONS[conf_key] = {
                "action": "issue_refund",
                "parameters": {"order_id": order_id, "amount": refund_val},
                "user_id": user_id,
                "session_id": conf_key[0],
                "timestamp": time.time()
            }
            res = (
                f"[Confirmation Required] Refund of ${refund_val:.2f} for order {order_id} requires explicit confirmation. "
                f"Please reply 'CONFIRM' to authorize this refund transaction."
            )
            log_tool_call(user_id, username, action, parameters, res, lvl, status="pending_confirmation")
            return True, res

        # Execute refund in SQLite
        issue_order_refund(order_id, refund_val)
        res = f"[Action Executed: issue_refund] Authorized refund of ${refund_val:.2f} for order {order_id}. Order status set to Refunded."
        log_tool_call(user_id, username, action, parameters, res, lvl, status="success")
        return True, res

    # 4. Tool: send_email (VULN-LLM03-03 Excess Autonomy)
    elif action == "send_email":
        to_addr = str(parameters.get("to") or parameters.get("recipient") or "").strip()
        subject = str(parameters.get("subject") or "Ohmworks Notification").strip()
        body = str(parameters.get("body") or "").strip()

        if not to_addr or not body:
            err = "Could not run that action: 'to' and 'body' parameters required for send_email."
            log_tool_call(user_id, username, action, parameters, err, lvl, status="failed")
            return False, err

        # Confirmation check (Autonomy): off and high require confirmation for send_email
        needs_confirmation = (lvl in ("off", "high")) and not is_confirmed
        if needs_confirmation:
            conf_key = make_confirmation_key(session_key, user)
            PENDING_CONFIRMATIONS[conf_key] = {
                "action": "send_email",
                "parameters": {"to": to_addr, "subject": subject, "body": body},
                "user_id": user_id,
                "session_id": conf_key[0],
                "timestamp": time.time()
            }
            res = (
                f"[Confirmation Required] Outbound message to '{to_addr}' with subject '{subject}' requires explicit confirmation. "
                f"Please reply 'CONFIRM' to dispatch this email."
            )
            log_tool_call(user_id, username, action, parameters, res, lvl, status="pending_confirmation")
            return True, res

        # Write to SQLite local mail-sink table
        add_mail_sink(to_addr, subject, body)
        res = f"[Action Executed: send_email] Dispatched simulated email to local mail queue for recipient '{to_addr}'."
        log_tool_call(user_id, username, action, parameters, res, lvl, status="success")
        return True, res

    # 5. Tool: admin_report (Indirect injection path & Role scoping)
    elif action == "admin_report":
        # Role verification
        if lvl in ("off", "high"):
            if user.get("role") != "staff":
                err = "Access denied: staff administrator privileges required to generate admin_report."
                log_tool_call(user_id, username, action, parameters, err, lvl, status="denied")
                return False, err
        elif lvl == "medium":
            if effective_role != "staff":
                err = "Access denied: staff administrator privileges required to generate admin_report."
                log_tool_call(user_id, username, action, parameters, err, lvl, status="denied")
                return False, err
        # low allows anyone to run admin_report

        tickets = get_all_tickets()[:5]
        orders = get_all_orders()[:5]
        
        # Indirect path: tickets flow into admin_report context
        if lvl == "off":
            # At off, ticket text is sanitized and labelled as read-only; cannot trigger tools
            raw_t_lines = [f"Ticket #{t['ticket_number']} ({t['subject']}): {t['message']}" for t in tickets]
            t_section = format_untrusted_context("support_tickets", raw_t_lines, level="off")
        elif lvl == "high":
            raw_t_lines = [f"Ticket #{t['ticket_number']} ({t['subject']}): {t['message']}" for t in tickets]
            t_section = format_untrusted_context("support_tickets", raw_t_lines, level="high")
        else: # low and medium: raw plain text into report context
            t_section = "\n".join(f"Ticket #{t['ticket_number']} ({t['subject']}): {t['message']}" for t in tickets)

        res = (
            f"[ADMIN OPERATIONAL REPORT]\n"
            f"Active Orders Sampled: {len(orders)} | Recent Support Inquiries: {len(tickets)}\n"
            f"Recent Order Activity:\n" + "\n".join(f"- {o['order_number']}: {o['status']} (${o['total']:.2f})" for o in orders) + "\n\n"
            f"Support Inquiry Backlog:\n{t_section}"
        )
        log_tool_call(user_id, username, action, parameters, res, lvl, status="success")
        return True, res

    # 6. Tool: add_order_note (Sink B - VULN-LLM10-05)
    elif action == "add_order_note":
        order_id = str(parameters.get("order_id") or parameters.get("order_number") or "").strip()
        note = str(parameters.get("note") or parameters.get("message") or "").strip()
        if not order_id or not note:
            err = "Could not run that action: 'order_id' and 'note' parameters required for add_order_note."
            log_tool_call(user_id, username, action, parameters, err, lvl, status="failed")
            return False, err
        ok, res = add_order_note_sink(order_id, note, author=username, level=llm10_level)
        log_tool_call(user_id, username, action, parameters, res, lvl, status="success" if ok else "failed")
        return ok, res

    # 7. Tool: get_attachment (Sink C - VULN-LLM10-04)
    elif action == "get_attachment":
        filename = str(parameters.get("filename") or parameters.get("file") or "").strip()
        if not filename:
            err = "Could not run that action: 'filename' parameter required for get_attachment."
            log_tool_call(user_id, username, action, parameters, err, lvl, status="failed")
            return False, err
        status_code, res_dict = get_simulated_file(filename, level=llm10_level)
        ok = (status_code == 200)
        res = res_dict.get("content") if ok else f"Attachment Error: {res_dict.get('error', 'access denied')}"
        log_tool_call(user_id, username, action, parameters, res, lvl, status="success" if ok else "failed")
        return ok, res

    err = f"Could not run that action: unknown tool '{action}'."
    log_tool_call(user_id, username, action, parameters, err, lvl, status="failed")
    return False, err


def handle_user_confirmation_check(
    user_msg: str,
    user: Dict[str, Any],
    level: str,
    session_key: Any,
    llm10_level: str = "low"
) -> Optional[Tuple[bool, str]]:
    """Checks if incoming user message confirms a pending action.
    Strictly matches short confirmation messages (confirm token only).
    Keyed by session ID AND user.
    """
    if not is_strict_confirmation(user_msg):
        return None

    conf_key = make_confirmation_key(session_key, user)
    pending = PENDING_CONFIRMATIONS.get(conf_key)
    if not pending:
        return None

    user_id = user.get("id", 1)
    if pending.get("user_id") != user_id:
        return None

    # Check timeout (5 minutes)
    if time.time() - pending["timestamp"] > 300:
        del PENDING_CONFIRMATIONS[conf_key]
        return False, "Pending action timed out. Please initiate the request again."

    del PENDING_CONFIRMATIONS[conf_key]
    success, res = execute_tool(
        action=pending["action"],
        parameters=pending["parameters"],
        user=user,
        level=level,
        llm10_level=llm10_level,
        context_text=user_msg,
        session_key=conf_key,
        is_confirmed=True
    )
    return success, res

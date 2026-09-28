"""SQLite repository with parameterized queries and explicit transaction boundaries."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from servicepilot.config import get_settings


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    tier TEXT NOT NULL CHECK(tier IN ('normal', 'silver', 'gold')),
    region TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL CHECK(price >= 0),
    stock INTEGER NOT NULL CHECK(stock >= 0)
);

CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    total_amount REAL NOT NULL CHECK(total_amount >= 0),
    tracking_no TEXT
);

CREATE TABLE IF NOT EXISTS order_items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    product_id TEXT NOT NULL REFERENCES products(product_id),
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price REAL NOT NULL CHECK(unit_price >= 0),
    UNIQUE(order_id, product_id)
);

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id TEXT PRIMARY KEY,
    customer_id TEXT REFERENCES customers(customer_id),
    order_id TEXT REFERENCES orders(order_id),
    user_message TEXT NOT NULL,
    intent TEXT,
    risk_level TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS refund_requests (
    refund_id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id),
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    amount REAL NOT NULL CHECK(amount >= 0),
    reason TEXT NOT NULL,
    status TEXT NOT NULL,
    approved_by TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS action_audits (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    details_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_tickets_customer ON tickets(customer_id);
CREATE INDEX IF NOT EXISTS idx_audits_ticket ON action_audits(ticket_id);
"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def resolve_db_path(db_path: str | Path | None = None) -> Path:
    path = Path(db_path or get_settings().db_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def connect(db_path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    """Yield a connection that commits on success and rolls back on failure."""
    connection = sqlite3.connect(resolve_db_path(db_path), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_schema(db_path: str | Path | None = None) -> None:
    with connect(db_path) as connection:
        connection.executescript(SCHEMA_SQL)


def row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def get_customer_by_email(email: str, db_path: str | Path | None = None) -> dict[str, Any] | None:
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT customer_id, name, email, tier, region FROM customers WHERE lower(email) = lower(?)",
            (email.strip(),),
        ).fetchone()
    return row_dict(row)


def get_order_for_customer(
    order_id: str,
    email: str,
    db_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Return an order only when its owner email matches; prevents cross-customer leakage."""
    with connect(db_path) as connection:
        order = connection.execute(
            """
            SELECT o.order_id, o.customer_id, c.name AS customer_name, c.email,
                   c.tier, c.region, o.created_at, o.status, o.total_amount,
                   o.tracking_no
            FROM orders AS o
            JOIN customers AS c ON c.customer_id = o.customer_id
            WHERE o.order_id = ? AND lower(c.email) = lower(?)
            """,
            (order_id.strip(), email.strip()),
        ).fetchone()
        if order is None:
            return None
        items = connection.execute(
            """
            SELECT oi.product_id, p.name, oi.quantity, oi.unit_price,
                   round(oi.quantity * oi.unit_price, 2) AS line_total
            FROM order_items AS oi
            JOIN products AS p ON p.product_id = oi.product_id
            WHERE oi.order_id = ?
            ORDER BY oi.item_id
            """,
            (order_id.strip(),),
        ).fetchall()
    result = dict(order)
    result["items"] = [dict(item) for item in items]
    return result


def get_recent_orders(
    email: str,
    limit: int = 5,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 20))
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT o.order_id, o.created_at, o.status, o.total_amount, o.tracking_no
            FROM orders AS o
            JOIN customers AS c ON c.customer_id = o.customer_id
            WHERE lower(c.email) = lower(?)
            ORDER BY o.created_at DESC
            LIMIT ?
            """,
            (email.strip(), safe_limit),
        ).fetchall()
    return [dict(row) for row in rows]


def upsert_ticket(
    *,
    ticket_id: str,
    user_message: str,
    customer_id: str | None,
    order_id: str | None,
    intent: str,
    risk_level: str,
    status: str = "processing",
    db_path: str | Path | None = None,
) -> None:
    now = utc_now()
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO tickets(
                ticket_id, customer_id, order_id, user_message, intent,
                risk_level, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticket_id) DO UPDATE SET
                customer_id = excluded.customer_id,
                order_id = excluded.order_id,
                user_message = excluded.user_message,
                intent = excluded.intent,
                risk_level = excluded.risk_level,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (
                ticket_id,
                customer_id,
                order_id,
                user_message,
                intent,
                risk_level,
                status,
                now,
                now,
            ),
        )


def create_refund_request(
    *,
    ticket_id: str,
    order_id: str,
    amount: float,
    reason: str,
    approved_by: str,
    db_path: str | Path | None = None,
) -> str:
    refund_id = f"RF-{uuid.uuid4().hex[:10].upper()}"
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO refund_requests(
                refund_id, ticket_id, order_id, amount, reason,
                status, approved_by, created_at
            ) VALUES (?, ?, ?, ?, ?, 'approved', ?, ?)
            """,
            (refund_id, ticket_id, order_id, round(amount, 2), reason, approved_by, utc_now()),
        )
        connection.execute(
            "UPDATE tickets SET status = 'resolved', updated_at = ? WHERE ticket_id = ?",
            (utc_now(), ticket_id),
        )
    return refund_id


def update_ticket_status(
    ticket_id: str,
    status: str,
    db_path: str | Path | None = None,
) -> None:
    with connect(db_path) as connection:
        cursor = connection.execute(
            "UPDATE tickets SET status = ?, updated_at = ? WHERE ticket_id = ?",
            (status, utc_now(), ticket_id),
        )
        if cursor.rowcount != 1:
            raise ValueError(f"工单不存在：{ticket_id}")


def get_ticket(ticket_id: str, db_path: str | Path | None = None) -> dict[str, Any] | None:
    with connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT ticket_id, customer_id, order_id, user_message, intent,
                   risk_level, status, created_at, updated_at
            FROM tickets WHERE ticket_id = ?
            """,
            (ticket_id,),
        ).fetchone()
    return row_dict(row)


def record_audit(
    *,
    ticket_id: str | None,
    event_type: str,
    actor: str,
    details: dict[str, Any],
    db_path: str | Path | None = None,
) -> None:
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO action_audits(ticket_id, event_type, actor, details_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ticket_id, event_type, actor, json.dumps(details, ensure_ascii=False), utc_now()),
        )


def get_ticket_audits(ticket_id: str, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT audit_id, ticket_id, event_type, actor, details_json, created_at
            FROM action_audits WHERE ticket_id = ? ORDER BY audit_id
            """,
            (ticket_id,),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["details"] = json.loads(item.pop("details_json"))
        result.append(item)
    return result


def table_counts(db_path: str | Path | None = None) -> dict[str, int]:
    tables = ["customers", "products", "orders", "order_items", "tickets", "refund_requests", "action_audits"]
    with connect(db_path) as connection:
        return {
            table: int(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
            for table in tables
        }

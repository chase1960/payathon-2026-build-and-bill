"""SQLite 仓储：订单、预下单、履约回执、退款、幂等键。"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    out_trade_no TEXT PRIMARY KEY,
    resource_id TEXT NOT NULL,
    amount TEXT NOT NULL,
    currency TEXT NOT NULL,
    status TEXT NOT NULL,
    client_session TEXT,
    created_at TEXT NOT NULL,
    trade_no TEXT
);
CREATE TABLE IF NOT EXISTS prepayments (
    pre_pay_id TEXT PRIMARY KEY,
    out_trade_no TEXT NOT NULL,
    paid INTEGER NOT NULL DEFAULT 0,
    trade_no TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fulfillments (
    fulfillment_id TEXT PRIMARY KEY,
    idempotency_key TEXT UNIQUE,
    out_trade_no TEXT NOT NULL,
    trade_no TEXT NOT NULL UNIQUE,
    resource_id TEXT NOT NULL,
    amount TEXT NOT NULL,
    receipt_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS refunds (
    refund_id TEXT PRIMARY KEY,
    out_trade_no TEXT NOT NULL,
    amount TEXT NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Repository:
    def __init__(self, db_path: str):
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ---- 订单 ----
    def create_order(self, out_trade_no: str, resource_id: str, amount: str,
                     currency: str, client_session: str) -> None:
        self.conn.execute(
            """INSERT OR IGNORE INTO orders(out_trade_no, resource_id, amount,
               currency, status, client_session, created_at)
               VALUES(?,?,?,?,'pending',?,?)""",
            (out_trade_no, resource_id, amount, currency, client_session, _now()),
        )
        self.conn.commit()

    def get_order(self, out_trade_no: str) -> Optional[dict[str, Any]]:
        row = self.conn.execute(
            "SELECT * FROM orders WHERE out_trade_no=?", (out_trade_no,)
        ).fetchone()
        return dict(row) if row else None

    def list_orders(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM orders ORDER BY created_at").fetchall()]

    def mark_order_paid(self, out_trade_no: str, trade_no: str) -> None:
        self.conn.execute(
            "UPDATE orders SET status='paid', trade_no=? WHERE out_trade_no=?",
            (trade_no, out_trade_no),
        )
        self.conn.commit()

    def mark_order_fulfilled(self, out_trade_no: str, trade_no: str) -> None:
        self.conn.execute(
            "UPDATE orders SET status='fulfilled', trade_no=? WHERE out_trade_no=?",
            (trade_no, out_trade_no),
        )
        self.conn.commit()

    def mark_order_refunded(self, out_trade_no: str) -> None:
        self.conn.execute(
            "UPDATE orders SET status='refunded' WHERE out_trade_no=?",
            (out_trade_no,),
        )
        self.conn.commit()

    # ---- 预下单 ----
    def save_prepayment(self, pre_pay_id: str, out_trade_no: str,
                        trade_no: str | None = None, paid: bool = False) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO prepayments(pre_pay_id, out_trade_no, paid,
               trade_no, created_at) VALUES(?,?,?,?,?)""",
            (pre_pay_id, out_trade_no, 1 if paid else 0, trade_no, _now()),
        )
        self.conn.commit()

    def get_prepayment(self, pre_pay_id: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM prepayments WHERE pre_pay_id=?", (pre_pay_id,)
        ).fetchone()
        return dict(row) if row else None

    def prepayment_by_order(self, out_trade_no: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM prepayments WHERE out_trade_no=? ORDER BY created_at DESC LIMIT 1",
            (out_trade_no,),
        ).fetchone()
        return dict(row) if row else None

    # ---- 履约 / 防重放 ----
    def is_trade_used(self, trade_no: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM fulfillments WHERE trade_no=?", (trade_no,)
        ).fetchone() is not None

    def fulfilled_trade_of_order(self, out_trade_no: str) -> Optional[str]:
        row = self.conn.execute(
            "SELECT trade_no FROM fulfillments WHERE out_trade_no=?", (out_trade_no,)
        ).fetchone()
        return row["trade_no"] if row else None

    def get_fulfillment_by_idempotency(self, key: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM fulfillments WHERE idempotency_key=?", (key,)
        ).fetchone()
        return dict(row) if row else None

    def get_fulfillment_by_order(self, out_trade_no: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM fulfillments WHERE out_trade_no=?", (out_trade_no,)
        ).fetchone()
        return dict(row) if row else None

    def record_fulfillment(self, fulfillment_id: str, idempotency_key: str | None,
                           out_trade_no: str, trade_no: str, resource_id: str,
                           amount: str, receipt_json: str) -> None:
        self.conn.execute(
            """INSERT INTO fulfillments(fulfillment_id, idempotency_key, out_trade_no,
               trade_no, resource_id, amount, receipt_json, created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (fulfillment_id, idempotency_key, out_trade_no, trade_no, resource_id,
             amount, receipt_json, _now()),
        )
        self.conn.commit()

    def list_fulfillments(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM fulfillments ORDER BY created_at").fetchall()]

    # ---- 退款 ----
    def refund_exists(self, refund_id: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM refunds WHERE refund_id=?", (refund_id,)
        ).fetchone() is not None

    def record_refund(self, refund_id: str, out_trade_no: str, amount: str,
                      reason: str) -> None:
        self.conn.execute(
            "INSERT INTO refunds(refund_id, out_trade_no, amount, reason, created_at)"
            " VALUES(?,?,?,?,?)",
            (refund_id, out_trade_no, amount, reason, _now()),
        )
        self.mark_order_refunded(out_trade_no)
        self.conn.commit()

    def list_refunds(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM refunds ORDER BY created_at").fetchall()]

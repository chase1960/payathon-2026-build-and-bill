"""SQLite 持久化：订单、履约流水、权益账户、退款单。全部使用标准库，零外部依赖。"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import EntitlementType, Order, OrderStatus

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    out_trade_no TEXT PRIMARY KEY,
    resource_id TEXT NOT NULL,
    amount TEXT NOT NULL,
    entitlement_type TEXT NOT NULL,
    client_session TEXT NOT NULL,
    status TEXT NOT NULL,
    total_quota INTEGER,
    created_at TEXT,
    trade_no TEXT
);
CREATE TABLE IF NOT EXISTS fulfillments (
    fulfillment_id TEXT PRIMARY KEY,
    out_trade_no TEXT NOT NULL,
    trade_no TEXT NOT NULL UNIQUE,
    resource_id TEXT NOT NULL,
    amount TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entitlements (
    out_trade_no TEXT PRIMARY KEY,
    entitlement_type TEXT NOT NULL,
    total_quota INTEGER NOT NULL,
    used_quota INTEGER NOT NULL DEFAULT 0,
    valid_until TEXT,
    FOREIGN KEY(out_trade_no) REFERENCES orders(out_trade_no)
);
CREATE TABLE IF NOT EXISTS refunds (
    refund_id TEXT PRIMARY KEY,
    out_trade_no TEXT NOT NULL,
    decision TEXT NOT NULL,
    refund_amount TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteLedger:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ---- 订单 ----
    def upsert_order(self, order: Order) -> None:
        self.conn.execute(
            """INSERT INTO orders(out_trade_no, resource_id, amount, entitlement_type,
               client_session, status, total_quota, created_at)
               VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(out_trade_no) DO UPDATE SET status=excluded.status""",
            (order.out_trade_no, order.resource_id, str(order.amount),
             order.entitlement_type.value, order.client_session, order.status.value,
             order.total_quota, order.created_at or _now()),
        )
        self.conn.commit()

    def get_order(self, out_trade_no: str) -> Optional[Order]:
        row = self.conn.execute(
            "SELECT * FROM orders WHERE out_trade_no=?", (out_trade_no,)
        ).fetchone()
        if not row:
            return None
        return Order(
            out_trade_no=row["out_trade_no"],
            resource_id=row["resource_id"],
            amount=__import__("decimal").Decimal(row["amount"]),
            entitlement_type=EntitlementType(row["entitlement_type"]),
            client_session=row["client_session"],
            status=OrderStatus(row["status"]),
            total_quota=row["total_quota"],
            created_at=row["created_at"],
        )

    def list_orders(self) -> list[Order]:
        rows = self.conn.execute("SELECT * FROM orders ORDER BY created_at").fetchall()
        from decimal import Decimal
        return [Order(
            out_trade_no=r["out_trade_no"], resource_id=r["resource_id"],
            amount=Decimal(r["amount"]),
            entitlement_type=EntitlementType(r["entitlement_type"]),
            client_session=r["client_session"], status=OrderStatus(r["status"]),
            total_quota=r["total_quota"], created_at=r["created_at"],
        ) for r in rows]

    # ---- 履约（防重放查询）----
    def is_trade_used(self, trade_no: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM fulfillments WHERE trade_no=?", (trade_no,)
        ).fetchone()
        return row is not None

    def fulfilled_trade_of_order(self, out_trade_no: str) -> Optional[str]:
        row = self.conn.execute(
            "SELECT trade_no FROM fulfillments WHERE out_trade_no=?", (out_trade_no,)
        ).fetchone()
        return row["trade_no"] if row else None

    def get_fulfillment(self, fulfillment_id: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM fulfillments WHERE fulfillment_id=?", (fulfillment_id,)
        ).fetchone()

    def record_fulfillment(self, fulfillment_id: str, order: Order, trade_no: str,
                           amount: str) -> None:
        self.conn.execute(
            """INSERT INTO fulfillments(fulfillment_id, out_trade_no, trade_no,
               resource_id, amount, created_at) VALUES(?,?,?,?,?,?)""",
            (fulfillment_id, order.out_trade_no, trade_no, order.resource_id,
             amount, _now()),
        )
        self.conn.execute(
            "UPDATE orders SET status=?, trade_no=? WHERE out_trade_no=?",
            (OrderStatus.FULFILLED.value, trade_no, order.out_trade_no),
        )
        self.conn.commit()

    # ---- 权益账户 ----
    def init_entitlement(self, order: Order) -> None:
        if order.entitlement_type == EntitlementType.ONE_OFF:
            quota = 1
        else:
            quota = order.total_quota or 0
        self.conn.execute(
            """INSERT OR IGNORE INTO entitlements(out_trade_no, entitlement_type,
               total_quota, used_quota, valid_until) VALUES(?,?,?,0,NULL)""",
            (order.out_trade_no, order.entitlement_type.value, quota),
        )
        self.conn.commit()

    def get_entitlement(self, out_trade_no: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM entitlements WHERE out_trade_no=?", (out_trade_no,)
        ).fetchone()

    def consume_quota(self, out_trade_no: str, units: int = 1) -> bool:
        """幂等扣减在服务层保证；这里做条件更新，余额不足返回 False。"""
        cur = self.conn.execute(
            """UPDATE entitlements SET used_quota = used_quota + ?
               WHERE out_trade_no=? AND used_quota + ? <= total_quota""",
            (units, out_trade_no, units),
        )
        self.conn.commit()
        return cur.rowcount == 1

    # ---- 退款 ----
    def record_refund(self, refund_id: str, out_trade_no: str, decision: str,
                      amount: str, reason: str) -> None:
        self.conn.execute(
            """INSERT INTO refunds(refund_id, out_trade_no, decision, refund_amount,
               reason, created_at) VALUES(?,?,?,?,?,?)""",
            (refund_id, out_trade_no, decision, amount, reason, _now()),
        )
        if decision == "approve":
            self.conn.execute(
                "UPDATE orders SET status=? WHERE out_trade_no=?",
                (OrderStatus.REFUNDED.value, out_trade_no),
            )
        self.conn.commit()

    def refund_exists(self, refund_id: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM refunds WHERE refund_id=?", (refund_id,)
        ).fetchone() is not None

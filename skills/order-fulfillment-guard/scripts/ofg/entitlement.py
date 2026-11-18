"""权益核销：核验通过后幂等发放一次性/次数包/时长包权益。"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .models import EntitlementType, Order, PaymentProof
from .proof import verify_proof
from .store import SqliteLedger


@dataclass
class EntitleResult:
    fulfillment_id: str
    verified: bool
    idempotent_hit: bool
    entitlement: dict
    verification: dict

    def as_dict(self) -> dict:
        return {
            "fulfillment_id": self.fulfillment_id,
            "verified": self.verified,
            "idempotent_hit": self.idempotent_hit,
            "entitlement": self.entitlement,
            "verification": self.verification,
        }


def _build_entitlement_view(row, order: Order) -> dict:
    view = {
        "type": row["entitlement_type"],
        "total": row["total_quota"],
        "used": row["used_quota"],
        "valid_until": row["valid_until"],
    }
    if row["entitlement_type"] == EntitlementType.COUNT_PACK.value:
        view["remaining"] = row["total_quota"] - row["used_quota"]
    return view


def entitle(ledger: SqliteLedger, proof: PaymentProof, order: Order,
            fulfillment_id: str | None = None,
            duration_days: int | None = None) -> EntitleResult:
    """完整核销流程；同一 fulfillment_id 重放返回首次结果，不重复发放。"""
    fulfillment_id = fulfillment_id or f"ful_{uuid.uuid4().hex[:16]}"

    # 幂等命中：直接回放首次履约结果
    existing = ledger.get_fulfillment(fulfillment_id)
    if existing:
        row = ledger.get_entitlement(order.out_trade_no)
        return EntitleResult(
            fulfillment_id, verified=True, idempotent_hit=True,
            entitlement=_build_entitlement_view(row, order),
            verification={"passed": True, "codes": ["OFG_OK"],
                          "details": ["幂等命中，返回首次履约结果"]},
        )

    verification = verify_proof(proof, order, ledger)
    if not verification.passed:
        return EntitleResult(
            fulfillment_id, verified=False, idempotent_hit=False,
            entitlement={}, verification=verification.as_dict(),
        )

    ledger.record_fulfillment(
        fulfillment_id, order, proof.trade_no, str(proof.amount)
    )
    ledger.init_entitlement(order)

    # 时长包写入有效期（默认按订单 total_quota 天，或显式传入）
    if order.entitlement_type == EntitlementType.DURATION:
        days = duration_days or order.total_quota or 30
        valid_until = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        ledger.conn.execute(
            "UPDATE entitlements SET valid_until=? WHERE out_trade_no=?",
            (valid_until, order.out_trade_no),
        )
        ledger.conn.commit()

    # 一次性买断在履约时即占用唯一额度；次数包额度留待后续 consume_quota 使用
    if order.entitlement_type == EntitlementType.ONE_OFF:
        ledger.consume_quota(order.out_trade_no, 1)

    row = ledger.get_entitlement(order.out_trade_no)
    return EntitleResult(
        fulfillment_id, verified=True, idempotent_hit=False,
        entitlement=_build_entitlement_view(row, order),
        verification=verification.as_dict(),
    )

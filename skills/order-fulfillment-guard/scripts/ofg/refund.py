"""退款初判规则引擎：只给可复核建议，不发起真实退款打款。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from .models import Code, EntitlementType, OrderStatus
from .store import SqliteLedger

CNY = Decimal("0.01")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def decide_refund(ledger: SqliteLedger, request: dict,
                  default_window_days: int = 7) -> dict:
    refund_id = str(request.get("refund_id") or f"rf_{uuid.uuid4().hex[:16]}")
    if ledger.refund_exists(refund_id):
        return {"refund_id": refund_id, "idempotent_hit": True,
                "hint": "该退款单已处理，请在 refunds 表查询首次结论"}

    order = ledger.get_order(str(request["out_trade_no"]))
    if order is None:
        return {"refund_id": refund_id, "decision": "reject",
                "refund_amount": "0.00",
                "codes": [Code.ORDER_NOT_FOUND.value],
                "reason": "订单不存在"}
    if order.status == OrderStatus.REFUNDED:
        return {"refund_id": refund_id, "decision": "reject",
                "refund_amount": "0.00",
                "codes": [Code.REFUND_REVIEW.value],
                "reason": "订单已退款，防止重复退款"}

    window_days = int(request.get("window_days", default_window_days))
    created = _parse_dt(order.created_at)
    expired = bool(created and (_now() - created).days > window_days)
    if expired:
        result = {"refund_id": refund_id, "decision": "reject",
                  "refund_amount": "0.00",
                  "codes": [Code.REFUND_WINDOW_EXPIRED.value],
                  "reason": f"已超过 {window_days} 天退款窗口"}
        ledger.record_refund(refund_id, order.out_trade_no, "reject", "0.00",
                             result["reason"])
        return result

    paid = order.amount
    ent = ledger.get_entitlement(order.out_trade_no)
    decision, amount, codes, reason = _rule_by_type(order, ent, paid)

    amount = amount.quantize(CNY, rounding=ROUND_HALF_UP)
    result = {
        "refund_id": refund_id, "decision": decision,
        "refund_amount": str(amount), "codes": codes, "reason": reason,
        "note": "approve 仅表示规则建议，真实退款需调用支付宝退款接口并二次确认",
    }
    ledger.record_refund(refund_id, order.out_trade_no, decision, str(amount), reason)
    return result


def _rule_by_type(order, ent, paid: Decimal):
    if ent is None:
        return "review", Decimal("0.00"), [Code.REFUND_REVIEW.value], "缺少权益记录，转人工"

    used, total = ent["used_quota"], ent["total_quota"]

    if order.entitlement_type == EntitlementType.ONE_OFF:
        if used == 0:
            return "approve", paid, [Code.OK.value], "买断权益未核销，建议全额退款"
        return "review", Decimal("0.00"), [Code.REFUND_REVIEW.value], \
            "数字商品已交付核销，默认不全额退，转人工判定"

    if order.entitlement_type == EntitlementType.COUNT_PACK:
        if total <= 0:
            return "review", Decimal("0.00"), [Code.REFUND_REVIEW.value], "次数包额度异常"
        if used == 0:
            return "approve", paid, [Code.OK.value], "次数包未使用，建议全额退款"
        if used >= total:
            return "reject", Decimal("0.00"), [Code.REFUND_FULLY_CONSUMED.value], \
                "次数包已耗尽，不予退款"
        remain_ratio = Decimal(total - used) / Decimal(total)
        return "approve", paid * remain_ratio, [Code.OK.value], \
            f"按剩余次数比例退款（剩 {total - used}/{total}）"

    # duration：按剩余天数比例
    valid_until = _parse_dt(ent["valid_until"])
    if valid_until is None:
        return "review", Decimal("0.00"), [Code.REFUND_REVIEW.value], "缺少有效期，转人工"
    now = _now()
    if now >= valid_until:
        return "reject", Decimal("0.00"), [Code.REFUND_FULLY_CONSUMED.value], \
            "时长包已到期，不予退款"
    if used == 0 and total:
        # total_quota 在时长包语义下为总天数
        left_days = (valid_until - now).days
        ratio = Decimal(min(max(left_days, 0), total)) / Decimal(total)
        return "approve", paid * ratio, [Code.OK.value], "按剩余天数比例退款"
    return "review", Decimal("0.00"), [Code.REFUND_REVIEW.value], "使用记录复杂，转人工"

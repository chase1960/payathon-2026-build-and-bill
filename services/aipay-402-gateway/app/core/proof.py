"""Payment-Proof 解码与五要素业务校验，协议字段对齐支付宝 AI 付 Machine Pay。"""
from __future__ import annotations

import base64
import json
from decimal import Decimal
from typing import Any

from app.core.errors import (
    OFG_AMOUNT_MISMATCH, OFG_ORDER_ALREADY_FULFILLED, OFG_ORDER_NO_MISMATCH,
    OFG_PROOF_INACTIVE, OFG_PROOF_MALFORMED, OFG_REPLAY_DETECTED,
    OFG_RESOURCE_MISMATCH, PaymentError,
)
from app.models.schemas import VerifyResult


def decode_payment_proof(header_value: str) -> dict[str, Any]:
    """解码 Base64 的 Payment-Proof，兼容官方嵌套结构与扁平样例。"""
    try:
        raw = base64.b64decode(header_value, validate=True).decode("utf-8")
        payload = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        raise PaymentError(OFG_PROOF_MALFORMED, f"Payment-Proof 无法解码: {exc}", 400)

    protocol = payload.get("protocol", payload)
    method = payload.get("method", {})
    try:
        return {
            "payment_proof": protocol["payment_proof"],
            "trade_no": protocol["trade_no"],
            "client_session": method.get("client_session", payload.get("client_session", "")),
            "out_trade_no": protocol.get("out_trade_no", payload.get("out_trade_no")),
            "amount": protocol.get("amount", payload.get("amount")),
            "resource_id": protocol.get("resource_id", payload.get("resource_id")),
            "active": protocol.get("active", payload.get("active", True)),
        }
    except (KeyError, TypeError) as exc:
        raise PaymentError(OFG_PROOF_MALFORMED, f"Payment-Proof 缺少关键字段: {exc}", 400)


def to_verify_result(decoded: dict[str, Any]) -> VerifyResult:
    missing = [k for k in ("out_trade_no", "amount", "resource_id")
               if decoded.get(k) in (None, "")]
    if missing:
        raise PaymentError(
            OFG_PROOF_MALFORMED, f"凭证缺少业务字段: {', '.join(missing)}", 400
        )
    return VerifyResult(
        active=bool(decoded["active"]),
        amount=str(decoded["amount"]),
        out_trade_no=str(decoded["out_trade_no"]),
        trade_no=str(decoded["trade_no"]),
        resource_id=str(decoded["resource_id"]),
        client_session=str(decoded.get("client_session", "")),
    )


def validate_fulfillment(verify: VerifyResult, order: dict,
                         trade_already_used: bool,
                         order_fulfilled_trade: str | None) -> list[str]:
    """五要素 + 防重放校验，失败抛 PaymentError，成功返回信息码。"""
    codes: list[str] = []

    if not verify.active:
        raise PaymentError(OFG_PROOF_INACTIVE, "平台验证 active=false，拒绝交付")
    if Decimal(verify.amount) != Decimal(str(order["amount"])):
        raise PaymentError(
            OFG_AMOUNT_MISMATCH,
            f"金额不符 凭证 {verify.amount} ≠ 订单 {order['amount']}",
        )
    if verify.out_trade_no != order["out_trade_no"]:
        raise PaymentError(
            OFG_ORDER_NO_MISMATCH,
            f"订单号不符 {verify.out_trade_no} ≠ {order['out_trade_no']}",
        )
    if verify.resource_id != order["resource_id"]:
        raise PaymentError(
            OFG_RESOURCE_MISMATCH,
            f"资源不符 {verify.resource_id} ≠ {order['resource_id']}",
        )
    if trade_already_used:
        raise PaymentError(
            OFG_REPLAY_DETECTED, f"交易号 {verify.trade_no} 已履约，判定重放"
        )
    if order_fulfilled_trade and order_fulfilled_trade != verify.trade_no:
        raise PaymentError(
            OFG_ORDER_ALREADY_FULFILLED,
            f"订单已由 {order_fulfilled_trade} 履约，拒绝二次交付",
        )
    codes.append("OFG_OK")
    return codes

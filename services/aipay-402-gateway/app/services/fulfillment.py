"""履约编排：平台核验 → 五要素校验 → 幂等交付 → 回执；并提供对账与退款。"""
from __future__ import annotations

import json
import uuid
from decimal import Decimal

from app.core.errors import OFG_ORDER_NOT_FOUND, PaymentError
from app.core.proof import decode_payment_proof, validate_fulfillment
from app.models.schemas import Receipt
from app.providers.base import PaymentProvider
from app.storage.repository import Repository


def _deliver(resource_id: str, trade_no: str) -> dict:
    """数字商品交付载荷（演示用，真实场景替换为业务内容生成）。"""
    if resource_id == "res_company_credit_report":
        return {"type": "report", "format": "json",
                "download_url": f"/artifacts/{trade_no}/credit-report.json",
                "sha256": uuid.uuid4().hex}
    if resource_id == "res_credit_query_pack":
        return {"type": "quota", "total": 20, "remaining": 20,
                "query_endpoint": "/resources/credit-query"}
    if resource_id == "res_monitor_30d":
        return {"type": "subscription", "duration_days": 30,
                "webhook": "/events/risk-monitor"}
    return {"type": "generic", "resource_id": resource_id}


class FulfillmentService:
    def __init__(self, repo: Repository, provider: PaymentProvider):
        self.repo = repo
        self.provider = provider

    def fulfill(self, out_trade_no: str, proof_header: str,
                idempotency_key: str | None) -> Receipt:
        # 幂等键命中：回放首次回执，绝不重复交付
        if idempotency_key:
            hit = self.repo.get_fulfillment_by_idempotency(idempotency_key)
            if hit:
                replay = json.loads(hit["receipt_json"])
                replay["idempotent_hit"] = True
                return Receipt(**replay)

        order = self.repo.get_order(out_trade_no)
        if order is None:
            raise PaymentError(OFG_ORDER_NOT_FOUND, f"订单 {out_trade_no} 不存在", 404)

        decoded = decode_payment_proof(proof_header)
        verify = self.provider.verify_proof(decoded)
        validate_fulfillment(
            verify, order,
            trade_already_used=self.repo.is_trade_used(verify.trade_no),
            order_fulfilled_trade=self.repo.fulfilled_trade_of_order(out_trade_no),
        )

        fulfillment_id = f"ful_{uuid.uuid4().hex[:16]}"
        receipt = Receipt(
            receipt_id=f"rcpt_{uuid.uuid4().hex[:16]}",
            out_trade_no=out_trade_no,
            trade_no=verify.trade_no,
            resource_id=verify.resource_id,
            amount=order["amount"],
            currency=order["currency"],
            fulfillment_id=fulfillment_id,
            idempotent_hit=False,
            delivered=_deliver(verify.resource_id, verify.trade_no),
        )
        self.repo.record_fulfillment(
            fulfillment_id, idempotency_key, out_trade_no, verify.trade_no,
            verify.resource_id, order["amount"],
            receipt.model_dump_json(),
        )
        self.repo.mark_order_fulfilled(out_trade_no, verify.trade_no)
        return receipt

    def reconcile(self) -> dict:
        orders = self.repo.list_orders()
        fulfillments = self.repo.list_fulfillments()
        fulfilled_nos = {f["out_trade_no"] for f in fulfillments}
        paid_total = sum(
            (Decimal(o["amount"]) for o in orders
             if o["status"] in ("paid", "fulfilled", "refunded")),
            Decimal("0.00"),
        )
        fulfilled_total = sum(
            (Decimal(f["amount"]) for f in fulfillments), Decimal("0.00"))
        undelivered_paid = [
            o["out_trade_no"] for o in orders
            if o["status"] == "paid" and o["out_trade_no"] not in fulfilled_nos
        ]
        return {
            "order_count": len(orders),
            "fulfillment_count": len(fulfillments),
            "paid_total_cny": str(paid_total),
            "fulfilled_total_cny": str(fulfilled_total),
            "paid_but_not_fulfilled": undelivered_paid,
            "balanced": paid_total == fulfilled_total and not undelivered_paid,
        }

    def refund(self, out_trade_no: str, reason: str | None) -> dict:
        order = self.repo.get_order(out_trade_no)
        if order is None:
            raise PaymentError(OFG_ORDER_NOT_FOUND, "订单不存在", 404)
        if order["status"] not in ("paid", "fulfilled"):
            raise PaymentError("AIPAY_REFUND_ILLEGAL_STATE",
                               f"订单状态 {order['status']} 不可退款", 409)
        refund_id = f"rf_{uuid.uuid4().hex[:16]}"
        # Mock 直接全额退款；真实 provider 应在此调用支付宝退款接口
        self.repo.record_refund(refund_id, out_trade_no, order["amount"],
                                reason or "")
        return {"refund_id": refund_id, "out_trade_no": out_trade_no,
                "refund_amount": order["amount"], "currency": order["currency"],
                "status": "refunded"}

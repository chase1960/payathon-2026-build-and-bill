"""内置 Mock 提供方：无需密钥即可跑通 402 → 支付 → 核验 → 履约全链路，用于联调与测试。"""
from __future__ import annotations

import base64
import json
import uuid
from typing import Any

from app.core.errors import OFG_PROOF_INACTIVE, PaymentError
from app.models.schemas import PrecreateRequest, VerifyResult
from app.providers.base import PaymentProvider
from app.storage.repository import Repository


class MockPaymentProvider(PaymentProvider):
    name = "mock"

    def __init__(self, repo: Repository):
        self.repo = repo

    def precreate(self, req: PrecreateRequest) -> str:
        pre_pay_id = f"amt_mock_{uuid.uuid4().hex[:16]}"
        self.repo.save_prepayment(pre_pay_id, req.out_trade_no, paid=False)
        return pre_pay_id

    def mock_pay(self, pre_pay_id: str) -> dict[str, str]:
        """模拟买家完成付款：置位已支付，生成 trade_no 与可回传的 Payment-Proof 头。"""
        prepay = self.repo.get_prepayment(pre_pay_id)
        if prepay is None:
            raise PaymentError("MOCK_PREPAY_NOT_FOUND", "预下单不存在", 404)
        order = self.repo.get_order(prepay["out_trade_no"])
        trade_no = f"mock_trade_{uuid.uuid4().hex[:16]}"
        self.repo.save_prepayment(pre_pay_id, prepay["out_trade_no"],
                                  trade_no=trade_no, paid=True)
        self.repo.mark_order_paid(prepay["out_trade_no"], trade_no)

        proof_payload = {
            "protocol": {
                "payment_proof": uuid.uuid4().hex,
                "trade_no": trade_no,
                "out_trade_no": order["out_trade_no"],
                "amount": order["amount"],
                "resource_id": order["resource_id"],
                "active": True,
            },
            "method": {"client_session": f"sess_{order['out_trade_no']}"},
        }
        header = base64.b64encode(
            json.dumps(proof_payload, ensure_ascii=False).encode("utf-8")
        ).decode("ascii")
        return {"trade_no": trade_no, "payment_proof": header}

    def verify_proof(self, decoded: dict[str, Any]) -> VerifyResult:
        row = self.repo.conn.execute(
            "SELECT paid FROM prepayments WHERE trade_no=?",
            (decoded["trade_no"],),
        ).fetchone()
        if row is None or not row["paid"]:
            raise PaymentError(OFG_PROOF_INACTIVE, "Mock 平台未查到该笔已支付交易")
        return VerifyResult(
            active=True,
            amount=str(decoded["amount"]),
            out_trade_no=str(decoded["out_trade_no"]),
            trade_no=str(decoded["trade_no"]),
            resource_id=str(decoded["resource_id"]),
            client_session=str(decoded.get("client_session", "")),
        )

"""受保护资源的 402 支付-核验-履约主流程，以及 Mock 支付端点。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse

from app.api.deps import (get_checkout_service, get_fulfillment_service,
                          get_provider)
from app.core.proof import decode_payment_proof
from app.providers.mock import MockPaymentProvider
from app.services.catalog import find_resource

router = APIRouter(tags=["resources"])


@router.get("/resources/{resource_id}/access")
def access_resource(
    resource_id: str,
    request: Request,
    payment_proof: str | None = Header(default=None, alias="Payment-Proof"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    client_session: str = Header(default="anonymous-agent", alias="X-Client-Session"),
    checkout=Depends(get_checkout_service),
    fulfillment=Depends(get_fulfillment_service),
):
    resource = find_resource(resource_id)

    # 1) 无凭证：预下单并返回 402 + amtPaymentLink
    if not payment_proof:
        bill = checkout.create_checkout(resource, client_session)
        return JSONResponse(
            status_code=402,
            content=bill.model_dump(),
            headers={"amtPaymentLink": bill.payment_link},
        )

    # 2) 携带 Payment-Proof：解码得到本商户单号后进入核验履约
    decoded = decode_payment_proof(payment_proof)
    out_trade_no = str(decoded["out_trade_no"])
    receipt = fulfillment.fulfill(out_trade_no, payment_proof, idempotency_key)
    return JSONResponse(status_code=200, content=receipt.model_dump())


@router.post("/mock/pay/{pre_pay_id}")
def mock_pay(pre_pay_id: str, provider=Depends(get_provider)):
    """仅 Mock 模式开放：模拟买家付款并返回可回传的 Payment-Proof。"""
    if not isinstance(provider, MockPaymentProvider):
        return JSONResponse(status_code=404,
                            content={"error": "mock endpoint disabled in alipay mode"})
    return provider.mock_pay(pre_pay_id)

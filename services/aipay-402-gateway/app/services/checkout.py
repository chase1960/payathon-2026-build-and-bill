"""结账编排：生成订单与预下单，产出 402 账单。"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.models.schemas import BillBody, CatalogResource, PrecreateRequest
from app.providers.base import PaymentProvider
from app.storage.repository import Repository


def _gen_out_trade_no() -> str:
    return f"AIP{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8]}"


def _pay_before(settings: Settings) -> str:
    t = datetime.now(timezone.utc) + timedelta(minutes=settings.pay_before_minutes)
    return t.isoformat()


class CheckoutService:
    def __init__(self, repo: Repository, provider: PaymentProvider,
                 settings: Settings):
        self.repo = repo
        self.provider = provider
        self.settings = settings

    def create_checkout(self, resource: CatalogResource,
                        client_session: str,
                        out_trade_no: str | None = None) -> BillBody:
        out_trade_no = out_trade_no or _gen_out_trade_no()
        pay_before = _pay_before(self.settings)

        existing = self.repo.get_order(out_trade_no)
        if existing is None:
            self.repo.create_order(
                out_trade_no, resource.resource_id, resource.price_cny,
                self.settings.currency, client_session,
            )

        # 已存在有效预下单则复用，避免一次访问生成多笔待支付单
        prepay = self.repo.prepayment_by_order(out_trade_no)
        if prepay and not prepay["paid"]:
            pre_pay_id = prepay["pre_pay_id"]
        else:
            req = PrecreateRequest(
                out_trade_no=out_trade_no,
                service_id=self.settings.service_id,
                goods_name=resource.name,
                amount=resource.price_cny,
                pay_before=pay_before,
                currency=self.settings.currency,
                memo=resource.description[:60],
                resource_id=resource.resource_id,
            )
            pre_pay_id = self.provider.precreate(req)

        return BillBody(
            out_trade_no=out_trade_no,
            resource_id=resource.resource_id,
            amount=resource.price_cny,
            currency=self.settings.currency,
            pay_before=pay_before,
            payment_link=pre_pay_id,  # 同时通过 amtPaymentLink 响应头下发
            instructions=(
                "请使用支付宝 AI 付完成支付，随后在请求头携带 Base64 编码的 "
                "Payment-Proof 重新请求本资源。"
            ),
        )

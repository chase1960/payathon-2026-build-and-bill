"""支付宝 AI 付（A2M / Machine Pay）真实提供方适配骨架。

接口名与字段严格对齐官方文档：
- 预下单 alipay.aipay.agent.payment.precreate → amt_pre_pay_id
- 核验   alipay.aipay.agent.payment.verify     → active/amount/out_trade_no/trade_no/resource_id

本文件保留完整请求/响应映射，**RSA2 签名与网关调用以 TODO 标注**：
接入时填入 App 证书/应用私钥并实现 `_sign` 与 `_post_openapi`，业务编排无需改动。
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.core.errors import OFG_PROOF_INACTIVE, PaymentError
from app.models.schemas import PrecreateRequest, VerifyResult
from app.providers.base import PaymentProvider

PRECREATE_METHOD = "alipay.aipay.agent.payment.precreate"
VERIFY_METHOD = "alipay.aipay.agent.payment.verify"


class AlipayAipayProvider(PaymentProvider):
    name = "alipay"

    def __init__(self, settings: Settings):
        self.settings = settings

    # ---- 公共网关调用占位 ----
    def _post_openapi(self, method: str, biz_content: dict) -> dict:
        if not self.settings.app_id or not self.settings.app_private_key:
            raise PaymentError(
                "AIPAY_NOT_CONFIGURED",
                "未配置 AIPAY_APP_ID / AIPAY_APP_PRIVATE_KEY，无法调用真实网关；"
                "请先在 .env 填入凭证并实现 RSA2 签名（见类内 TODO）",
                503,
            )
        payload = {
            "app_id": self.settings.app_id,
            "method": method,
            "charset": "utf-8",
            "sign_type": "RSA2",
            "biz_content": biz_content,
            # TODO: timestamp、nonce、version=1.0、format=JSON
        }
        # TODO: payload["sign"] = self._sign(canonical_query, app_private_key)
        #   1) 按 key 排序拼接待签名串；2) RSA-SHA256 签名后 Base64；
        #   3) 用 httpx.post(settings.active_gateway, data=payload) 发起请求；
        #   4) 校验 alipay 公钥响应签名后返回 data 节点。
        with httpx.Client(timeout=10) as client:  # pragma: no cover - 需真实凭证
            resp = client.post(self.settings.active_gateway, data=payload)
            resp.raise_for_status()
            return resp.json()

    def precreate(self, req: PrecreateRequest) -> str:
        biz = {
            "out_trade_no": req.out_trade_no,
            "service_id": req.service_id,
            "goods_name": req.goods_name,
            "amount": req.amount,                 # 单位元，单笔不超过 50
            "pay_before": req.pay_before,
            "currency": req.currency,            # 当前仅支持 CNY
            "memo": req.memo,
        }
        data = self._post_openapi(PRECREATE_METHOD, biz)
        try:
            return data["amt_pre_pay_id"]
        except KeyError:
            raise PaymentError("AIPAY_PRECREATE_FAILED", f"预下单响应异常: {data}", 502)

    def verify_proof(self, decoded: dict[str, Any]) -> VerifyResult:
        biz = {
            "payment_proof": decoded["payment_proof"],
            "out_trade_no": decoded.get("out_trade_no"),
            "resource_id": decoded.get("resource_id"),
        }
        data = self._post_openapi(VERIFY_METHOD, biz)
        if not data.get("active", False):
            raise PaymentError(OFG_PROOF_INACTIVE, "支付宝 verify 返回 active=false")
        return VerifyResult(
            active=bool(data["active"]),
            amount=str(data["amount"]),
            out_trade_no=str(data["out_trade_no"]),
            trade_no=str(data["trade_no"]),
            resource_id=str(data["resource_id"]),
            client_session=str(decoded.get("client_session", "")),
        )

"""Pydantic v2 请求/响应模型。金额一律用字符串十进制传输。"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EntitlementKind(str, Enum):
    one_off = "one_off"
    count_pack = "count_pack"
    duration = "duration"


class CatalogResource(BaseModel):
    resource_id: str
    name: str
    description: str
    price_cny: str
    currency: str = "CNY"
    entitlement: EntitlementKind
    quota: Optional[int] = None
    endpoint: str
    tags: list[str] = Field(default_factory=list)


class Catalog(BaseModel):
    service_id: str
    protocol: str = "alipay-aipay/machine-pay-402"
    currency: str = "CNY"
    resources: list[CatalogResource]


class PrecreateRequest(BaseModel):
    out_trade_no: str
    service_id: str
    goods_name: str
    amount: str
    pay_before: str
    currency: str = "CNY"
    memo: Optional[str] = None
    resource_id: str


class BillBody(BaseModel):
    """402 响应体：机器可读的结构化账单。"""
    error: str = "payment_required"
    code: str = "OFG_402"
    out_trade_no: str
    resource_id: str
    amount: str
    currency: str
    pay_before: str
    payment_link: str
    instructions: str


class VerifyResult(BaseModel):
    active: bool
    amount: str
    out_trade_no: str
    trade_no: str
    resource_id: str
    client_session: str


class Receipt(BaseModel):
    receipt_id: str
    out_trade_no: str
    trade_no: str
    resource_id: str
    amount: str
    currency: str
    fulfillment_id: str
    idempotent_hit: bool
    delivered: dict


class OrderView(BaseModel):
    out_trade_no: str
    resource_id: str
    amount: str
    status: str
    trade_no: Optional[str] = None
    pre_pay_id: Optional[str] = None


class RefundRequest(BaseModel):
    reason: Optional[str] = None

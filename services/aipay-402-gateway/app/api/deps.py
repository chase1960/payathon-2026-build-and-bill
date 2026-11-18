"""依赖装配：按 AIPAY_PROVIDER 在 Mock 与真实支付宝实现间切换。"""
from __future__ import annotations

from functools import lru_cache

from app.config import settings
from app.providers.alipay_aipay import AlipayAipayProvider
from app.providers.base import PaymentProvider
from app.providers.mock import MockPaymentProvider
from app.services.checkout import CheckoutService
from app.services.fulfillment import FulfillmentService
from app.storage.repository import Repository


@lru_cache(maxsize=1)
def get_repo() -> Repository:
    return Repository(settings.db_path)


@lru_cache(maxsize=1)
def get_provider() -> PaymentProvider:
    if settings.provider == "alipay":
        return AlipayAipayProvider(settings)
    return MockPaymentProvider(get_repo())


@lru_cache(maxsize=1)
def get_checkout_service() -> CheckoutService:
    return CheckoutService(get_repo(), get_provider(), settings)


@lru_cache(maxsize=1)
def get_fulfillment_service() -> FulfillmentService:
    return FulfillmentService(get_repo(), get_provider())

"""支付提供方抽象：Mock 与真实支付宝 AI Pay 实现同一接口，可无缝切换。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.models.schemas import PrecreateRequest, VerifyResult


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    def precreate(self, req: PrecreateRequest) -> str:
        """预下单，返回 amt_pre_pay_id。"""

    @abstractmethod
    def verify_proof(self, decoded: dict[str, Any]) -> VerifyResult:
        """向支付平台核验凭证，返回标准化 VerifyResult。"""

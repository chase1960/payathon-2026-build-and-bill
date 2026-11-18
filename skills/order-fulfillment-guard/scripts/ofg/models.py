"""领域模型与常量。金额统一使用 Decimal（入参为字符串）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional


# ---- 违规 / 结论码：全部带 OFG 前缀，便于在工单系统里检索 ----
class Code(str, Enum):
    OK = "OFG_OK"
    PROOF_INACTIVE = "OFG_1001"          # 凭证 active=false 或平台验证未通过
    AMOUNT_MISMATCH = "OFG_1002"         # 凭证金额与订单金额不一致
    ORDER_NO_MISMATCH = "OFG_1003"       # out_trade_no 不一致
    RESOURCE_MISMATCH = "OFG_1004"       # resource_id 不一致
    REPLAY_DETECTED = "OFG_1005"         # trade_no 已履约，疑似重放
    PROOF_MALFORMED = "OFG_1006"         # 凭证结构缺字段
    ORDER_NOT_FOUND = "OFG_1007"         # 找不到对应订单
    ORDER_ALREADY_FULFILLED = "OFG_1008"  # 订单已被另一凭证履约
    REFUND_WINDOW_EXPIRED = "OFG_2001"   # 超过退款窗口
    REFUND_FULLY_CONSUMED = "OFG_2002"   # 权益已耗尽，默认不退
    REFUND_REVIEW = "OFG_2003"           # 需人工复核
    RISK_REPEATED_PAYMENT = "OFG_3001"   # 同会话短时重复支付
    RISK_AMOUNT_ANOMALY = "OFG_3002"     # 金额偏离正常区间
    RISK_SESSION_INCONSISTENT = "OFG_3003"  # 买家会话与订单归属不一致


class EntitlementType(str, Enum):
    ONE_OFF = "one_off"          # 一次性买断
    COUNT_PACK = "count_pack"    # 次数包
    DURATION = "duration"        # 时长包（按天）


class OrderStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FULFILLED = "fulfilled"
    REFUNDED = "refunded"
    CLOSED = "closed"


@dataclass(frozen=True)
class PaymentProof:
    """对齐支付宝 AI 付 Payment-Proof（Base64 解码后业务字段）。"""
    payment_proof: str
    trade_no: str
    client_session: str
    out_trade_no: str
    amount: Decimal
    resource_id: str
    active: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> "PaymentProof":
        required = ["payment_proof", "trade_no", "client_session",
                    "out_trade_no", "amount", "resource_id"]
        missing = [k for k in required if data.get(k) in (None, "")]
        if missing:
            raise ValueError(f"凭证缺少必填字段: {', '.join(missing)}")
        return cls(
            payment_proof=str(data["payment_proof"]),
            trade_no=str(data["trade_no"]),
            client_session=str(data["client_session"]),
            out_trade_no=str(data["out_trade_no"]),
            amount=Decimal(str(data["amount"])),
            resource_id=str(data["resource_id"]),
            active=bool(data.get("active", True)),
        )


@dataclass
class Order:
    out_trade_no: str
    resource_id: str
    amount: Decimal
    entitlement_type: EntitlementType
    client_session: str
    status: OrderStatus = OrderStatus.PENDING
    # count_pack 总次数 / duration 总天数；one_off 不使用
    total_quota: Optional[int] = None
    created_at: Optional[str] = None
    trade_no: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Order":
        return cls(
            out_trade_no=str(data["out_trade_no"]),
            resource_id=str(data["resource_id"]),
            amount=Decimal(str(data["amount"])),
            entitlement_type=EntitlementType(data["entitlement_type"]),
            client_session=str(data["client_session"]),
            status=OrderStatus(data.get("status", "pending")),
            total_quota=data.get("total_quota"),
            created_at=data.get("created_at"),
            trade_no=data.get("trade_no"),
        )


@dataclass
class VerificationResult:
    passed: bool
    codes: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"passed": self.passed, "codes": self.codes, "details": self.details}

"""Payment-Proof 五要素核验，对齐支付宝 AI 付 verify 业务校验口径。"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional, Protocol

from .models import Code, Order, PaymentProof, VerificationResult


class FulfillmentLedger(Protocol):
    """核验所需的最小账本接口，store.sqlite 与内存实现都满足。"""
    def is_trade_used(self, trade_no: str) -> bool: ...
    def fulfilled_trade_of_order(self, out_trade_no: str) -> Optional[str]: ...


def verify_proof(
    proof: PaymentProof,
    order: Optional[Order],
    ledger: Optional[FulfillmentLedger] = None,
) -> VerificationResult:
    """返回是否允许履约；不抛业务异常，所有问题收敛进 codes/details。"""
    codes: list[str] = []
    details: list[str] = []

    # 1. 订单必须存在
    if order is None:
        codes.append(Code.ORDER_NOT_FOUND.value)
        details.append(f"未找到商户订单 {proof.out_trade_no}，拒绝交付")
        return VerificationResult(False, codes, details)

    # 2. 平台侧验证结论
    if not proof.active:
        codes.append(Code.PROOF_INACTIVE.value)
        details.append("支付凭证 active=false，平台验证未通过")

    # 3. 金额严格一致（Decimal，杜绝 0.1+0.2 浮点问题）
    if proof.amount != order.amount:
        codes.append(Code.AMOUNT_MISMATCH.value)
        details.append(f"金额不一致: 凭证 {proof.amount} ≠ 订单 {order.amount}")

    # 4. 商户订单号一致
    if proof.out_trade_no != order.out_trade_no:
        codes.append(Code.ORDER_NO_MISMATCH.value)
        details.append(
            f"订单号不一致: 凭证 {proof.out_trade_no} ≠ 订单 {order.out_trade_no}"
        )

    # 5. 资源 ID 一致（防止拿 A 资源的凭证领 B 资源）
    if proof.resource_id != order.resource_id:
        codes.append(Code.RESOURCE_MISMATCH.value)
        details.append(
            f"资源不一致: 凭证 {proof.resource_id} ≠ 订单 {order.resource_id}"
        )

    # 6. 买家会话归属一致（弱化校验：不一致给风险提示，但归并到防重放账本判断）
    if proof.client_session != order.client_session:
        codes.append(Code.RISK_SESSION_INCONSISTENT.value)
        details.append("买家 client_session 与订单归属不一致，需人工关注")

    if ledger is not None:
        # 7. trade_no 全局防重放
        if ledger.is_trade_used(proof.trade_no):
            codes.append(Code.REPLAY_DETECTED.value)
            details.append(f"交易号 {proof.trade_no} 已完成过履约，判定为重放请求")
        # 8. 同一订单已被别的凭证履约
        used_trade = ledger.fulfilled_trade_of_order(order.out_trade_no)
        if used_trade and used_trade != proof.trade_no:
            codes.append(Code.ORDER_ALREADY_FULFILLED.value)
            details.append(
                f"订单 {order.out_trade_no} 已由交易号 {used_trade} 履约"
            )

    # 阻断类违规（风险类 RISK_* 不单独阻断交付，会话不一致仅提示，这里阻断码显式列出）
    blocking = {
        Code.PROOF_INACTIVE.value,
        Code.AMOUNT_MISMATCH.value,
        Code.ORDER_NO_MISMATCH.value,
        Code.RESOURCE_MISMATCH.value,
        Code.REPLAY_DETECTED.value,
        Code.ORDER_NOT_FOUND.value,
        Code.ORDER_ALREADY_FULFILLED.value,
    }
    passed = not (set(codes) & blocking)
    if passed:
        codes.insert(0, Code.OK.value)
        details.append("五要素核验通过，允许履约")
    return VerificationResult(passed, codes, details)


def to_decimal(value: str) -> Decimal:
    """统一金额入口，拒绝非法十进制。"""
    return Decimal(str(value)).quantize(Decimal("0.01"))

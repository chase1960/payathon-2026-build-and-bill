"""与 Skill 层保持一致的 OFG 违规码与业务异常。"""
from __future__ import annotations


class PaymentError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 402):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


# 复用 order-fulfillment-guard 的 OFG 口径
OFG_OK = "OFG_OK"
OFG_PROOF_INACTIVE = "OFG_1001"
OFG_AMOUNT_MISMATCH = "OFG_1002"
OFG_ORDER_NO_MISMATCH = "OFG_1003"
OFG_RESOURCE_MISMATCH = "OFG_1004"
OFG_REPLAY_DETECTED = "OFG_1005"
OFG_PROOF_MALFORMED = "OFG_1006"
OFG_ORDER_NOT_FOUND = "OFG_1007"
OFG_ORDER_ALREADY_FULFILLED = "OFG_1008"

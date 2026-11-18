"""日结对账：本地订单与平台账单逐笔匹配，输出四类差异。"""
from __future__ import annotations

from decimal import Decimal
from typing import Any


def _amount(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def reconcile(local_orders: list[dict], platform_bill: list[dict]) -> dict:
    local = {str(o["out_trade_no"]): o for o in local_orders}
    bill = {str(b["out_trade_no"]): b for b in platform_bill}

    diffs = {
        "local_only": [],        # 本地有、账单无：可能掉单或未支付
        "bill_only": [],         # 账单有、本地无：漏登记，风险最高
        "amount_mismatch": [],   # 金额不一致：疑似篡改或回调错误
        "status_mismatch": [],   # 状态不一致：履约/记账滞后
    }
    settled_total = Decimal("0.00")

    for no, order in local.items():
        b = bill.get(no)
        if b is None:
            diffs["local_only"].append({
                "out_trade_no": no, "local_amount": str(order["amount"]),
                "local_status": order.get("status"),
            })
            continue
        if _amount(order["amount"]) != _amount(b["amount"]):
            diffs["amount_mismatch"].append({
                "out_trade_no": no,
                "local_amount": str(order["amount"]),
                "bill_amount": str(b["amount"]),
                "gap": str(_amount(b["amount"]) - _amount(order["amount"])),
            })
        if str(order.get("status")) != str(b.get("status")):
            diffs["status_mismatch"].append({
                "out_trade_no": no,
                "local_status": order.get("status"),
                "bill_status": b.get("status"),
            })
        if str(b.get("status")) == "paid":
            settled_total += _amount(b["amount"])

    for no, b in bill.items():
        if no not in local:
            diffs["bill_only"].append({
                "out_trade_no": no, "bill_amount": str(b["amount"]),
                "bill_status": b.get("status"), "trade_no": b.get("trade_no"),
            })
            if str(b.get("status")) == "paid":
                settled_total += _amount(b["amount"])

    return {
        "local_count": len(local),
        "bill_count": len(bill),
        "settled_total_cny": str(settled_total),
        "diff_counts": {k: len(v) for k, v in diffs.items()},
        "balanced": all(len(v) == 0 for v in diffs.values()),
        "differences": diffs,
        "handling_hint": {
            "local_only": "核对是否为未支付超时单，必要时关单",
            "bill_only": "优先排查，补登订单并核查是否已发货",
            "amount_mismatch": "暂停自动履约，比对预下单金额与回调金额",
            "status_mismatch": "以平台状态为准补记流水，跟进交付",
        },
    }

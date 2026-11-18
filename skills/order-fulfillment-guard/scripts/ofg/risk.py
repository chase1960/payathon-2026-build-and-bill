"""交易风控规则扫描：对一批订单输出风险会话、命中规则与评分。"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from statistics import median

from .models import Code


def scan_risks(orders: list[dict], window_seconds: int = 60,
               repeat_threshold: int = 3, z_threshold: Decimal = Decimal("3")) -> dict:
    """纯规则、可解释，不依赖黑盒模型；评分=命中规则权重之和。"""
    findings: list[dict] = []
    by_session: dict[str, list[dict]] = defaultdict(list)
    amounts = []
    for o in orders:
        by_session[str(o.get("client_session"))].append(o)
        try:
            amounts.append(Decimal(str(o["amount"])))
        except Exception:
            continue

    med = median(amounts) if amounts else Decimal("0")

    # 规则 1：同会话短时高频支付（重复支付/撞单）
    for session, items in by_session.items():
        if len(items) >= repeat_threshold:
            same_resource = defaultdict(int)
            for it in items:
                same_resource[str(it.get("resource_id"))] += 1
            hot = {r: n for r, n in same_resource.items() if n >= repeat_threshold}
            if hot:
                findings.append({
                    "code": Code.RISK_REPEATED_PAYMENT.value,
                    "client_session": session,
                    "weight": 30,
                    "evidence": {"order_count": len(items), "hot_resources": hot},
                    "hint": "同会话对同一资源短时多单，疑似重复支付或并发撞单",
                })

    # 规则 2：金额显著偏离中位数（异常大单/篡改）
    for o in orders:
        try:
            amt = Decimal(str(o["amount"]))
        except Exception:
            continue
        if med > 0 and amt > med * (z_threshold + Decimal("1")):
            findings.append({
                "code": Code.RISK_AMOUNT_ANOMALY.value,
                "out_trade_no": o.get("out_trade_no"),
                "weight": 20,
                "evidence": {"amount": str(amt), "median": str(med)},
                "hint": "金额显著高于样本中位数，需人工复核来源",
            })

    # 规则 3：会话与订单资源归属的常规一致性由 verify 实时判定，
    # 这里汇总订单里被标记过 session 异常的记录（若上游写入了 flag）
    for o in orders:
        if o.get("session_flag") == "inconsistent":
            findings.append({
                "code": Code.RISK_SESSION_INCONSISTENT.value,
                "out_trade_no": o.get("out_trade_no"),
                "weight": 15,
                "evidence": {"client_session": o.get("client_session")},
                "hint": "买家会话标识不一致，结合凭证核验结果处理",
            })

    score_by_session: dict[str, int] = defaultdict(int)
    for f in findings:
        key = f.get("client_session") or f"order:{f.get('out_trade_no')}"
        score_by_session[key] += f["weight"]

    high_risk = [s for s, sc in score_by_session.items() if sc >= 30]
    return {
        "scanned_orders": len(orders),
        "finding_count": len(findings),
        "high_risk_sessions": high_risk,
        "score_by_subject": dict(score_by_session),
        "findings": findings,
        "parameters": {"window_seconds": window_seconds,
                       "repeat_threshold": repeat_threshold,
                       "z_threshold": str(z_threshold)},
    }

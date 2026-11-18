"""命令行入口：verify / entitle / reconcile / refund / risk。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .models import Order, PaymentProof
from .proof import verify_proof
from .reconcile import reconcile as run_reconcile
from .refund import decide_refund
from .risk import scan_risks
from .store import SqliteLedger
from .entitlement import entitle as run_entitle


def _load_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _find_order(payload, out_trade_no: str) -> Order | None:
    if isinstance(payload, list):
        for item in payload:
            if str(item.get("out_trade_no")) == out_trade_no:
                return Order.from_dict(item)
        return None
    return Order.from_dict(payload)


def _print(result: dict, pretty: bool) -> None:
    if pretty:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False))


def _has_blocking(result: dict) -> bool:
    if "verification" in result:
        return not result["verification"].get("passed", False)
    if "passed" in result:
        return not result["passed"]
    if result.get("decision") == "reject":
        return True
    if result.get("high_risk_sessions"):
        return True
    if result.get("balanced") is False:
        return True
    return False


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ofg", description="AI 交易履约核验官")
    sub = p.add_subparsers(dest="command", required=True)

    v = sub.add_parser("verify", help="五要素核验 Payment-Proof")
    v.add_argument("--proof", required=True)
    v.add_argument("--order", required=True)
    v.add_argument("--db", help="可选：提供 sqlite 账本以启用防重放校验")
    v.add_argument("--pretty", action="store_true")

    e = sub.add_parser("entitle", help="核验并幂等核销权益")
    e.add_argument("--proof", required=True)
    e.add_argument("--order", required=True)
    e.add_argument("--db", required=True)
    e.add_argument("--fulfillment-id")
    e.add_argument("--pretty", action="store_true")

    r = sub.add_parser("reconcile", help="日结对账")
    r.add_argument("--local", required=True)
    r.add_argument("--bill", required=True)
    r.add_argument("--pretty", action="store_true")

    rf = sub.add_parser("refund", help="退款初判")
    rf.add_argument("--request", required=True)
    rf.add_argument("--db", required=True)
    rf.add_argument("--pretty", action="store_true")

    rk = sub.add_parser("risk", help="风控扫描")
    rk.add_argument("--order", required=True)
    rk.add_argument("--pretty", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "verify":
            proof = PaymentProof.from_dict(_load_json(args.proof))
            order = _find_order(_load_json(args.order), proof.out_trade_no)
            ledger = SqliteLedger(args.db) if args.db else None
            result = verify_proof(proof, order, ledger).as_dict()
            if ledger:
                ledger.close()

        elif args.command == "entitle":
            proof = PaymentProof.from_dict(_load_json(args.proof))
            order = _find_order(_load_json(args.order), proof.out_trade_no)
            if order is None:
                raise SystemExit("订单不存在，无法核销")
            ledger = SqliteLedger(args.db)
            ledger.upsert_order(order)
            result = run_entitle(
                ledger, proof, order, fulfillment_id=args.fulfillment_id
            ).as_dict()
            ledger.close()

        elif args.command == "reconcile":
            result = run_reconcile(_load_json(args.local), _load_json(args.bill))

        elif args.command == "refund":
            ledger = SqliteLedger(args.db)
            result = decide_refund(ledger, _load_json(args.request))
            ledger.close()

        else:  # risk
            payload = _load_json(args.order)
            orders = payload if isinstance(payload, list) else [payload]
            result = scan_risks(orders)

        _print(result, getattr(args, "pretty", False))
        return 2 if _has_blocking(result) else 0
    except (KeyError, ValueError, FileNotFoundError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""AI Agent 客户端示例：自动理解 402 账单、完成支付、携带 Payment-Proof 重试并取得回执。

运行：
    cd services/aipay-402-gateway
    uvicorn app.main:app --port 8000        # 另开一个终端
    python examples/agent_client.py
"""
from __future__ import annotations

import sys

import httpx

BASE_URL = "http://localhost:8000"


def pay_for_bill(client: httpx.Client, pre_pay_id: str) -> str:
    """Mock 模式下的付款动作；真实场景替换为唤起支付宝 AI 付并轮询支付结果。"""
    resp = client.post(f"{BASE_URL}/mock/pay/{pre_pay_id}")
    resp.raise_for_status()
    return resp.json()["payment_proof"]


def fetch_paid_resource(client: httpx.Client, resource_id: str,
                        idempotency_key: str) -> dict:
    headers = {"Idempotency-Key": idempotency_key, "X-Client-Session": "agent-demo"}
    resp = client.get(f"{BASE_URL}/resources/{resource_id}/access", headers=headers)

    if resp.status_code == 402:
        bill = resp.json()
        pre_pay_id = resp.headers.get("amtPaymentLink") or bill["payment_link"]
        print(f"[agent] 收到 402 账单：{bill['amount']} {bill['currency']}，"
              f"资源 {bill['resource_id']}，开始支付 {pre_pay_id}")
        proof = pay_for_bill(client, pre_pay_id)

        headers["Payment-Proof"] = proof
        resp = client.get(f"{BASE_URL}/resources/{resource_id}/access", headers=headers)

    resp.raise_for_status()
    return resp.json()


def main() -> int:
    with httpx.Client(timeout=10) as client:
        catalog = client.get(f"{BASE_URL}/.well-known/aipay-catalog").json()
        print("[agent] 发现可购资源：",
              [r["resource_id"] for r in catalog["resources"]])

        receipt = fetch_paid_resource(
            client, "res_company_credit_report", idempotency_key="idem-demo-001"
        )
        print("[agent] 履约成功，回执：")
        print(receipt)

        # 用同一幂等键重试，验证不会重复交付
        again = fetch_paid_resource(
            client, "res_company_credit_report", idempotency_key="idem-demo-001"
        )
        print("[agent] 幂等重试 idempotent_hit =", again["idempotent_hit"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

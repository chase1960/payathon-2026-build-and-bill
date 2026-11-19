import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.deps import get_repo  # noqa: E402
from app.main import app  # noqa: E402


class GatewayTestCase(unittest.TestCase):
    def setUp(self):
        self.repo = get_repo()
        for table in ("refunds", "fulfillments", "prepayments", "orders"):
            self.repo.conn.execute(f"DELETE FROM {table}")
        self.repo.conn.commit()
        self.client = TestClient(app)

    def _start_purchase(self, resource_id):
        """返回 (402 账单, pre_pay_id)。"""
        resp = self.client.get(f"/resources/{resource_id}/access",
                               headers={"Idempotency-Key": "k-1"})
        self.assertEqual(resp.status_code, 402)
        return resp.json(), resp.headers["amtPaymentLink"]

    def _pay(self, pre_pay_id):
        resp = self.client.post(f"/mock/pay/{pre_pay_id}")
        self.assertEqual(resp.status_code, 200)
        return resp.json()["payment_proof"]

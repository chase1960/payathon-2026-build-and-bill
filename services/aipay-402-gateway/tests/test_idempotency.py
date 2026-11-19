import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests._client import GatewayTestCase  # noqa: E402

RESOURCE = "res_company_credit_report"
ACCESS = f"/resources/{RESOURCE}/access"


class TestIdempotency(GatewayTestCase):
    def test_same_idempotency_key_replays_receipt(self):
        _, pre_pay_id = self._start_purchase(RESOURCE)
        proof = self._pay(pre_pay_id)
        headers = {"Payment-Proof": proof, "Idempotency-Key": "stable-key"}

        first = self.client.get(ACCESS, headers=headers)
        second = self.client.get(ACCESS, headers=headers)
        self.assertEqual(first.status_code, 200)
        self.assertFalse(first.json()["idempotent_hit"])
        self.assertTrue(second.json()["idempotent_hit"])
        self.assertEqual(first.json()["receipt_id"], second.json()["receipt_id"])

        count = self.repo.conn.execute(
            "SELECT COUNT(*) c FROM fulfillments").fetchone()["c"]
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()

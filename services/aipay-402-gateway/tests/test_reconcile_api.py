import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests._client import GatewayTestCase  # noqa: E402


class TestReconcileAndRefund(GatewayTestCase):
    def _fulfill_one(self, resource="res_company_credit_report", key="k"):
        resp = self.client.get(f"/resources/{resource}/access",
                               headers={"Idempotency-Key": key})
        pre_pay_id = resp.headers["amtPaymentLink"]
        proof = self._pay(pre_pay_id)
        done = self.client.get(f"/resources/{resource}/access",
                               headers={"Payment-Proof": proof,
                                        "Idempotency-Key": key})
        self.assertEqual(done.status_code, 200)
        return done.json()["out_trade_no"]

    def test_balanced_after_fulfillment(self):
        self._fulfill_one()
        report = self.client.get("/admin/reconcile").json()
        self.assertTrue(report["balanced"])
        self.assertEqual(report["fulfillment_count"], 1)
        self.assertEqual(report["fulfilled_total_cny"], "9.90")

    def test_paid_without_fulfillment_unbalanced(self):
        self.repo.create_order("ORPHAN1", "res_monitor_30d", "39.00", "CNY", "s")
        self.repo.mark_order_paid("ORPHAN1", "trade_orphan")
        report = self.client.get("/admin/reconcile").json()
        self.assertFalse(report["balanced"])
        self.assertIn("ORPHAN1", report["paid_but_not_fulfilled"])

    def test_refund_flow(self):
        out_no = self._fulfill_one(key="kr")
        resp = self.client.post(f"/orders/{out_no}/refund", json={"reason": "demo"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "refunded")
        order = self.client.get(f"/orders/{out_no}").json()["order"]
        self.assertEqual(order["status"], "refunded")
        self.assertEqual(len(self.repo.list_refunds()), 1)


if __name__ == "__main__":
    unittest.main()

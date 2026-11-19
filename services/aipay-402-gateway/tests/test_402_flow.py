import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests._client import GatewayTestCase  # noqa: E402


class Test402Flow(GatewayTestCase):
    def test_catalog_discovery(self):
        resp = self.client.get("/.well-known/aipay-catalog")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["protocol"], "alipay-aipay/machine-pay-402")
        self.assertGreaterEqual(len(body["resources"]), 3)

    def test_full_402_to_200_flow(self):
        bill, pre_pay_id = self._start_purchase("res_company_credit_report")
        self.assertEqual(bill["code"], "OFG_402")
        self.assertEqual(bill["amount"], "9.90")
        self.assertTrue(pre_pay_id.startswith("amt_"))

        proof = self._pay(pre_pay_id)
        resp = self.client.get(
            "/resources/res_company_credit_report/access",
            headers={"Payment-Proof": proof, "Idempotency-Key": "k-1"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        receipt = resp.json()
        self.assertEqual(receipt["resource_id"], "res_company_credit_report")
        self.assertEqual(receipt["amount"], "9.90")
        self.assertFalse(receipt["idempotent_hit"])
        self.assertIn("download_url", receipt["delivered"])

    def test_order_persisted_as_fulfilled(self):
        _, pre_pay_id = self._start_purchase("res_company_credit_report")
        proof = self._pay(pre_pay_id)
        self.client.get("/resources/res_company_credit_report/access",
                        headers={"Payment-Proof": proof, "Idempotency-Key": "k-1"})
        orders = self.client.get("/admin/orders").json()["orders"]
        self.assertEqual(orders[0]["status"], "fulfilled")


if __name__ == "__main__":
    unittest.main()

import base64
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests._client import GatewayTestCase  # noqa: E402

RESOURCE = "res_company_credit_report"
ACCESS = f"/resources/{RESOURCE}/access"


def _recode(proof_header, mutate):
    payload = json.loads(base64.b64decode(proof_header))
    mutate(payload)
    return base64.b64encode(json.dumps(payload).encode()).decode()


class TestProofValidation(GatewayTestCase):
    def test_malformed_proof_rejected(self):
        resp = self.client.get(ACCESS, headers={"Payment-Proof": "not-base64!!!"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], "OFG_1006")

    def test_tampered_amount_rejected(self):
        _, pre_pay_id = self._start_purchase(RESOURCE)
        proof = self._pay(pre_pay_id)
        bad = _recode(proof, lambda p: p["protocol"].__setitem__("amount", "0.01"))
        resp = self.client.get(ACCESS, headers={"Payment-Proof": bad})
        self.assertEqual(resp.status_code, 402)
        self.assertEqual(resp.json()["code"], "OFG_1002")

    def test_tampered_resource_rejected(self):
        _, pre_pay_id = self._start_purchase(RESOURCE)
        proof = self._pay(pre_pay_id)
        bad = _recode(proof, lambda p: p["protocol"].__setitem__(
            "resource_id", "res_monitor_30d"))
        resp = self.client.get(ACCESS, headers={"Payment-Proof": bad})
        self.assertEqual(resp.json()["code"], "OFG_1004")

    def test_trade_no_replay_rejected(self):
        _, pre_pay_id = self._start_purchase(RESOURCE)
        proof = self._pay(pre_pay_id)
        first = self.client.get(ACCESS, headers={"Payment-Proof": proof,
                                                 "Idempotency-Key": "ka"})
        self.assertEqual(first.status_code, 200)
        # 同一凭证换幂等键重放：trade_no 已履约，必须拦截
        replay = self.client.get(ACCESS, headers={"Payment-Proof": proof,
                                                  "Idempotency-Key": "kb"})
        self.assertEqual(replay.status_code, 402)
        self.assertEqual(replay.json()["code"], "OFG_1005")


if __name__ == "__main__":
    unittest.main()

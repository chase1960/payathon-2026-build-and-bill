import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ofg.entitlement import entitle  # noqa: E402
from ofg.models import EntitlementType, Order, PaymentProof  # noqa: E402
from ofg.store import SqliteLedger  # noqa: E402


def proof(order_no="O1", trade="t1", session="s1", amount="9.90", res="r1"):
    return PaymentProof(
        payment_proof="pf", trade_no=trade, client_session=session,
        out_trade_no=order_no, amount=Decimal(amount), resource_id=res,
    )


def order(etype=EntitlementType.ONE_OFF, quota=None, no="O1"):
    return Order(
        out_trade_no=no, resource_id="r1", amount=Decimal("9.90"),
        entitlement_type=etype, client_session="s1", total_quota=quota,
        created_at="2026-11-18T00:00:00+00:00",
    )


class TestEntitlement(unittest.TestCase):
    def setUp(self):
        self.db = SqliteLedger(":memory:")

    def tearDown(self):
        self.db.close()

    def test_one_off_fulfill_and_idempotent_replay(self):
        o = order()
        self.db.upsert_order(o)
        r1 = entitle(self.db, proof(), o, fulfillment_id="f1")
        self.assertTrue(r1.verified)
        self.assertFalse(r1.idempotent_hit)
        # 同一 fulfillment_id 重放：不重复发放
        r2 = entitle(self.db, proof(), o, fulfillment_id="f1")
        self.assertTrue(r2.idempotent_hit)
        self.assertEqual(self.db.conn.execute(
            "SELECT COUNT(*) c FROM fulfillments").fetchone()["c"], 1)

    def test_trade_no_replay_blocked(self):
        o = order(no="O1")
        self.db.upsert_order(o)
        entitle(self.db, proof(trade="same-trade"), o, fulfillment_id="f1")
        # 换一个 fulfillment_id 但复用 trade_no，必须被防重放拦截
        r = entitle(self.db, proof(trade="same-trade"), o, fulfillment_id="f2")
        self.assertFalse(r.verified)
        self.assertIn("OFG_1005", r.verification["codes"])

    def test_count_pack_quota_consumption(self):
        o = order(EntitlementType.COUNT_PACK, quota=5)
        self.db.upsert_order(o)
        r = entitle(self.db, proof(), o, fulfillment_id="fc")
        self.assertTrue(r.verified)
        self.assertTrue(self.db.consume_quota("O1", 4))
        self.assertFalse(self.db.consume_quota("O1", 2))  # 余额不足
        row = self.db.get_entitlement("O1")
        self.assertEqual(row["used_quota"], 4)

    def test_duration_sets_validity(self):
        o = order(EntitlementType.DURATION, quota=30)
        self.db.upsert_order(o)
        r = entitle(self.db, proof(), o, fulfillment_id="fd")
        self.assertTrue(r.verified)
        self.assertIsNotNone(r.entitlement["valid_until"])


if __name__ == "__main__":
    unittest.main()

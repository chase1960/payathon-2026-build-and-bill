import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ofg.models import EntitlementType, Order  # noqa: E402
from ofg.refund import decide_refund  # noqa: E402
from ofg.store import SqliteLedger  # noqa: E402


def make_order(no, etype, quota=None, created="2026-11-18T00:00:00+00:00",
               amount="20.00"):
    return Order(
        out_trade_no=no, resource_id="r", amount=Decimal(amount),
        entitlement_type=etype, client_session="s", total_quota=quota,
        created_at=created,
    )


class TestRefund(unittest.TestCase):
    def setUp(self):
        self.db = SqliteLedger(":memory:")

    def tearDown(self):
        self.db.close()

    def test_unconsumed_one_off_full_refund(self):
        o = make_order("O1", EntitlementType.ONE_OFF)
        self.db.upsert_order(o)
        self.db.init_entitlement(o)  # 建账但未核销
        r = decide_refund(self.db, {"refund_id": "r1", "out_trade_no": "O1"})
        self.assertEqual(r["decision"], "approve")
        self.assertEqual(r["refund_amount"], "20.00")

    def test_count_pack_partial_refund_ratio(self):
        o = make_order("O2", EntitlementType.COUNT_PACK, quota=10)
        self.db.upsert_order(o)
        self.db.init_entitlement(o)
        self.db.consume_quota("O2", 4)  # 用掉 4/10，应退 60%
        r = decide_refund(self.db, {"refund_id": "r2", "out_trade_no": "O2"})
        self.assertEqual(r["decision"], "approve")
        self.assertEqual(r["refund_amount"], "12.00")

    def test_count_pack_exhausted_rejected(self):
        o = make_order("O3", EntitlementType.COUNT_PACK, quota=3)
        self.db.upsert_order(o)
        self.db.init_entitlement(o)
        self.db.consume_quota("O3", 3)
        r = decide_refund(self.db, {"refund_id": "r3", "out_trade_no": "O3"})
        self.assertEqual(r["decision"], "reject")
        self.assertIn("OFG_2002", r["codes"])

    def test_window_expired_rejected(self):
        o = make_order("O4", EntitlementType.ONE_OFF, created="2020-01-01T00:00:00+00:00")
        self.db.upsert_order(o)
        self.db.init_entitlement(o)
        r = decide_refund(self.db, {"refund_id": "r4", "out_trade_no": "O4"})
        self.assertEqual(r["decision"], "reject")
        self.assertIn("OFG_2001", r["codes"])

    def test_refund_idempotent(self):
        o = make_order("O5", EntitlementType.ONE_OFF)
        self.db.upsert_order(o)
        self.db.init_entitlement(o)
        decide_refund(self.db, {"refund_id": "r5", "out_trade_no": "O5"})
        again = decide_refund(self.db, {"refund_id": "r5", "out_trade_no": "O5"})
        self.assertTrue(again.get("idempotent_hit"))


if __name__ == "__main__":
    unittest.main()

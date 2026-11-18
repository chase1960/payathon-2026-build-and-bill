import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ofg.models import EntitlementType, Order, OrderStatus, PaymentProof  # noqa: E402
from ofg.proof import verify_proof  # noqa: E402


def make_proof(**over):
    base = dict(
        payment_proof="p001", trade_no="t001", client_session="s1",
        out_trade_no="O1", amount=Decimal("9.90"), resource_id="r1", active=True,
    )
    base.update(over)
    return PaymentProof(**base)


def make_order(**over):
    base = dict(
        out_trade_no="O1", resource_id="r1", amount=Decimal("9.90"),
        entitlement_type=EntitlementType.ONE_OFF, client_session="s1",
    )
    base.update(over)
    return Order(**base)


class FakeLedger:
    def __init__(self, used_trades=None, order_trade=None):
        self.used = used_trades or set()
        self.order_trade = order_trade or {}

    def is_trade_used(self, trade_no):
        return trade_no in self.used

    def fulfilled_trade_of_order(self, out_trade_no):
        return self.order_trade.get(out_trade_no)


class TestVerify(unittest.TestCase):
    def test_pass_all_five_checks(self):
        r = verify_proof(make_proof(), make_order(), FakeLedger())
        self.assertTrue(r.passed)
        self.assertIn("OFG_OK", r.codes)

    def test_inactive_rejected(self):
        r = verify_proof(make_proof(active=False), make_order(), FakeLedger())
        self.assertFalse(r.passed)
        self.assertIn("OFG_1001", r.codes)

    def test_amount_mismatch(self):
        r = verify_proof(make_proof(amount=Decimal("8.00")), make_order(), FakeLedger())
        self.assertIn("OFG_1002", r.codes)

    def test_resource_mismatch(self):
        r = verify_proof(make_proof(resource_id="r2"), make_order(), FakeLedger())
        self.assertIn("OFG_1004", r.codes)

    def test_replay_detected(self):
        r = verify_proof(make_proof(), make_order(), FakeLedger(used_trades={"t001"}))
        self.assertIn("OFG_1005", r.codes)
        self.assertFalse(r.passed)

    def test_order_already_fulfilled_by_other_trade(self):
        r = verify_proof(
            make_proof(trade_no="t_new"),
            make_order(),
            FakeLedger(order_trade={"O1": "t_old"}),
        )
        self.assertIn("OFG_1008", r.codes)

    def test_order_missing(self):
        r = verify_proof(make_proof(), None, FakeLedger())
        self.assertIn("OFG_1007", r.codes)

    def test_session_inconsistent_is_warning_not_blocking(self):
        r = verify_proof(make_proof(client_session="sX"), make_order(), FakeLedger())
        self.assertTrue(r.passed)
        self.assertIn("OFG_3003", r.codes)


if __name__ == "__main__":
    unittest.main()

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ofg.reconcile import reconcile  # noqa: E402


class TestReconcile(unittest.TestCase):
    def test_four_diff_types(self):
        local = [
            {"out_trade_no": "A", "amount": "9.90", "status": "paid"},   # 金额不符
            {"out_trade_no": "B", "amount": "5.00", "status": "pending"},  # 状态不符
            {"out_trade_no": "C", "amount": "3.00", "status": "paid"},  # 本地独有
            {"out_trade_no": "D", "amount": "7.00", "status": "paid"},  # 完全匹配
        ]
        bill = [
            {"out_trade_no": "A", "amount": "8.90", "status": "paid", "trade_no": "tA"},
            {"out_trade_no": "B", "amount": "5.00", "status": "paid", "trade_no": "tB"},
            {"out_trade_no": "D", "amount": "7.00", "status": "paid", "trade_no": "tD"},
            {"out_trade_no": "E", "amount": "6.60", "status": "paid", "trade_no": "tE"},
        ]
        r = reconcile(local, bill)
        self.assertFalse(r["balanced"])
        self.assertEqual(len(r["differences"]["amount_mismatch"]), 1)
        self.assertEqual(len(r["differences"]["status_mismatch"]), 1)
        self.assertEqual(len(r["differences"]["local_only"]), 1)
        self.assertEqual(len(r["differences"]["bill_only"]), 1)

    def test_balanced_day(self):
        data = [{"out_trade_no": "A", "amount": "1.00", "status": "paid"}]
        r = reconcile(data, [
            {"out_trade_no": "A", "amount": "1.00", "status": "paid", "trade_no": "t"}
        ])
        self.assertTrue(r["balanced"])
        self.assertEqual(r["settled_total_cny", "1.00")


if __name__ == "__main__":
    unittest.main()

"""Independent arithmetic oracle and adapter representation parity."""
from dataclasses import dataclass
from decimal import Decimal as D
from unittest import TestCase

from mfx_research.shared_h1_features import h1_zone, mean_true_range


@dataclass(frozen=True)
class Row:
    high: object
    low: object
    close: object


class P269Tests(TestCase):
    def setUp(self):
        self.rows = (Row("11","9","10"), Row("15","13","14"),
                     Row("14","12","13"), Row("9","8","8"))
        self.decimal = tuple(Row(D(r.high),D(r.low),D(r.close)) for r in self.rows)

    def test_gap_aware_tr_and_text_decimal_parity(self):
        for rows in (self.rows, self.decimal):
            self.assertEqual(mean_true_range(rows, 3), D(4))
            self.assertEqual(mean_true_range(rows, 2), D(7)/D(2))

    def test_zone_extrema_and_exact_width(self):
        for rows in (self.rows, self.decimal):
            self.assertEqual(h1_zone(rows, 2, D(4), D("0.3"), "B2"),
                             (D(8), D("9.2")))
            self.assertEqual(h1_zone(rows, 2, D(4), D("0.3"), "S2"),
                             (D("12.8"), D(14)))

    def test_mirror_with_same_mean(self):
        reflected = tuple(Row(D(40)-r.low,D(40)-r.high,D(40)-r.close)
                          for r in self.decimal)
        m = mean_true_range(self.decimal, 3)
        self.assertEqual(m, mean_true_range(reflected, 3))
        lo, hi = h1_zone(self.decimal, 3, m, D("0.3"), "B2")
        self.assertEqual(h1_zone(reflected, 3, m, D("0.3"), "S2"),
                         (D(40)-hi,D(40)-lo))

    def test_flat_and_nonpositive_zone_left_to_source_caller(self):
        rows = (Row("1","1","1"),)*4
        self.assertEqual(mean_true_range(rows, 3), D(0))
        self.assertEqual(h1_zone(rows, 3, D(2), D(1), "S2"), (D(-1),D(1)))

    def test_missing_history_rejected(self):
        for p in (0,4,True):
            with self.assertRaisesRegex(ValueError, "P269_COMPLETE"):
                mean_true_range(self.rows,p)
        with self.assertRaisesRegex(ValueError, "P269_COMPLETE"):
            mean_true_range(list(self.rows),3)

    def test_invalid_zone_side_or_window_rejected(self):
        for n,side in ((0,"B2"),(5,"S2"),(2,"B9"),(True,"B2")):
            with self.assertRaisesRegex(ValueError,"P269_EXACT"):
                h1_zone(self.rows,n,D(1),D(1),side)

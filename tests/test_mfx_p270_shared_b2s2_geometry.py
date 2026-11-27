"""P270 boundary and mirror tests on the same calculation used by both adapters."""
from decimal import Decimal as D
from unittest import TestCase

from mfx_research.shared_b2s2_geometry import b2s2_geometry


def calc(first_low="9", first_high="10", first_close="10", last_close="11",
         level="10", tolerance="0", chase="1"):
    return b2s2_geometry("B2", D(first_low), D(first_high), D(first_close),
                         D(last_close), (D("8"), D("9")),
                         None if level is None else D(level), D(tolerance), D(chase))


class P270Tests(TestCase):
    def test_exact_overlap_cross_and_chase_boundary(self):
        self.assertEqual(calc(), (True, True, True))

    def test_touch_not_strict_close_cross(self):
        self.assertEqual(calc(last_close="10"), (True, False, False))
        self.assertEqual(calc(first_close="10.1"), (True, False, False))

    def test_cross_but_chase_excess(self):
        self.assertEqual(calc(last_close="11.01"), (True, True, False))

    def test_near_tolerance_independent_of_cross(self):
        self.assertEqual(calc(first_low="9.01"), (False, True, True))
        self.assertEqual(calc(first_low="9.01", tolerance="0.01"), (True, True, True))

    def test_mirror(self):
        for last in ("10", "11", "11.01"):
            q = D(40)
            got = b2s2_geometry("S2", q-D(10), q-D(9), q-D(10),
                                q-D(last), (q-D(9), q-D(8)), q-D(10), D(0), D(1))
            self.assertEqual(got, calc(last_close=last))

    def test_missing_level_and_invalid_rule(self):
        self.assertEqual(calc(level=None), (True, False, False))
        with self.assertRaisesRegex(ValueError, "P270_B2_S2_ONLY"):
            b2s2_geometry("B9",D(9),D(10),D(10),D(11),(D(8),D(9)),D(10),D(0),D(1))

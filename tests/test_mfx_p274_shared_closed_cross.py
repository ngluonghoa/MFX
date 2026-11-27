"""P274 one price-cross primitive, preserving different prior boundaries."""
from decimal import Decimal as D
from unittest import TestCase

from mfx_research.shared_b2s2_geometry import strict_closed_cross, b2s2_geometry


class P274Tests(TestCase):
    def test_bos_allows_prior_equality_both_sides(self):
        self.assertTrue(strict_closed_cross("B2", D(10), D(11), D(10)))
        self.assertTrue(strict_closed_cross("S2", D(10), D(9), D(10)))

    def test_reclaim_disallows_prior_equality_both_sides(self):
        self.assertFalse(strict_closed_cross("B2", D(10), D(11), D(10), prior_inclusive=False))
        self.assertFalse(strict_closed_cross("S2", D(10), D(9), D(10), prior_inclusive=False))

    def test_reclaim_strict_opposite_then_cross(self):
        self.assertTrue(strict_closed_cross("B2", D(9), D(11), D(10), prior_inclusive=False))
        self.assertTrue(strict_closed_cross("S2", D(11), D(9), D(10), prior_inclusive=False))

    def test_latest_equality_never_cross(self):
        for inclusive in (True, False):
            self.assertFalse(strict_closed_cross("B2", D(9), D(10), D(10), prior_inclusive=inclusive))
            self.assertFalse(strict_closed_cross("S2", D(11), D(10), D(10), prior_inclusive=inclusive))

    def test_already_beyond_never_recross(self):
        self.assertFalse(strict_closed_cross("B2", D(11), D(12), D(10)))
        self.assertFalse(strict_closed_cross("S2", D(9), D(8), D(10)))

    def test_geometry_uses_inclusive_prior_and_invalid_rule_denied(self):
        self.assertEqual(b2s2_geometry("B2", D(9), D(10), D(10), D(11),
                                       (D(8), D(9)), D(10), D(0), D(1)), (True, True, True))
        with self.assertRaisesRegex(ValueError, "P270_B2_S2_ONLY"):
            strict_closed_cross("B1", D(9), D(11), D(10))

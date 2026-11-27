"""P273 shared selection: strict extrema, ambiguity and right window."""
from decimal import Decimal
from unittest import TestCase

from mfx_research.shared_pivot_selection import strict_pivot_indices


def series(*pairs: tuple[str, str]) -> tuple[tuple[Decimal, Decimal], ...]:
    return tuple((Decimal(hi), Decimal(lo)) for hi, lo in pairs)


class P273Tests(TestCase):
    def test_strict_high(self):
        p = series(("5","2"), ("6","3"), ("5","2"))
        self.assertEqual(strict_pivot_indices(p,1,1), ((1,"HIGH"),))

    def test_strict_low(self):
        p = series(("5","2"), ("4","1"), ("5","2"))
        self.assertEqual(strict_pivot_indices(p,1,1), ((1,"LOW"),))

    def test_equal_high_and_low_boundaries_not_pivots(self):
        p = series(("6","2"), ("6","2"), ("5","2"))
        self.assertEqual(strict_pivot_indices(p,1,1), ())

    def test_outside_bar_discarded(self):
        p = series(("5","2"), ("6","1"), ("5","2"))
        self.assertEqual(strict_pivot_indices(p,1,1), ())

    def test_right_window_must_exist_and_width_matters(self):
        p = series(("5","2"), ("5","2"), ("6","3"), ("5","2"), ("7","2"))
        self.assertEqual(strict_pivot_indices(p[:3],1,1), ())
        self.assertEqual(strict_pivot_indices(p,2,2), ())
        self.assertEqual(strict_pivot_indices(p[:4],1,1), ((2,"HIGH"),))

    def test_mirror_and_invalid_width(self):
        p = series(("5","2"), ("6","3"), ("5","2"))
        k = Decimal("20")
        mirror = tuple((k-lo,k-hi) for hi,lo in p)
        self.assertEqual(strict_pivot_indices(mirror,1,1), ((1,"LOW"),))
        with self.assertRaisesRegex(ValueError,"P273_POSITIVE"):
            strict_pivot_indices(p,True,1)

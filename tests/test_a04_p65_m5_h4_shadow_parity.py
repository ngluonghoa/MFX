"""A04/P0.65 hermetic M5->H4 shadow / native parity research tests.

No HTTP, Drive credentials, broker, live signals or source-baseline changes.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from mfx_cache.h4_shadow import (
    CALENDAR, M5_PER_H4, VERSION, compare_shadow_to_native, derive_h4_shadow,
)
from mfx_cache.native_fx_htf import NativeFXBar
from mfx_cache.td_m5_codec import ClosedM5Bar
from mfx_cache.v2_engine import derive_intraday

UTC = timezone.utc
START = datetime(2026, 11, 11, 0, 0, tzinfo=UTC)
ASOF = START + timedelta(hours=8, seconds=16)


def m5(count: int = 48, *, start: datetime = START) -> tuple[ClosedM5Bar, ...]:
    rows = []
    for i in range(count):
        price_step = Decimal(i % 48) / Decimal(100000)
        rows.append(ClosedM5Bar(
            start_utc=(start + timedelta(minutes=5*i)).isoformat(),
            open="1.10000", high=str(Decimal("1.12000") + price_step),
            low=str(Decimal("1.09000") - price_step), close="1.11000",
        ))
    return tuple(rows)


def native(candle: object, **overrides: object) -> NativeFXBar:
    details = dict(
        symbol="EUR/USD", interval="4h",
        native_open_label=getattr(candle, "start_utc").replace("T", " ").replace("+00:00", ""),
        time_reference="UTC_INTRADAY_OPEN",
        exchange_timezone="Australia/Sydney",
        open=getattr(candle, "open"), high=getattr(candle, "high"),
        low=getattr(candle, "low"), close=getattr(candle, "close"),
    )
    details.update(overrides)
    return NativeFXBar(**details)


class H4ShadowDerivationTests(unittest.TestCase):
    def test_exact_48_closed_m5_generate_one_non_native_h4(self) -> None:
        report = derive_h4_shadow(m5(), asof_utc=ASOF)
        self.assertEqual(report.frame, "H4")
        self.assertEqual(len(report.candles), 1)
        c = report.candles[0]
        self.assertEqual(c.start_utc, START.isoformat())
        self.assertEqual(c.end_utc, (START + timedelta(hours=4)).isoformat())
        self.assertEqual(c.source_count, M5_PER_H4)
        self.assertEqual((c.open, c.close), ("1.10000", "1.11000"))
        self.assertEqual((Decimal(c.high), Decimal(c.low)),
                         (Decimal("1.12047"), Decimal("1.08953")))
        self.assertEqual((c.derivation_version, c.calendar_version),
                         (VERSION, CALENDAR))
        self.assertFalse(c.is_source_native)
        self.assertFalse(c.source_numeric_strategy_approved)
        self.assertEqual((report.provider_calls, report.broker_orders), (0, 0))
        self.assertEqual(len(c.source_sha256), 64)

    def test_47_bars_not_h4(self) -> None:
        report = derive_h4_shadow(m5(47), asof_utc=ASOF)
        self.assertFalse(report.candles)
        self.assertEqual(report.skipped_incomplete_windows, (START.isoformat(),))

    def test_hole_not_silently_filled(self) -> None:
        rows = m5()
        report = derive_h4_shadow(rows[:22] + rows[23:], asof_utc=ASOF)
        self.assertEqual(len(report.candles), 0)
        self.assertEqual(len(report.skipped_incomplete_windows), 1)

    def test_two_independent_windows_and_sha(self) -> None:
        report = derive_h4_shadow(m5(96), asof_utc=ASOF)
        self.assertEqual(len(report.candles), 2)
        self.assertNotEqual(report.candles[0].source_sha256,
                            report.candles[1].source_sha256)
        self.assertEqual(report.candles[1].start_utc,
                         (START + timedelta(hours=4)).isoformat())

    def test_midnight_crossing_starts_new_utc_group(self) -> None:
        start = START.replace(hour=20) - timedelta(days=1)
        report = derive_h4_shadow(m5(96, start=start), asof_utc=ASOF)
        self.assertEqual([x.start_utc for x in report.candles],
                         [start.isoformat(), START.isoformat()])

    def test_partial_early_window_cannot_generate_h4(self) -> None:
        report = derive_h4_shadow(m5(47, start=START + timedelta(minutes=5)),
                                  asof_utc=ASOF)
        self.assertFalse(report.candles)

    def test_duplicate_or_reordered_m5_fails_closed(self) -> None:
        rows = m5()
        for bad in (rows + rows[-1:], (rows[1], rows[0]) + rows[2:]):
            with self.assertRaisesRegex(ValueError, "DUPLICATE_OR_UNORDERED"):
                derive_h4_shadow(bad, asof_utc=ASOF)

    def test_future_or_unclosed_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "NOT_SETTLED"):
            derive_h4_shadow(m5(), asof_utc=START + timedelta(hours=4, seconds=14))

    def test_bad_utc_alignment_fails_closed(self) -> None:
        rows = m5()
        bad = replace(rows[10], start_utc=START.replace(minute=51).isoformat())
        with self.assertRaisesRegex(ValueError, "UTC_ALIGNMENT"):
            derive_h4_shadow(rows[:10] + (bad,) + rows[11:], asof_utc=ASOF)

    def test_existing_v2_public_contract_still_requires_native_h4(self) -> None:
        with self.assertRaisesRegex(ValueError, "H4_D1_MUST_BE_PROVIDER_NATIVE"):
            derive_intraday(m5(), "H4", asof_utc=ASOF)
        with self.assertRaisesRegex(ValueError, "H4_D1_MUST_BE_PROVIDER_NATIVE"):
            derive_intraday(m5(), "D1", asof_utc=ASOF)


class H4NativeParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.shadow = derive_h4_shadow(m5(), asof_utc=ASOF)
        self.reference = native(self.shadow.candles[0])

    def test_exact_ohlc_match_never_approves_source_replacement(self) -> None:
        result = compare_shadow_to_native(self.shadow, (self.reference,))
        self.assertEqual((result.matches, result.mismatches, result.missing_native),
                         (1, 0, 0))
        self.assertEqual(result.rows[0].status, "MATCH")
        self.assertFalse(result.fully_verified)
        self.assertFalse(result.source_numeric_strategy_approved)
        self.assertEqual((result.provider_calls, result.drive_writes,
                          result.broker_orders), (0, 0, 0))

    def test_decimal_equivalent_price_strings_are_equal(self) -> None:
        ref = replace(self.reference, open="1.1", close="1.11")
        self.assertEqual(compare_shadow_to_native(self.shadow, (ref,)).matches, 1)

    def test_native_high_low_mismatch_visible(self) -> None:
        ref = replace(self.reference, high="1.13000", low="1.08000")
        out = compare_shadow_to_native(self.shadow, (ref,))
        self.assertEqual((out.matches, out.mismatches), (0, 1))
        self.assertEqual(out.rows[0].differing_fields, ("high", "low"))

    def test_absent_native_is_not_a_match(self) -> None:
        out = compare_shadow_to_native(self.shadow, ())
        self.assertEqual((out.matches, out.missing_native), (0, 1))
        self.assertIsNone(out.rows[0].native_bar_sha256)

    def test_wrong_side_or_provenance_is_rejected(self) -> None:
        for ref in (
            replace(self.reference, price_side="BID"),
            replace(self.reference, is_provider_native=False),
            replace(self.reference, source_numeric_strategy_approved=True),
            replace(self.reference, broker_orders=1),
            replace(self.reference, symbol="GBP/USD"),
            replace(self.reference, exchange_timezone="UTC"),
            replace(self.reference, interval="1day"),
        ):
            with self.subTest(ref=ref):
                with self.assertRaisesRegex(ValueError, "PROVENANCE"):
                    compare_shadow_to_native(self.shadow, (ref,))

    def test_bad_native_h4_grid_is_rejected(self) -> None:
        ref = replace(self.reference, native_open_label="2026-11-11 02:00:00")
        with self.assertRaisesRegex(ValueError, "UTC_GRID"):
            compare_shadow_to_native(self.shadow, (ref,))

    def test_duplicate_native_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            compare_shadow_to_native(self.shadow,
                                     (self.reference, self.reference))

    def test_bad_native_price_is_rejected(self) -> None:
        for val in ("NaN", "-1", "not a price"):
            with self.subTest(val=val):
                with self.assertRaises(ValueError):
                    compare_shadow_to_native(
                        self.shadow, (replace(self.reference, high=val),))

    def test_untrusted_shadow_provenance_rejected(self) -> None:
        bad = replace(self.shadow.candles[0], is_source_native=True)
        with self.assertRaisesRegex(ValueError, "UNTRUSTED_SHADOW"):
            compare_shadow_to_native(
                replace(self.shadow, candles=(bad,)), (self.reference,))

    def test_no_derived_h4_no_false_match(self) -> None:
        out = compare_shadow_to_native(
            derive_h4_shadow(m5(47), asof_utc=ASOF), (self.reference,))
        self.assertEqual(out.rows, ())
        self.assertEqual((out.matches, out.mismatches), (0, 0))
        self.assertFalse(out.fully_verified)


if __name__ == "__main__":
    unittest.main()

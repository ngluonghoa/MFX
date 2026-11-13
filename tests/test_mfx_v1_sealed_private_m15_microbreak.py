"""P0.158: causal M15 microbreak computations on SEALED synthetic fixtures.

These are deterministic synthetic-source tests. No external publisher first-known,
market OOS, source-owner strategy value, bid/ask cost or verified BUY/SELL.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from decimal import Decimal
import json
from unittest import TestCase

from mfx_research.sealed_multibar_private_features import (
    calculate_private_multibar_from_sealed_rows,
)
from mfx_research.sealed_private_pivot_sensitivity import (
    scan_private_sealed_pivot_sensitivity,
)
from mfx_research.sealed_private_m15_microbreak import (
    VERSION, compute_private_sealed_m15_microbreak,
)
from mfx_research.six_tf_readonly_context import (
    build_six_timeframe_readonly_context,
)
from test_mfx_v1_sealed_multibar_private_features import archived
from test_mfx_v1_six_tf_sealed_archive_consumer import ASOF, consume
from test_mfx_v1_manual_signal_only_drive_output import mocked
from tools.run_mfx_v1_manual_drive_six_tf import safe_summary


def manufactured(*, direction="FLAT", prev_already_crossed=False):
    """Return correct typed closed-source receipts from *synthetic* M5."""
    m5, h4, d1, _ = archived()
    rows = list(m5)
    if direction == "UP":
        rows[-12] = replace(rows[-12], high="1.1050")
        if prev_already_crossed:
            rows[-4] = replace(
                rows[-4], high="1.1080", close="1.1060",
            )
        rows[-1] = replace(
            rows[-1], high="1.1090", close="1.1070",
        )
    elif direction == "DOWN":
        rows[-12] = replace(rows[-12], low="1.0950")
        rows[-1] = replace(
            rows[-1], low="1.0920", close="1.0940",
        )
    elif direction != "FLAT":
        raise ValueError("TEST_UNKNOWN_DIRECTION")
    source = tuple(rows)
    tech = build_six_timeframe_readonly_context(
        source[-12:], h4, d1, asof_utc=ASOF,
    )
    multi = calculate_private_multibar_from_sealed_rows(
        source, h4, d1, tech, asof_utc=ASOF,
    )
    pivot = scan_private_sealed_pivot_sensitivity(multi, tech)
    return multi, tech, pivot


def actual(data=None):
    r = consume() if data is None else data
    return compute_private_sealed_m15_microbreak(
        r.private_multibar, r.technical, r.private_pivot_sensitivity,
    )


class MfxP158SealedM15MicroBreakTests(TestCase):
    def test_01_actual_consumer_computes_but_does_not_signal(self):
        r = consume()
        a = actual(r)
        self.assertEqual(a.version, VERSION)
        self.assertEqual((a.action, a.stage), ("NO_SIGNAL", "UNVERIFIED"))
        self.assertFalse(a.may_trade)
        self.assertFalse(a.may_publish_prices_or_signals)
        self.assertEqual(a.asof_utc, r.technical.asof_utc)

    def test_02_both_profiles_use_sim_windows_not_approvals(self):
        a = actual()
        self.assertEqual(
            tuple((x.left_bars, x.right_bars) for x in a.profiles),
            ((1, 1), (2, 2)),
        )
        self.assertTrue(all(not x.source_numeric_rule_approved
                            for x in a.profiles))
        self.assertFalse(a.original_b2_s2_approved)

    def test_03_flat_source_has_no_experimental_break(self):
        a = actual()
        self.assertTrue(all(x.experimental_cross == "NO_RESEARCH_EVENT"
                            for x in a.profiles))

    def test_04_prior_confirmed_high_cross_is_real_decimal_arithmetic(self):
        multi, tech, pivots = manufactured(direction="UP")
        a = compute_private_sealed_m15_microbreak(multi, tech, pivots)
        self.assertEqual(
            tuple(x.experimental_cross for x in a.profiles),
            ("EXPERIMENTAL_UP_CROSS", "EXPERIMENTAL_UP_CROSS"),
        )
        self.assertTrue(all(x.referenced_mid_pivot == Decimal("1.1050")
                            for x in a.profiles))
        self.assertTrue(all(x.latest_closed_mid_price == Decimal("1.1070")
                            for x in a.profiles))
        self.assertTrue(all(x.prior_right_closed_high_available
                            for x in a.profiles))

    def test_05_prior_confirmed_low_cross_is_real_decimal_arithmetic(self):
        multi, tech, pivots = manufactured(direction="DOWN")
        a = compute_private_sealed_m15_microbreak(multi, tech, pivots)
        self.assertEqual(
            tuple(x.experimental_cross for x in a.profiles),
            ("EXPERIMENTAL_DOWN_CROSS", "EXPERIMENTAL_DOWN_CROSS"),
        )
        self.assertTrue(all(x.referenced_mid_pivot == Decimal("1.0950")
                            for x in a.profiles))

    def test_06_cross_is_not_repeated_when_previous_close_was_above(self):
        multi, tech, pivots = manufactured(
            direction="UP", prev_already_crossed=True,
        )
        a = compute_private_sealed_m15_microbreak(multi, tech, pivots)
        self.assertTrue(all(x.experimental_cross == "NO_RESEARCH_EVENT"
                            for x in a.profiles))

    def test_07_known_pivot_must_precede_latest_bar_open(self):
        multi, tech, pivots = manufactured(direction="UP")
        a = compute_private_sealed_m15_microbreak(multi, tech, pivots)
        self.assertTrue(all(x.latest_candle_closed_utc ==
                            "2026-11-12T12:00:00+00:00"
                            for x in a.profiles))
        self.assertTrue(all(x.status ==
                            "PRIVATE_PRIOR_CONFIRMED_M15_LEVEL_EVALUATED"
                            for x in a.profiles))

    def test_08_stale_m5_m15_never_borrow_old_microbreak(self):
        r = consume(asof=ASOF + timedelta(minutes=18))
        a = actual(r)
        self.assertIn("M15", a.frames_missing_or_stale)
        self.assertTrue(all(x.status == "M15_MISSING_OR_STALE"
                            and x.experimental_cross == "NO_RESEARCH_EVENT"
                            for x in a.profiles))

    def test_09_forged_approval_denied(self):
        r = consume()
        multi = replace(r.private_multibar,
                        original_forex_numeric_source_approved=True)
        with self.assertRaisesRegex(ValueError, "RIGHTS_OR_EXECUTION"):
            compute_private_sealed_m15_microbreak(
                multi, r.technical, r.private_pivot_sensitivity,
            )

    def test_10_forged_pivot_cannot_be_passed_to_research(self):
        r = consume()
        forged = replace(r.private_pivot_sensitivity, studied=())
        with self.assertRaisesRegex(ValueError, "PIVOT_RESULT"):
            compute_private_sealed_m15_microbreak(
                r.private_multibar, r.technical, forged,
            )

    def test_11_modified_private_source_sha_cannot_pass(self):
        r = consume()
        multi = r.private_multibar
        frames = list(multi.private_closed_histories)
        name, rows = frames[0]
        frames[0] = (name, (replace(rows[0], high="1.1100"),) + rows[1:])
        with self.assertRaisesRegex(ValueError, "PRIVATE_INPUT_SHA"):
            compute_private_sealed_m15_microbreak(
                replace(multi, private_closed_histories=tuple(frames)),
                r.technical, r.private_pivot_sensitivity,
            )

    def test_12_exact_typed_receipts_not_dict_or_manual_guess(self):
        r = consume()
        for bad in (None, {}, []):
            with self.subTest(bad=bad), self.assertRaisesRegex(
                    TypeError, "EXACT_SEALED_TYPED"):
                compute_private_sealed_m15_microbreak(
                    bad, r.technical, r.private_pivot_sensitivity,
                )

    def test_13_private_result_immutable(self):
        a = actual()
        with self.assertRaises(FrozenInstanceError):
            a.action = "BUY"
        with self.assertRaises(FrozenInstanceError):
            a.profiles[0].experimental_cross = "BUY"

    def test_14_private_repr_cannot_leak_direction_or_price(self):
        a = actual()
        self.assertNotIn("experimental_cross", repr(a))
        self.assertNotIn("latest_closed_mid_price", repr(a))

    def test_15_no_extra_get_write_order_or_quote(self):
        a = actual()
        self.assertEqual(
            (a.provider_requests, a.drive_gets_added,
             a.drive_writes, a.broker_orders), (0, 0, 0, 0),
        )
        self.assertFalse(a.real_bidask_sl_tp_net_rr_approved)
        self.assertFalse(a.source_d1_session_or_revision_qualified)

    def test_16_source_only_m15_no_fake_h4_d1_confirmation(self):
        a = actual()
        self.assertTrue(all(x.source_price_side == "MID"
                            for x in a.profiles))
        self.assertFalse(a.publisher_first_known_verified)
        self.assertFalse(a.historical_oos_accepted)

    def test_17_safe_report_cannot_publish_experimental_cross(self):
        report = safe_summary(mocked(), drive_gets=0)
        encoded = json.dumps(report, sort_keys=True)
        for token in (
            "EXPERIMENTAL_UP_CROSS", "EXPERIMENTAL_DOWN_CROSS",
            "referenced_mid_pivot", "latest_closed_mid_price",
            "1.1050", "1.1070",
        ):
            self.assertNotIn(token, encoded)
        self.assertEqual(report["action"], "NO_SIGNAL")

    def test_18_safe_report_m15_stale_marked(self):
        r = mocked(asof=ASOF + timedelta(minutes=18))
        report = safe_summary(r, drive_gets=3)
        self.assertEqual(report["action"], "NO_SIGNAL")

    def test_19_replay_is_deterministic(self):
        self.assertEqual(actual(), actual())

    def test_20_no_signed_owner_source_from_private_math(self):
        a = actual()
        self.assertFalse(a.independently_licensed_provider_data)
        self.assertFalse(a.original_b2_s2_approved)
        self.assertFalse(a.may_publish_prices_or_signals)

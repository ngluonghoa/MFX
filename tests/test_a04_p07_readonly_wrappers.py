"""A04/P0.7 test exact CI-only pure delegations, not plugin integration."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from copy import deepcopy
import json
import unittest

from forex_trading.cache_indicators import ema_full, ema_recompute
from forex_trading.catalog import ZONES, catalog_counts
from forex_trading.market_data import evaluate_closed_bar
from forex_trading.model import ActionIntent
from forex_trading.quotes import (
    Quote, QuoteQuality, indicative_price,
)
from tools.a04_p07_readonly_wrappers import (
    readonly_asof, readonly_bar, readonly_catalog_counts,
    readonly_catalog_validate, readonly_ema, readonly_ema_recompute,
    readonly_quote,
)
from tools.compare_a04_p07_wrapper_golden import (
    BASELINE, compare_wrapped, validate_wrapped_snapshot,
    verify_pinned_comparison,
)
from tools.render_a04_p07_wrapper_golden import render

T = datetime(2026, 11, 7, tzinfo=timezone.utc)


class ReadOnlyWrapperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.quote = Quote(
            "SYNTH_ONLY", "rev-01", T, T + timedelta(seconds=1),
            Decimal("1.222"), Decimal("1.223"), QuoteQuality.VERIFIED,
        )

    def test_four_quote_intents_passthrough_equal_frozen_source(self) -> None:
        for intent in ActionIntent:
            with self.subTest(intent=intent):
                when = T + timedelta(seconds=2)
                age = timedelta(seconds=10)
                self.assertEqual(
                    readonly_quote(self.quote, intent, when, age),
                    indicative_price(self.quote, intent, when, age),
                )

    def test_quote_future_known_fails_with_exact_original_reason(self) -> None:
        for func in (readonly_quote, indicative_price):
            with self.assertRaisesRegex(ValueError, "not yet known"):
                func(self.quote, ActionIntent.ENTRY_LONG, T, timedelta(seconds=10))

    def test_quote_unverified_is_not_promoted(self) -> None:
        q = replace(self.quote, quality=QuoteQuality.UNVERIFIED)
        for func in (readonly_quote, indicative_price):
            with self.assertRaisesRegex(ValueError, "unverified"):
                func(q, ActionIntent.ENTRY_SHORT, T + timedelta(seconds=2),
                     timedelta(seconds=10))

    def test_indicators_preserve_precise_decimal_recompute(self) -> None:
        series = (Decimal("1.01"), Decimal("1.02"), Decimal("1.03"))
        original = ema_full(series, 3)
        self.assertEqual(readonly_ema(series, 3), original)
        self.assertEqual(
            readonly_ema_recompute(series, 3, original, 2),
            ema_recompute(series, 3, original, 2),
        )

    def test_ema_invalid_period_does_not_succeed_in_wrapper(self) -> None:
        with self.assertRaisesRegex(ValueError, "EMA period"):
            readonly_ema((Decimal("1.1"),), 0)

    def test_catalog_is_taxonomy_not_signal_detection(self) -> None:
        self.assertEqual(readonly_catalog_counts(ZONES), catalog_counts(ZONES))
        self.assertIsNone(readonly_catalog_validate(ZONES))
        self.assertEqual(len(ZONES), 18)

    def test_catalog_duplicate_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Duplicate zone"):
            readonly_catalog_validate(ZONES + (ZONES[0],))

    def test_missing_bar_is_not_treated_as_zero_volume(self) -> None:
        when = T + timedelta(minutes=15)
        self.assertEqual(readonly_bar(None, when),
                         evaluate_closed_bar(None, when))
        self.assertFalse(readonly_bar(None, when).permission_to_trade)

    def test_missing_revision_is_not_fabricated(self) -> None:
        self.assertIsNone(readonly_asof((), T))

    def test_rendered_synthetic_wrapper_matches_direct_core_34_cases(self) -> None:
        from pathlib import Path
        source = Path(__file__).resolve().parents[1] / "src"
        result = render(source)
        self.assertEqual(result["scenario_count"], 34)
        self.assertTrue(result["wrapper_matches_direct_source"])
        self.assertFalse(result["may_release_or_trade"])
        self.assertEqual(len(validate_wrapped_snapshot(result)), 34)

    def test_exact_comparison_denies_modified_error_reason(self) -> None:
        from copy import deepcopy
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "src"
        original = render(root)
        forged = deepcopy(original)
        target = next(x for x in forged["scenarios"]
                      if x["id"] == "quote.reject_stale")
        target["outcome"]["reason"] = "WRAPPER-SILENTLY-PROMOTED"
        with self.assertRaisesRegex(ValueError, "A04P07_FROZEN_FOREX_VS_MFX_WRAPPER_DRIFT"):
            compare_wrapped(original, forged)

    def _pinned_receipt(self):
        pinned = json.loads(BASELINE.read_text(encoding="utf-8"))
        receipt = {
            **pinned["observed"],
            "frozen_forex_commit":
                "7e1c1c012b1b189be5ad7b9d07756eac012a8309",
            "wrapper_vs_direct_pass": True,
            "original_forex_vs_mfx_pass": True,
            "source_module_edits": False,
            "plugin_loaded": False,
            "real_provider_used": False,
            "numerical_detector_or_tp_tested": False,
            "may_release_or_trade": False,
        }
        return receipt, pinned

    def test_pinned_receipt_matches_source_observation(self) -> None:
        receipt, pinned = self._pinned_receipt()
        self.assertEqual(receipt["case_count"], 34)
        verify_pinned_comparison(receipt, pinned)

    def test_pinned_receipt_rejects_case_sha_tamper(self) -> None:
        receipt, pinned = self._pinned_receipt()
        forged = dict(receipt, case_sha256="f"*64)
        with self.assertRaisesRegex(ValueError, "A04P07_PINNED_WRAPPER_DRIFT"):
            verify_pinned_comparison(forged, pinned)

    def test_pinned_receipt_rejects_full_snapshot_sha_tamper(self) -> None:
        receipt, pinned = self._pinned_receipt()
        forged = dict(receipt, full_snapshot_sha256="f"*64)
        with self.assertRaisesRegex(ValueError, "A04P07_PINNED_WRAPPER_DRIFT"):
            verify_pinned_comparison(forged, pinned)

    def test_pinned_receipt_cannot_grant_plugin_or_trading(self) -> None:
        receipt, pinned = self._pinned_receipt()
        for flag in ("plugin_loaded", "real_provider_used", "may_release_or_trade"):
            with self.subTest(flag=flag):
                forged = dict(receipt, **{flag: True})
                with self.assertRaisesRegex(ValueError, "A04P07_FORBIDDEN_AUTHORITY"):
                    verify_pinned_comparison(forged, pinned)

    def test_pinned_receipt_rejects_policy_baseline_weakening(self) -> None:
        receipt, pinned = self._pinned_receipt()
        forged = deepcopy(pinned)
        forged["required_false_flags"] = []
        with self.assertRaisesRegex(ValueError, "A04P07_BASELINE_AUTHORITY_WEAKENED"):
            verify_pinned_comparison(receipt, forged)

    def test_exact_comparison_denies_fake_vendor_permission(self) -> None:
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "src"
        original = render(root)
        forged = dict(original, real_provider_io=True)
        with self.assertRaisesRegex(ValueError, "A04P07_UNAUTHORIZED_WRAPPER_AUTHORITY"):
            validate_wrapped_snapshot(forged)


if __name__ == "__main__":
    unittest.main()

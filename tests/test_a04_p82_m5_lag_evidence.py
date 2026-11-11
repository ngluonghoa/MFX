"""Offline A04/P0.82 M5 audit lag negative evidence tests."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from tools.mfx_m5_lag_evidence import (
    M5LagObservation, classify_m5_lag, SCHEMA,
)

UTC = timezone.utc
OPEN = datetime(2026, 11, 11, 16, 0, tzinfo=UTC)


def sample(**kw):
    base = M5LagObservation(
        audit_at_utc=OPEN + timedelta(minutes=13),
        last_closed_bar_open_utc=OPEN,
        expected_closed_bar_open_utc=OPEN + timedelta(minutes=5),
        manifest_pairs=21, closed_bars=252,
        full_history_audited=False,
    )
    return replace(base, **kw)


class M5LagEvidenceTests(TestCase):
    def test_01_single_lag_is_not_outage(self):
        r = classify_m5_lag(sample(), as_of_utc=OPEN + timedelta(minutes=13))
        self.assertEqual(r.status, "LAG_OBSERVED_NOT_OUTAGE_PROOF")
        self.assertEqual(r.observed_lag_bars, 1)
        self.assertFalse(r.outage_proven)

    def test_02_old_snapshot_needs_recheck(self):
        r = classify_m5_lag(sample(), as_of_utc=OPEN + timedelta(hours=4))
        self.assertEqual(r.status, "STALE_AUDIT_RECHECK_REQUIRED")

    def test_03_publication_grace(self):
        r = classify_m5_lag(sample(
            audit_at_utc=OPEN + timedelta(minutes=10, seconds=30)),
            as_of_utc=OPEN + timedelta(minutes=10, seconds=31))
        self.assertEqual(r.status, "PUBLICATION_WINDOW_RECHECK_REQUIRED")

    def test_04_matching_tail_not_full_history(self):
        r = classify_m5_lag(sample(
            last_closed_bar_open_utc=OPEN + timedelta(minutes=5)),
            as_of_utc=OPEN + timedelta(minutes=13))
        self.assertEqual(r.status, "TAIL_MATCH_ONLY")
        self.assertFalse(r.complete_history_verified)

    def test_05_full_history_claim_is_only_caller_supplied(self):
        r = classify_m5_lag(sample(full_history_audited=True),
                            as_of_utc=OPEN + timedelta(minutes=13))
        self.assertTrue(r.complete_history_verified)
        self.assertFalse(r.outage_proven)

    def test_06_future_audit_rejected(self):
        with self.assertRaises(ValueError):
            classify_m5_lag(sample(), as_of_utc=OPEN)

    def test_07_future_bar_rejected(self):
        with self.assertRaises(ValueError):
            classify_m5_lag(sample(
                expected_closed_bar_open_utc=OPEN + timedelta(hours=1)),
                as_of_utc=OPEN + timedelta(hours=2))

    def test_08_off_grid_bar_rejected(self):
        with self.assertRaises(ValueError):
            classify_m5_lag(sample(
                last_closed_bar_open_utc=OPEN + timedelta(minutes=1)),
                as_of_utc=OPEN + timedelta(minutes=13))

    def test_09_inconsistent_count_rejected(self):
        with self.assertRaises(ValueError):
            classify_m5_lag(sample(closed_bars=253),
                            as_of_utc=OPEN + timedelta(minutes=13))

    def test_10_boolean_count_rejected(self):
        with self.assertRaises(ValueError):
            classify_m5_lag(sample(manifest_pairs=True),
                            as_of_utc=OPEN + timedelta(minutes=13))

    def test_11_naive_clock_rejected(self):
        with self.assertRaises(ValueError):
            classify_m5_lag(sample(),
                            as_of_utc=datetime(2026, 11, 11, 16, 13))

    def test_12_no_mutations_or_trading(self):
        r = classify_m5_lag(sample(), as_of_utc=OPEN + timedelta(minutes=13))
        self.assertEqual((r.vendor_calls, r.drive_writes, r.broker_orders),
                         (0, 0, 0))
        self.assertFalse(r.source_substitution_authorized)
        self.assertFalse(r.live_v2_authorized)
        self.assertEqual(r.schema, SCHEMA)

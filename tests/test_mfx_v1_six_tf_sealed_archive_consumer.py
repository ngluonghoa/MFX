"""MFX v1: sealed source cache -> 6TF read-only, all offline, no OAuth."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest import TestCase
from unittest.mock import patch

from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.native_htf_archive import plan_native_sealed
from mfx_cache.td_m5_codec import ClosedM5Bar, digest
from mfx_cache.v2_batch_commit import _make_plan
from mfx_research.six_tf_sealed_archive_consumer import (
    D1_KNOWN_SOURCE_REVISION_HOLD, D1_HOLD_PUBLIC_STATUS,
    D1_KNOWN_SOURCE_REVISION_INCIDENT, SyntheticFixturePins,
    _m5_pinned_rows, consume_sealed_archives_for_six_tf,
)

UTC = timezone.utc
ASOF = datetime(2026, 11, 12, 12, 1, tzinfo=UTC)
SOURCE = datetime(2026, 11, 12, 10, tzinfo=UTC)
PRICES = {"open": "1.1000", "high": "1.1020", "low": "1.0990",
          "close": "1.1010"}


class ReadOnlyStore:
    """No write API, even in the test-double contract."""

    def __init__(self) -> None:
        self.objects: dict[str, dict[str, dict[str, Any]]] = {
            "manifest": {}, "chunk": {},
        }

    def list_names(self, bucket: str) -> tuple[str, ...]:
        return tuple(sorted(self.objects[bucket]))

    def read(self, bucket: str, name: str) -> dict[str, Any]:
        return copy.deepcopy(self.objects[bucket][name])


def _seed_m5(store: ReadOnlyStore, count: int = 2) -> SyntheticFixturePins:
    previous = None
    saved = []
    for i in range(count):
        hour = SOURCE + timedelta(hours=i)
        bars = tuple(ClosedM5Bar(
            start_utc=(hour + timedelta(minutes=5*n)).isoformat(),
            **PRICES,
        ) for n in range(12))
        plan = _make_plan(
            previous, hour_utc=hour.isoformat(),
            bars=bars, now_utc=ASOF)
        store.objects["manifest"][plan.manifest_name] = copy.deepcopy(
            plan.manifest)
        store.objects["chunk"][plan.chunk_name] = copy.deepcopy(plan.chunk)
        saved.append(plan)
        previous = plan.manifest
    return SyntheticFixturePins(
        root_hour_utc=saved[0].hour_utc,
        root_sha256=saved[0].manifest_sha256,
        checkpoint_hour_utc=saved[-1].hour_utc,
        checkpoint_sha256=saved[-1].manifest_sha256,
        checkpoint_pairs=count,
    )


def _native(interval: str, labels: tuple[str, ...]) -> NativeFXBatch:
    axis = ("UTC_INTRADAY_OPEN" if interval == "4h"
            else "EXCHANGE_LOCAL_SESSION_DATE")
    return NativeFXBatch(
        symbol="EUR/USD", interval=interval,
        exchange_timezone="Australia/Sydney",
        time_reference=axis, incomplete_excluded=0,
        closed_bars=tuple(NativeFXBar(
            symbol="EUR/USD", interval=interval,
            native_open_label=label, time_reference=axis,
            exchange_timezone="Australia/Sydney",
            exchange_timezone_origin="DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT",
            **PRICES,
        ) for label in labels),
    )


def _seed_native(
    store: ReadOnlyStore, interval: str, labels: tuple[str, ...],
) -> None:
    plan = plan_native_sealed(_native(interval, labels), previous=None)
    if plan is None:
        raise AssertionError("synthetic fixture did not create a plan")
    store.objects["manifest"][plan.manifest_name] = copy.deepcopy(
        plan.manifest)
    store.objects["chunk"][plan.chunk_name] = copy.deepcopy(plan.chunk)


def fixtures():
    m5, h4, d1 = ReadOnlyStore(), ReadOnlyStore(), ReadOnlyStore()
    pins = _seed_m5(m5)
    _seed_native(h4, "4h", ("2026-11-12 08:00:00",))
    _seed_native(d1, "1day", ("2026-11-11",))
    return m5, h4, d1, pins


def consume(
    m5=None, h4=None, d1=None, pins=None, *, asof=ASOF,
):
    if m5 is None:
        m5, h4, d1, pins = fixtures()
    return consume_sealed_archives_for_six_tf(
        m5, h4, d1, asof_utc=asof, fixture_pins=pins)


class SealedSixTFConsumerTests(TestCase):
    def test_01_composes_all_six_frames_after_full_sha_audits(self):
        result = consume()
        self.assertEqual(result.technical.total_frames, 6)
        self.assertTrue(result.technical.research_technical_context_complete)
        self.assertEqual(tuple(x.frame for x in result.technical.frames),
                         ("M5", "M15", "M30", "H1", "H4", "D1"))

    def test_02_real_existing_3_6_12_derivation_is_used(self):
        result = consume()
        self.assertEqual([x.source_bar_count for x in result.technical.frames],
                         [1, 3, 6, 12, 1, 1])
        self.assertTrue(result.technical.frames[4].native)
        self.assertEqual(result.technical.frames[5].time_basis,
                         "EXCHANGE_LOCAL_SESSION_DATE")
        self.assertIsNone(result.technical.frames[5].end_utc)

    def test_03_all_three_sealed_sha_chains_and_tips(self):
        result = consume()
        self.assertTrue(result.all_three_bounded_sha_chains_verified)
        self.assertEqual((result.m5_manifest_pairs_full_sha,
                          result.h4_manifest_pairs_full_sha,
                          result.d1_manifest_pairs_full_sha), (2, 1, 1))
        for value in (result.m5_manifest_tip_sha256,
                      result.h4_manifest_tip_sha256,
                      result.d1_manifest_tip_sha256):
            self.assertEqual(len(value), 64)

    def test_04_test_fixture_pins_cannot_be_reviewed_source_pins(self):
        self.assertFalse(consume().github_reviewed_m5_anchors_checked)

    def test_05_no_numeric_or_account_licence_promotion(self):
        r = consume()
        self.assertEqual(r.technical.action, "NO_SIGNAL")
        self.assertEqual(r.technical.stage, "UNVERIFIED")
        self.assertFalse(r.storage_reader_identity_independently_attested)
        self.assertFalse(r.provider_account_data_rights_verified)
        self.assertFalse(r.source_first_known_time_proven)
        self.assertFalse(r.independent_monotonic_witness_verified)
        self.assertFalse(r.source_numeric_entry_rules_approved)
        self.assertFalse(r.bidask_costs_and_sl_tp_net_rr_approved)
        self.assertFalse(r.may_publish_buy_sell)
        self.assertFalse(r.may_trade)

    def test_06_no_vendor_get_or_drive_mutation_or_broker(self):
        m, h, d, p = fixtures()
        old = [copy.deepcopy(s.objects) for s in (m, h, d)]
        r = consume(m, h, d, p)
        self.assertEqual((r.provider_price_calls, r.drive_cache_writes,
                          r.broker_orders), (0, 0, 0))
        self.assertEqual([s.objects for s in (m, h, d)], old)
        self.assertFalse(hasattr(m, "put_if_absent"))

    def test_07_m5_early_raw_price_change_denied(self):
        m, h, d, p = fixtures()
        key = sorted(m.objects["chunk"])[0]
        m.objects["chunk"][key]["bars"][0]["close"] = "1.1005"
        with self.assertRaises(ValueError):
            consume(m, h, d, p)

    def test_08_m5_newest_raw_price_change_denied(self):
        m, h, d, p = fixtures()
        key = sorted(m.objects["chunk"])[-1]
        m.objects["chunk"][key]["bars"][0]["close"] = "1.1005"
        with self.assertRaises(ValueError):
            consume(m, h, d, p)

    def test_09_m5_history_rewritten_denied(self):
        m, h, d, p = fixtures()
        key = sorted(m.objects["manifest"])[0]
        m.objects["manifest"][key]["total_batches"] = 99
        with self.assertRaises(ValueError):
            consume(m, h, d, p)

    def test_10_m5_checkpoint_rollback_denied(self):
        m, h, d, p = fixtures()
        name = sorted(m.objects["manifest"])[-1]
        chunk = m.objects["manifest"][name]["chunk_name"]
        del m.objects["manifest"][name]
        del m.objects["chunk"][chunk]
        with self.assertRaisesRegex(ValueError, "ROLLBACK"):
            consume(m, h, d, p)

    def test_11_m5_orphan_chunk_denied(self):
        m, h, d, p = fixtures()
        m.objects["chunk"]["fake_orphan.json"] = {}
        with self.assertRaisesRegex(ValueError, "ROLLBACK"):
            consume(m, h, d, p)

    def test_12_h4_sha_tampering_denied(self):
        m, h, d, p = fixtures()
        key = next(iter(h.objects["chunk"]))
        h.objects["chunk"][key]["bars"][0]["high"] = "1.9"
        with self.assertRaises(ValueError):
            consume(m, h, d, p)

    def test_13_d1_sha_tampering_denied(self):
        m, h, d, p = fixtures()
        key = next(iter(d.objects["chunk"]))
        d.objects["chunk"][key]["bars"][0]["low"] = "0.5"
        with self.assertRaises(ValueError):
            consume(m, h, d, p)

    def test_14_missing_native_manifest_denied(self):
        m, h, d, p = fixtures()
        h.objects["manifest"].clear()
        with self.assertRaisesRegex(ValueError, "INCOMPLETE"):
            consume(m, h, d, p)

    def test_15_native_orphan_chunk_denied(self):
        m, h, d, p = fixtures()
        d.objects["chunk"]["orphan"] = {}
        with self.assertRaisesRegex(ValueError, "UNCOMMITTED"):
            consume(m, h, d, p)

    def test_16_missing_native_chunk_denied(self):
        m, h, d, p = fixtures()
        d.objects["chunk"].clear()
        with self.assertRaises(ValueError):
            consume(m, h, d, p)

    def test_17_stale_latest_m5_research_no_signal(self):
        m, h, d, p = fixtures()
        result = consume(m, h, d, p, asof=ASOF + timedelta(minutes=11))
        self.assertIn("M5", result.technical.missing_or_stale_frames)
        self.assertEqual(result.technical.action, "NO_SIGNAL")

    def test_18_stale_h4_retains_missing_reason(self):
        m, h, d, p = fixtures()
        h.objects = {"manifest": {}, "chunk": {}}
        _seed_native(h, "4h", ("2026-11-12 00:00:00",))
        result = consume(m, h, d, p)
        self.assertIn("H4", result.technical.missing_or_stale_frames)
        self.assertFalse(result.may_publish_buy_sell)

    def test_19_stale_sydney_local_d1_retains_missing_reason(self):
        m, h, d, p = fixtures()
        d.objects = {"manifest": {}, "chunk": {}}
        _seed_native(d, "1day", ("2026-11-07",))
        result = consume(m, h, d, p)
        self.assertIn("D1", result.technical.missing_or_stale_frames)

    def test_20_reject_naive_decision_asof(self):
        m, h, d, p = fixtures()
        with self.assertRaisesRegex(ValueError, "EXACT_UTC_ASOF"):
            consume(m, h, d, p, asof=datetime(2026, 11, 12, 12, 1))

    def test_21_reject_wrong_timezone_decision_asof(self):
        m, h, d, p = fixtures()
        with self.assertRaisesRegex(ValueError, "EXACT_UTC_ASOF"):
            consume(m, h, d, p,
                    asof=ASOF.astimezone(timezone(timedelta(hours=7))))

    def test_22_default_reviewed_pins_deny_synthetic_source(self):
        m, h, d, _ = fixtures()
        with self.assertRaisesRegex(ValueError, "ROLLBACK_OR_UNVERIFIABLE_BOUND"):
            consume_sealed_archives_for_six_tf(
                m, h, d, asof_utc=ASOF)

    def test_23_forged_fixture_pins_type_denied(self):
        m, h, d, _ = fixtures()
        with self.assertRaisesRegex(ValueError, "SYNTHETIC_PINS_TYPE"):
            consume(m, h, d, pins={})

    def test_24_wrong_native_source_interval_denied(self):
        m, h, d, p = fixtures()
        h.objects = {"manifest": {}, "chunk": {}}
        _seed_native(h, "1day", ("2026-11-11",))
        with self.assertRaises(ValueError):
            consume(m, h, d, p)

    def test_25_latest_native_h4_was_truly_closed_asof(self):
        r = consume()
        h4 = r.technical.frames[4]
        self.assertEqual(h4.source_label, "2026-11-12 08:00:00")
        self.assertEqual(h4.end_utc, "2026-11-12T12:00:00+00:00")

    def test_26_first_known_and_historical_replay_never_inferred(self):
        r = consume()
        self.assertFalse(r.historical_asof_replay_proven)
        self.assertFalse(r.technical.historical_asof_replay_proven)
        self.assertFalse(r.technical.archive_sha_independently_verified)
        self.assertEqual(r.status,
                         "SEALED_READONLY_CACHE_TECHNICAL_RESEARCH_ONLY_NO_SIGNAL")

    def test_27_out_of_scope_future_h4_cannot_be_composed(self):
        m, h, d, p = fixtures()
        h.objects = {"manifest": {}, "chunk": {}}
        _seed_native(h, "4h", ("2026-11-12 12:00:00",))
        with self.assertRaisesRegex(ValueError, "NATIVE_H4_OPEN_OR_FUTURE"):
            consume(m, h, d, p)

    def test_28_unlisted_native_scope_is_not_accepted(self):
        m, h, d, p = fixtures()
        d.objects["manifest"]["not_a_native_manifest"] = {}
        with self.assertRaises(ValueError):
            consume(m, h, d, p)

    def test_29_cache_evidence_is_deterministic(self):
        r1, r2 = consume(), consume()
        self.assertEqual(r1, r2)

    def test_30_existing_six_tf_receipt_still_never_authenticates_rights(self):
        r = consume()
        self.assertTrue(r.technical.research_technical_context_complete)
        self.assertFalse(r.technical.source_feed_subscription_verified)
        self.assertFalse(r.technical.forex_1to1_numerical_parity_verified)
        self.assertFalse(r.technical.entry_sl_tp_net_rr_approved)

    @staticmethod
    def _reviewed_mode_with_in_memory_pinned_fixture(
        m: ReadOnlyStore, h: ReadOnlyStore, d: ReadOnlyStore,
        pins: SyntheticFixturePins,
    ):
        """Mock ONLY external M5 anchor validation to exercise real-only path.

        NOT a real producer/source proof. Native H4/D1 SHA checks remain real.
        """
        bars, evidence = _m5_pinned_rows(
            m, asof_utc=ASOF, fixture_pins=pins,
        )
        with patch(
            "mfx_research.six_tf_sealed_archive_consumer._m5_pinned_rows",
            return_value=(bars, evidence),
        ):
            return consume_sealed_archives_for_six_tf(
                m, h, d, asof_utc=ASOF,
            )

    def test_31_known_source_d1_hold_is_versioned_no_silent_timeout(self):
        self.assertIs(D1_KNOWN_SOURCE_REVISION_HOLD, True)
        self.assertIn("2026_11_11", D1_KNOWN_SOURCE_REVISION_INCIDENT)
        self.assertIn("QUARANTINE", D1_HOLD_PUBLIC_STATUS)

    def test_32_original_sha_audited_archive_is_still_d1_hold(self):
        m, h, d, pins = fixtures()
        r = self._reviewed_mode_with_in_memory_pinned_fixture(m, h, d, pins)
        self.assertEqual(r.status, D1_HOLD_PUBLIC_STATUS)
        self.assertTrue(r.native_d1_numeric_revision_quarantine_active)
        self.assertEqual(
            r.native_d1_numeric_revision_quarantine_incident,
            D1_KNOWN_SOURCE_REVISION_INCIDENT,
        )
        self.assertTrue(r.private_signal_research_suppressed_by_d1_hold)
        self.assertEqual(r.technical.total_frames, 6)
        self.assertTrue(r.technical.research_technical_context_complete)
        # Physically available 6/6 is NOT the same as trusted for strategy.

    def test_33_quarantine_skips_all_private_swing_and_signal_calculations(self):
        m, h, d, pins = fixtures()
        with patch(
            "mfx_research.six_tf_sealed_archive_consumer."
            "calculate_private_multibar_from_sealed_rows",
            side_effect=AssertionError("DISPUTED_D1_MUST_NOT_ENTER_RESEARCH"),
        ):
            r = self._reviewed_mode_with_in_memory_pinned_fixture(m, h, d, pins)
        self.assertIsNone(r.private_multibar)
        self.assertIsNone(r.private_pivot_sensitivity)
        self.assertIsNone(r.private_m15_microbreak)
        self.assertIsNone(r.private_m15_prefix_replay)

    def test_34_source_hold_keeps_original_sha_evidence_and_zero_permissions(self):
        m, h, d, pins = fixtures()
        r = self._reviewed_mode_with_in_memory_pinned_fixture(m, h, d, pins)
        self.assertEqual(
            (r.m5_manifest_pairs_full_sha,
             r.h4_manifest_pairs_full_sha, r.d1_manifest_pairs_full_sha),
            (2, 1, 1),
        )
        for sha in (
            r.m5_manifest_tip_sha256,
            r.h4_manifest_tip_sha256,
            r.d1_manifest_tip_sha256,
        ):
            self.assertEqual(len(sha), 64)
        self.assertTrue(r.github_reviewed_m5_anchors_checked)
        self.assertFalse(r.provider_account_data_rights_verified)
        self.assertFalse(r.source_first_known_time_proven)
        self.assertFalse(r.may_publish_buy_sell)
        self.assertFalse(r.may_trade)
        self.assertEqual(
            (r.provider_price_calls, r.drive_cache_writes, r.broker_orders),
            (0, 0, 0),
        )

    def test_35_quarantine_read_only_does_not_modify_cached_objects(self):
        m, h, d, pins = fixtures()
        before = [copy.deepcopy(s.objects) for s in (m, h, d)]
        self._reviewed_mode_with_in_memory_pinned_fixture(m, h, d, pins)
        self.assertEqual([s.objects for s in (m, h, d)], before)

    def test_36_sha_tampering_still_rejected_before_quarantine_result(self):
        m, h, d, pins = fixtures()
        k = next(iter(d.objects["chunk"]))
        d.objects["chunk"][k]["bars"][0]["high"] = "1.9999"
        with self.assertRaises(ValueError):
            self._reviewed_mode_with_in_memory_pinned_fixture(m, h, d, pins)

    def test_37_synthetic_fixture_mode_retains_existing_research_only(self):
        result = consume()
        self.assertFalse(result.native_d1_numeric_revision_quarantine_active)
        self.assertFalse(result.private_signal_research_suppressed_by_d1_hold)
        self.assertEqual(
            result.status,
            "SEALED_READONLY_CACHE_TECHNICAL_RESEARCH_ONLY_NO_SIGNAL",
        )
        self.assertIsNotNone(result.private_multibar)
        self.assertIsNotNone(result.private_m15_prefix_replay)

    def test_38_hold_applies_even_when_affected_date_ages_out_of_recent_native(self):
        m, h, d, pins = fixtures()
        d.objects = {"manifest": {}, "chunk": {}}
        _seed_native(d, "1day", ("2026-11-10",))
        # The source policy remains on HOLD even when the injected
        # source slice does not include the exact incident-date row.
        r = self._reviewed_mode_with_in_memory_pinned_fixture(m, h, d, pins)
        self.assertTrue(r.native_d1_numeric_revision_quarantine_active)
        self.assertTrue(r.private_signal_research_suppressed_by_d1_hold)
        self.assertEqual(r.status, D1_HOLD_PUBLIC_STATUS)

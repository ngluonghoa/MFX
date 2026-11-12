"""MFX signal-first: 256->257 source audit boundary without false full SHA."""
from __future__ import annotations

import copy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from mfx_cache.td_m5_codec import ClosedM5Bar, digest
from mfx_cache.v2_batch_commit import _make_plan
from mfx_research.six_tf_sealed_archive_consumer import (
    SyntheticFixturePins, _m5_pinned_rows, consume_sealed_archives_for_six_tf,
)
from tools.run_mfx_v1_manual_drive_six_tf import safe_summary
from test_mfx_v1_six_tf_sealed_archive_consumer import (
    PRICES, ReadOnlyStore, _seed_native,
)

UTC = timezone.utc
START = datetime(2026, 11, 12, 10, tzinfo=UTC)
ASOF = datetime(2026, 12, 1, 12, tzinfo=UTC)
ROLLING = "ROOT_PINNED_ALL_MANIFESTS_LATEST_256_CHUNKS"
FULL = "FULL_BOUNDED_ALL_RAW_SHA"


def seeded_archive(count: int) -> tuple[ReadOnlyStore, SyntheticFixturePins]:
    store = ReadOnlyStore()
    prev = None
    head = None
    root = None
    checkpoint = None
    for i in range(count):
        hour = START + timedelta(hours=i)
        bars = tuple(ClosedM5Bar(
            start_utc=(hour + timedelta(minutes=5*n)).isoformat(),
            **PRICES,
        ) for n in range(12))
        plan = _make_plan(
            prev, hour_utc=hour.isoformat(),
            bars=bars, now_utc=ASOF,
        )
        store.objects["chunk"][plan.chunk_name] = copy.deepcopy(plan.chunk)
        store.objects["manifest"][plan.manifest_name] = copy.deepcopy(
            plan.manifest)
        if i == 0:
            root = plan
        if i == 30:
            checkpoint = plan
        head = plan
        prev = plan.manifest
    if root is None or checkpoint is None or head is None:
        raise AssertionError("need root and 31-pair checkpoint")
    return store, SyntheticFixturePins(
        root_hour_utc=root.hour_utc,
        root_sha256=root.manifest_sha256,
        checkpoint_hour_utc=checkpoint.hour_utc,
        checkpoint_sha256=checkpoint.manifest_sha256,
        checkpoint_pairs=31,
    )


class CountingStore(ReadOnlyStore):
    def __init__(self, prior):
        super().__init__()
        self.objects = copy.deepcopy(prior.objects)
        self.read_events = []

    def read(self, bucket, name):
        self.read_events.append((bucket, name))
        return super().read(bucket, name)


class SixTFRollingM5SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base, cls.pins = seeded_archive(257)
        cls.h4 = ReadOnlyStore()
        cls.d1 = ReadOnlyStore()
        _seed_native(cls.h4, "4h", ("2026-11-12 08:00:00",))
        _seed_native(cls.d1, "1day", ("2026-11-11",))

    def m5(self):
        return copy.deepcopy(self.base)

    def consume(self, *, m5=None, h4=None, d1=None):
        return consume_sealed_archives_for_six_tf(
            self.m5() if m5 is None else m5,
            copy.deepcopy(self.h4) if h4 is None else h4,
            copy.deepcopy(self.d1) if d1 is None else d1,
            asof_utc=ASOF, fixture_pins=self.pins,
        )

    def test_01_257_passes_verified_manifest_and_latest256_raw_only(self):
        r = self.consume()
        self.assertEqual(r.m5_sha_audit_mode, ROLLING)
        self.assertEqual(r.m5_total_archived_manifest_pairs, 257)
        self.assertEqual(r.m5_total_manifest_parent_chain_verified, 257)
        self.assertEqual(r.m5_manifest_pairs_full_sha, 256)
        self.assertEqual(r.m5_historical_raw_chunks_not_reread, 1)
        self.assertTrue(r.m5_recent_raw_sha_verified)
        self.assertFalse(r.all_three_bounded_sha_chains_verified)
        self.assertFalse(r.m5_full_historical_raw_sha_verified)

    def test_02_at_256_keeps_full_raw_sha_proof(self):
        m = self.m5()
        name = sorted(m.objects["manifest"])[-1]
        old = m.objects["manifest"].pop(name)
        del m.objects["chunk"][old["chunk_name"]]
        r = self.consume(m5=m)
        self.assertEqual(r.m5_sha_audit_mode, FULL)
        self.assertEqual(r.m5_manifest_pairs_full_sha, 256)
        self.assertEqual(r.m5_total_manifest_parent_chain_verified, 256)
        self.assertEqual(r.m5_total_archived_manifest_pairs, 256)
        self.assertEqual(r.m5_historical_raw_chunks_not_reread, 0)
        self.assertTrue(r.all_three_bounded_sha_chains_verified)
        self.assertTrue(r.m5_full_historical_raw_sha_verified)

    def test_03_rolling_m5_does_not_read_unverified_old_raw_chunk(self):
        store = CountingStore(self.base)
        rows, evidence = _m5_pinned_rows(
            store, asof_utc=ASOF, fixture_pins=self.pins)
        name = sorted(store.objects["chunk"])[0]
        self.assertNotIn(("chunk", name), store.read_events)
        self.assertEqual(evidence["m5_historical_unread_chunks"], 1)
        self.assertEqual(evidence["m5_manifest_full_sha_parent_chain_verified"],
                         257)
        self.assertEqual(len(rows), 256*12)

    def test_04_rolling_recent_corrupt_raw_sha_denied(self):
        m = self.m5()
        name = sorted(m.objects["chunk"])[-1]
        m.objects["chunk"][name]["bars"][0]["close"] = "1.199"
        with self.assertRaises(ValueError):
            self.consume(m5=m)

    def test_05_rolling_middle_recent_raw_sha_denied(self):
        m = self.m5()
        name = sorted(m.objects["chunk"])[100]
        m.objects["chunk"][name]["bars"][0]["high"] = "1.400"
        with self.assertRaises(ValueError):
            self.consume(m5=m)

    def test_06_rolling_root_sha_pin_denied(self):
        m = self.m5()
        name = sorted(m.objects["manifest"])[0]
        m.objects["manifest"][name]["total_batches"] = 999
        with self.assertRaises(ValueError):
            self.consume(m5=m)

    def test_07_rolling_checkpoint_sha_pin_denied(self):
        m = self.m5()
        name = sorted(m.objects["manifest"])[30]
        m.objects["manifest"][name]["total_closed_m5"] = 9999
        with self.assertRaises(ValueError):
            self.consume(m5=m)

    def test_08_middle_old_manifest_fork_denied(self):
        m = self.m5()
        name = sorted(m.objects["manifest"])[5]
        m.objects["manifest"][name]["continuity_status"] = "FAKE"
        with self.assertRaises(ValueError):
            self.consume(m5=m)

    def test_09_missing_past_chunk_is_not_ignored(self):
        m = self.m5()
        del m.objects["chunk"][sorted(m.objects["chunk"])[0]]
        with self.assertRaises(ValueError):
            self.consume(m5=m)

    def test_10_orphan_latest_chunk_is_not_ignored(self):
        m = self.m5()
        m.objects["chunk"]["unattached_mfx_chunk.json"] = {}
        with self.assertRaises(ValueError):
            self.consume(m5=m)

    def test_11_rolling_never_claims_source_numeric_signal(self):
        r = self.consume()
        self.assertEqual(r.technical.action, "NO_SIGNAL")
        self.assertEqual(r.technical.stage, "UNVERIFIED")
        self.assertFalse(r.technical.entry_sl_tp_net_rr_approved)
        self.assertFalse(r.may_publish_buy_sell)
        self.assertFalse(r.may_trade)
        self.assertFalse(r.github_reviewed_m5_anchors_checked)

    def test_12_old_raw_chunk_tamper_remains_unproven_not_promoted(self):
        # Deliberately changing unread historic raw bytes is NOT detected.
        # This is why full-history SHA MUST be false, regardless of head.
        m = self.m5()
        name = sorted(m.objects["chunk"])[0]
        m.objects["chunk"][name]["bars"][0]["close"] = "1.2"
        r = self.consume(m5=m)
        self.assertEqual(r.m5_historical_raw_chunks_not_reread, 1)
        self.assertFalse(r.m5_full_historical_raw_sha_verified)
        self.assertFalse(r.all_three_bounded_sha_chains_verified)
        self.assertEqual(r.technical.action, "NO_SIGNAL")

    def test_13_masked_output_reports_exact_SHA_scope(self):
        r = replace(
            self.consume(), github_reviewed_m5_anchors_checked=True)
        # Artificial fixture pin replacement is QA-only, NOT live proof.
        v = safe_summary(r, drive_gets=1234)
        self.assertEqual(v["m5_sha_audit_mode"], ROLLING)
        self.assertEqual(v["m5_total_archived_manifest_pairs"], 257)
        self.assertEqual(v["m5_manifest_chunk_pairs_full_sha"], 256)
        self.assertEqual(v["m5_historical_raw_chunks_not_reread"], 1)
        self.assertFalse(v["m5_full_historical_raw_sha_verified"])
        self.assertEqual(v["action"], "NO_SIGNAL")
        for field in ("open", "close", "high", "low", "api_key", "refresh_token"):
            self.assertNotIn(field, v)

    def test_14_masked_full_output_reports_all_history_full(self):
        m = self.m5()
        name = sorted(m.objects["manifest"])[-1]
        entry = m.objects["manifest"].pop(name)
        m.objects["chunk"].pop(entry["chunk_name"])
        r = replace(self.consume(m5=m),
                    github_reviewed_m5_anchors_checked=True)
        v = safe_summary(r, drive_gets=1234)
        self.assertEqual(v["m5_sha_audit_mode"], FULL)
        self.assertEqual(v["m5_historical_raw_chunks_not_reread"], 0)
        self.assertTrue(v["m5_full_historical_raw_sha_verified"])

    def test_15_forged_full_history_flag_denied_in_rolling(self):
        r = replace(
            self.consume(), github_reviewed_m5_anchors_checked=True,
            m5_full_historical_raw_sha_verified=True)
        with self.assertRaisesRegex(ValueError, "SHA_SCOPE"):
            safe_summary(r, drive_gets=1234)

    def test_16_forged_parent_chain_count_denied(self):
        r = replace(
            self.consume(), github_reviewed_m5_anchors_checked=True,
            m5_total_manifest_parent_chain_verified=0)
        with self.assertRaisesRegex(ValueError, "SHA_SCOPE"):
            safe_summary(r, drive_gets=1234)

    def test_17_forged_unread_chunk_count_denied(self):
        r = replace(
            self.consume(), github_reviewed_m5_anchors_checked=True,
            m5_historical_raw_chunks_not_reread=0)
        with self.assertRaisesRegex(ValueError, "SHA_SCOPE"):
            safe_summary(r, drive_gets=1234)

    def test_18_forged_audit_mode_denied(self):
        r = replace(
            self.consume(), github_reviewed_m5_anchors_checked=True,
            m5_sha_audit_mode=FULL)
        with self.assertRaisesRegex(ValueError, "SHA_SCOPE"):
            safe_summary(r, drive_gets=1234)

    def test_19_archives_over_1024_manifest_cap_fail_closed(self):
        class OverBounded:
            def list_names(self, bucket):
                return tuple(f"MFX_RESEARCH_{i:06d}" for i in range(1025))
            def read(self, bucket, name):
                raise AssertionError("must reject before reading")
        with self.assertRaisesRegex(ValueError, "UNVERIFIABLE_BOUND"):
            _m5_pinned_rows(
                OverBounded(), asof_utc=ASOF, fixture_pins=self.pins)

    def test_20_invalid_utc_asof_still_denied(self):
        with self.assertRaisesRegex(ValueError, "EXACT_UTC_ASOF"):
            consume_sealed_archives_for_six_tf(
                self.m5(), copy.deepcopy(self.h4), copy.deepcopy(self.d1),
                asof_utc=datetime(2026, 12, 1), fixture_pins=self.pins)

    def test_21_mutating_head_during_recheck_denied(self):
        class ChangingStore(CountingStore):
            def __init__(self, store):
                super().__init__(store)
                self.manifest_list_reads = 0
            def list_names(self, bucket):
                result = super().list_names(bucket)
                if bucket == "manifest":
                    self.manifest_list_reads += 1
                    if self.manifest_list_reads > 3:
                        return result[:-1]
                return result
        with self.assertRaises(ValueError):
            self.consume(m5=ChangingStore(self.base))

    def test_22_wrong_synthetic_checkpoint_position_denied(self):
        p = replace(self.pins, checkpoint_pairs=30)
        with self.assertRaises(ValueError):
            consume_sealed_archives_for_six_tf(
                self.m5(), copy.deepcopy(self.h4), copy.deepcopy(self.d1),
                asof_utc=ASOF, fixture_pins=p)

    def test_23_replayed_256_tail_has_12_m5_per_last_hour(self):
        m = self.m5()
        last = sorted(m.objects["manifest"])[-1]
        head = m.objects["manifest"][last]
        rows, evidence = _m5_pinned_rows(
            m, asof_utc=ASOF, fixture_pins=self.pins)
        self.assertEqual(len(rows[-12:]), 12)
        self.assertEqual(head["total_closed_m5"], 257*12)
        self.assertEqual(
            evidence["m5_latest_manifest_sha256"], digest(head))

    def test_24_no_automatic_native_h4_substitution(self):
        r = self.consume()
        h4 = r.technical.frames[4]
        self.assertTrue(h4.native)
        self.assertNotEqual(h4.source_label, r.technical.frames[0].source_label)
        self.assertFalse(r.may_publish_buy_sell)

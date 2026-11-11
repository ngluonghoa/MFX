"""A04/P0.74: hermetic native V2 shard handoff NO-LIVE-GO tests."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest import TestCase
import copy

from mfx_cache.td_m5_codec import digest
from tools.mfx_native_htf_drive_seal import (
    NativeArchiveState, audit_native_archive, MAX_NATIVE_FILES,
)
from tools.mfx_native_shard_v2_design import (
    DESIGN_ONLY, propose_native_v2_shard_handoff, verify_native_v2_proposal,
)
from test_a04_p58_native_htf_cache_audit import ReadOnlyFakeStore, native


def v1_state(tf: str) -> tuple[ReadOnlyFakeStore, NativeArchiveState]:
    store = ReadOnlyFakeStore()
    label = "2026-11-11 08:00:00" if tf == "4h" else "2026-11-11"
    store.seed(native(tf, (label,)))
    return store, audit_native_archive(store, symbol="EUR/USD", interval=tf)


def root_proposal(tf: str):
    store, state = v1_state(tf)
    proposal = propose_native_v2_shard_handoff(
        state, symbol="EUR/USD", interval=tf,
        expected_v1_manifest_sha256=digest(state.last_manifest))
    return store, state, proposal


class P074NativeV2OfflineTests(TestCase):
    def test_01_h4_root_inert_and_sha_deterministic(self):
        store, state, p = root_proposal("4h")
        before = copy.deepcopy(store.data)
        twin = propose_native_v2_shard_handoff(
            state, symbol="EUR/USD", interval="4h",
            expected_v1_manifest_sha256=digest(state.last_manifest))
        self.assertEqual(p, twin)
        verify_native_v2_proposal(
            p, state, expected_v1_manifest_sha256=digest(state.last_manifest))
        self.assertEqual(p.status, DESIGN_ONLY)
        self.assertEqual(p.legacy_remaining_append_pairs, 255)
        self.assertTrue(p.awaiting_legacy_full_256)
        self.assertEqual((p.drive_writes,p.estimated_vendor_requests,p.broker_orders),(0,0,0))
        self.assertEqual(before,store.data)

    def test_02_d1_sydney_independent_namespace(self):
        _, _, h = root_proposal("4h")
        _, _, d = root_proposal("1day")
        self.assertNotEqual(h.proposed_v2_scope,d.proposed_v2_scope)
        self.assertIn("H4_NATIVE_V2_SHARD000001",h.proposed_v2_scope)
        self.assertIn("D1_NATIVE_V2_SHARD000001",d.proposed_v2_scope)
        self.assertTrue(d.requires_external_anti_rollback_witness)
        self.assertTrue(d.requires_separate_owner_activation)

    def test_03_wrong_parent_sha_denied(self):
        _, s = v1_state("4h")
        with self.assertRaisesRegex(ValueError,"TIP_SHA_MISMATCH"):
            propose_native_v2_shard_handoff(
                s,symbol="EUR/USD",interval="4h",
                expected_v1_manifest_sha256="f"*64)

    def test_04_bad_expected_sha_denied(self):
        _, s = v1_state("4h")
        for bad in ("","ABC","F"*64,"nothex"*12):
            with self.subTest(bad=bad),self.assertRaisesRegex(
                    ValueError,"EXPECTED_V1_SHA_REQUIRED"):
                propose_native_v2_shard_handoff(
                    s,symbol="EUR/USD",interval="4h",
                    expected_v1_manifest_sha256=bad)

    def test_05_orphan_missing_or_unequal_pairs_denied(self):
        _, s = v1_state("4h")
        for bad in (
            replace(s,uncommitted_chunk_names=("orphan",)),
            replace(s,manifest_count=2),
            replace(s,chunk_count=2),
            replace(s,chunk_count=0),
            replace(s,manifest_count=0),
            replace(s,manifest_count=True),
        ):
            with self.subTest(bad=bad),self.assertRaisesRegex(
                    ValueError,"NOT_FULLY_SEALED"):
                propose_native_v2_shard_handoff(
                    bad,symbol="EUR/USD",interval="4h",
                    expected_v1_manifest_sha256=digest(s.last_manifest))

    def test_06_above_v1_hard_limit_denied(self):
        _, s = v1_state("4h")
        bad=replace(s,manifest_count=257,chunk_count=257)
        with self.assertRaisesRegex(ValueError,"NOT_FULLY_SEALED"):
            propose_native_v2_shard_handoff(
                bad,symbol="EUR/USD",interval="4h",
                expected_v1_manifest_sha256=digest(s.last_manifest))

    def test_07_wrong_pair_or_timeframe_denied(self):
        _, s = v1_state("4h")
        for pair,tf in (("GBP/USD","4h"),("EUR/USD","5min"),("EUR/USD","7day")):
            with self.subTest(pair=pair,tf=tf),self.assertRaisesRegex(
                    ValueError,"ONLY_EURUSD_NATIVE_H4_D1"):
                propose_native_v2_shard_handoff(
                    s,symbol=pair,interval=tf,
                    expected_v1_manifest_sha256=digest(s.last_manifest))

    def test_08_renamed_legacy_head_denied(self):
        _, s = v1_state("4h")
        bad=replace(s,latest_manifest_name="renamed.json")
        with self.assertRaisesRegex(ValueError,"MANIFEST_NAME_SHA_MISMATCH"):
            propose_native_v2_shard_handoff(
                bad,symbol="EUR/USD",interval="4h",
                expected_v1_manifest_sha256=digest(s.last_manifest))

    def test_09_batch_counter_tamper_denied(self):
        _, s = v1_state("4h")
        bad=replace(s,manifest_count=2,chunk_count=2)
        with self.assertRaisesRegex(ValueError,"BATCH_COUNT_MISMATCH"):
            propose_native_v2_shard_handoff(
                bad,symbol="EUR/USD",interval="4h",
                expected_v1_manifest_sha256=digest(s.last_manifest))

    def test_10_changed_historical_tip_denied(self):
        _, s, p = root_proposal("4h")
        tail=dict(s.last_manifest)
        tail["total_closed_native_bars"]+=9
        bad=replace(s,last_manifest=tail)
        with self.assertRaises(ValueError):
            verify_native_v2_proposal(
                p,bad,expected_v1_manifest_sha256=digest(s.last_manifest))

    def test_11_forged_owner_permission_denied(self):
        _, s, p = root_proposal("4h")
        altered=replace(p,requires_separate_owner_activation=False)
        with self.assertRaisesRegex(ValueError,"CHANGED_OR_FORGED"):
            verify_native_v2_proposal(
                altered,s,expected_v1_manifest_sha256=digest(s.last_manifest))

    def test_12_full_256_is_still_offline_not_live(self):
        _, s = v1_state("4h")
        tail=dict(s.last_manifest)
        tail["batch_count"]=256
        tail["total_closed_native_bars"]=256
        tail["parent_manifest_sha256"]="a"*64
        from mfx_cache.native_htf_archive import _name
        name=_name("manifest","EUR/USD","4h",
                   tail["last_native_open_label"],digest(tail))
        artificial=replace(s,manifest_count=256,chunk_count=256,
                           last_manifest=tail,latest_manifest_name=name)
        p=propose_native_v2_shard_handoff(
            artificial,symbol="EUR/USD",interval="4h",
            expected_v1_manifest_sha256=digest(tail))
        self.assertEqual(p.legacy_remaining_append_pairs,0)
        self.assertFalse(p.awaiting_legacy_full_256)
        self.assertTrue(p.requires_independent_full_sha_recheck)
        self.assertTrue(p.requires_external_anti_rollback_witness)
        self.assertTrue(p.requires_separate_owner_activation)
        self.assertEqual((p.status,p.drive_writes),(DESIGN_ONLY,0))

    def test_13_off_grid_h4_last_label_denied(self):
        _, s = v1_state("4h")
        tail=copy.deepcopy(s.last_manifest)
        tail["last_native_open_label"]="2026-11-11 09:00:00"
        tail["recent_native_bar_index"][-1]["label"]="2026-11-11 09:00:00"
        from mfx_cache.native_htf_archive import _name
        name=_name("manifest","EUR/USD","4h",
                   tail["last_native_open_label"],digest(tail))
        bad=replace(s,last_manifest=tail,latest_manifest_name=name)
        with self.assertRaisesRegex(ValueError,"NOT_UTC_FOUR_HOUR_GRID"):
            propose_native_v2_shard_handoff(
                bad,symbol="EUR/USD",interval="4h",
                expected_v1_manifest_sha256=digest(tail))

    def test_14_d1_not_sydney_denied(self):
        _, s = v1_state("1day")
        tail=dict(s.last_manifest)
        tail["exchange_timezone"]="UTC"
        bad=replace(s,last_manifest=tail)
        with self.assertRaises(ValueError):
            propose_native_v2_shard_handoff(
                bad,symbol="EUR/USD",interval="1day",
                expected_v1_manifest_sha256=digest(tail))

    def test_15_existing_native_writer_and_audit_not_switched(self):
        self.assertEqual(MAX_NATIVE_FILES,256)
        writer=Path(".github/workflows/mfx-native-htf-incremental-commit.yml"
                    ).read_text(encoding="utf-8")
        self.assertIn('cron: "25 * * * *"',writer)
        self.assertIn("MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED",writer)
        self.assertNotIn("mfx_native_shard_v2_design",writer)
        reader=Path("tools/run_mfx_native_htf_cache_audit.py"
                    ).read_text(encoding="utf-8")
        self.assertNotIn("mfx_native_shard_v2_design",reader)

"""A04/P0.75: pure V2 H4/D1 shard-chain and fork/recovery simulations.

Synthetic 256-pair V1 tail below is a FAKE fixture; it cannot attest
real V1 history, trusted external witness or a live V2 migration.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import copy
import unittest

from mfx_cache.native_fx_htf import NativeFXBatch
from mfx_cache.native_htf_archive import _name
from mfx_cache.td_m5_codec import digest
from tools.mfx_native_htf_drive_seal import NativeArchiveState
from tools.mfx_native_shard_v2_design import propose_native_v2_shard_handoff
from tools.mfx_native_v2_shard_chain import (
    MAX_RESEARCH_SHARDS, SCHEMA, V2SealedPair, audit_v2_chain,
    plan_v2_append,
)
from test_a04_p74_native_v2_handoff import v1_state
from test_a04_p58_native_htf_cache_audit import native

NOW = datetime(2026, 11, 20, 0, 0, tzinfo=timezone.utc)
H4 = ("2026-11-11 12:00:00", "2026-11-11 16:00:00",
      "2026-11-11 20:00:00", "2026-11-12 00:00:00",
      "2026-11-12 04:00:00", "2026-11-12 08:00:00",
      "2026-11-12 12:00:00", "2026-11-12 16:00:00",
      "2026-11-12 20:00:00")
D1 = ("2026-11-12", "2026-11-13", "2026-11-16", "2026-11-17")


def fake_full_v1(tf: str):
    """Fabricated 256th metadata, intentionally NOT a real chain audit."""
    _, seed = v1_state(tf)
    tail = copy.deepcopy(seed.last_manifest)
    tail["batch_count"] = 256
    tail["total_closed_native_bars"] = 256
    tail["parent_manifest_sha256"] = "a" * 64
    tip_sha = digest(tail)
    tail_name = _name(
        "manifest", "EUR/USD", tf, tail["last_native_open_label"], tip_sha)
    state = NativeArchiveState(
        tail, tail_name, 256, 256, ())
    proposal = propose_native_v2_shard_handoff(
        state, symbol="EUR/USD", interval=tf,
        expected_v1_manifest_sha256=tip_sha)
    return state, proposal, tip_sha


def append(state, proposal, v1_sha, history, labels, *, cap=2, now=NOW):
    prior_head = (
        proposal.proposed_anchor_sha256 if not history
        else history[-1].manifest_sha256)
    return plan_v2_append(
        proposal, state, expected_v1_manifest_sha256=v1_sha,
        history=tuple(history), expected_history_tip_sha256=prior_head,
        batch=native(proposal.interval, tuple(labels)),
        now_utc=now, shard_capacity=cap)


def chain(tf="4h", labels=H4[:3], *, cap=2):
    state, proposal, v1_sha = fake_full_v1(tf)
    history = []
    for label in labels:
        history.append(append(
            state, proposal, v1_sha, history, [label], cap=cap))
    return state, proposal, v1_sha, tuple(history)


def verify(state, proposal, v1_sha, history, *, cap=2, tip=None, now=NOW):
    tip = tip if tip is not None else (
        history[-1].manifest_sha256 if history
        else proposal.proposed_anchor_sha256)
    return audit_v2_chain(
        proposal, state,
        expected_v1_manifest_sha256=v1_sha,
        pairs=tuple(history), expected_v2_tip_sha256=tip,
        now_utc=now, shard_capacity=cap)


class A04P075NativeV2ShardChainTests(unittest.TestCase):
    def test_01_empty_chain_is_unwitnessed_offline(self):
        state, p, sha = fake_full_v1("4h")
        receipt = verify(state, p, sha, ())
        self.assertEqual(receipt.pair_count, 0)
        self.assertEqual(receipt.shard_count, 0)
        self.assertEqual(receipt.latest_manifest_sha256,
                         p.proposed_anchor_sha256)
        self.assertTrue(receipt.complete_supplied_chain_sha_verified)
        self.assertFalse(receipt.independent_external_tail_witness_verified)
        self.assertFalse(receipt.v2_live_activation_authorized)

    def test_02_first_h4_append_is_pure_and_v1_root_anchored(self):
        s, p, sha = fake_full_v1("4h")
        original = copy.deepcopy(s.last_manifest)
        pair = append(s, p, sha, (), [H4[0]])
        self.assertEqual(pair.manifest["parent_manifest_sha256"],
                         p.proposed_anchor_sha256)
        self.assertEqual(pair.manifest["v1_tip_manifest_sha256"],sha)
        self.assertEqual(pair.manifest["shard_pair_index"],1)
        self.assertIn("SHARD000001",pair.manifest_name)
        self.assertEqual(pair.chunk_sha256,digest(pair.chunk))
        self.assertEqual(pair.manifest_sha256,digest(pair.manifest))
        self.assertEqual(s.last_manifest,original)
        self.assertEqual(verify(s,p,sha,(pair,)).total_native_bars,1)

    def test_03_daily_uses_sydney_date_not_utc_h4(self):
        s,p,sha,h = chain("1day",D1[:2])
        r = verify(s,p,sha,h)
        self.assertEqual(r.last_native_open_label,"2026-11-13")
        self.assertEqual(r.total_native_bars,2)
        self.assertEqual(h[0].manifest["time_reference"],
                         "EXCHANGE_LOCAL_SESSION_DATE")
        self.assertIn("D1_NATIVE_V2",h[0].chunk_name)
        self.assertEqual(r.provider_requests,0)
        self.assertEqual(r.real_drive_writes,0)
        self.assertEqual(r.broker_orders,0)

    def test_04_rollover_links_previous_shard_sha(self):
        s,p,sha,h = chain()
        self.assertEqual([a.manifest["shard_number"] for a in h],[1,1,2])
        self.assertEqual([a.manifest["shard_pair_index"] for a in h],[1,2,1])
        self.assertEqual(h[2].manifest["parent_manifest_sha256"],
                         h[1].manifest_sha256)
        self.assertEqual(h[2].manifest["shard_bridge_sha256"],
                         h[1].manifest_sha256)
        self.assertEqual(h[1].manifest["shard_bridge_sha256"],
                         p.proposed_anchor_sha256)
        self.assertEqual(verify(s,p,sha,h).shard_count,2)

    def test_05_corrupt_old_chunk_fails_full_chain(self):
        s,p,sha,h=chain()
        changed=copy.deepcopy(h[0])
        changed.chunk["bars"][0]["close"]="5.0000"
        with self.assertRaises(ValueError):
            verify(s,p,sha,(changed,*h[1:]))

    def test_06_tamper_parent_sha_or_filename_denied(self):
        s,p,sha,h=chain()
        for modified in (
            replace(h[1],manifest={**h[1].manifest,
                "parent_manifest_sha256":"b"*64}),
            replace(h[1],manifest_name="fake.json"),
        ):
            with self.subTest(modified=modified.manifest_name):
                with self.assertRaises(ValueError):
                    verify(s,p,sha,(h[0],modified,h[2]))

    def test_07_missing_middle_pair_denied_even_when_last_digest_preserved(self):
        s,p,sha,h=chain()
        with self.assertRaises(ValueError):
            verify(s,p,sha,(h[0],h[2]),tip=h[-1].manifest_sha256)

    def test_08_out_of_order_shards_denied(self):
        s,p,sha,h=chain()
        with self.assertRaises(ValueError):
            verify(s,p,sha,(h[1],h[0],h[2]))

    def test_09_known_expected_tip_blocks_fork(self):
        s,p,sha,h=chain()
        with self.assertRaisesRegex(ValueError,"TIP_ROLLBACK_OR_FORK"):
            verify(s,p,sha,h,tip="f"*64)

    def test_10_replayed_legacy_or_current_label_denied(self):
        s,p,sha,h=chain()
        for label in ("2026-11-11 08:00:00",H4[2],H4[0]):
            with self.subTest(label=label), self.assertRaisesRegex(
                    ValueError,"DUPLICATE_OR_ROLLBACK_NATIVE_LABEL"):
                append(s,p,sha,h,[label])

    def test_11_bad_utc_h4_grid_fails_closed(self):
        s,p,sha=fake_full_v1("4h")
        with self.assertRaisesRegex(ValueError,"P061_H4_UTC_4H_GRID_REQUIRED"):
            append(s,p,sha,(),["2026-11-11 13:00:00"])

    def test_12_future_or_not_yet_closed_h4_denied(self):
        s,p,sha=fake_full_v1("4h")
        at=datetime(2026,11,11,16,2,14,tzinfo=timezone.utc)
        with self.assertRaisesRegex(
                ValueError,"NOT_YET_PUBLICATION_ELIGIBLE"):
            append(s,p,sha,(),[H4[0]],now=at)
        at=at+timedelta(seconds=1)
        append(s,p,sha,(),[H4[0]],now=at)

    def test_13_sydney_d1_close_guard(self):
        s,p,sha=fake_full_v1("1day")
        with self.assertRaisesRegex(
                ValueError,"D1_NOT_YET_PUBLICATION_ELIGIBLE"):
            append(s,p,sha,(),["2026-11-12"],
                   now=datetime(2026,11,12,13,2,14,tzinfo=timezone.utc))
        append(s,p,sha,(),["2026-11-12"],
               now=datetime(2026,11,12,13,2,15,tzinfo=timezone.utc))

    def test_14_source_wrong_interval_or_synthetic_price_denied(self):
        s,p,sha=fake_full_v1("4h")
        bad_d1=native("1day",(D1[0],))
        with self.assertRaisesRegex(ValueError,
                                    "NATIVE_CLOSED_BATCH_REQUIRED"):
            plan_v2_append(p,s,expected_v1_manifest_sha256=sha,
                history=(),expected_history_tip_sha256=p.proposed_anchor_sha256,
                batch=bad_d1,now_utc=NOW,shard_capacity=2)
        good=native("4h",(H4[0],))
        wrong=replace(good,closed_bars=(
            replace(good.closed_bars[0],source_numeric_strategy_approved=True),))
        with self.assertRaises(ValueError):
            plan_v2_append(p,s,expected_v1_manifest_sha256=sha,
                history=(),expected_history_tip_sha256=p.proposed_anchor_sha256,
                batch=wrong,now_utc=NOW,shard_capacity=2)

    def test_15_weekend_gap_not_auto_filled_or_waived(self):
        s,p,sha,h=chain("1day",(D1[0],D1[2]))
        self.assertEqual([x.manifest["last_native_open_label"] for x in h],
                         ["2026-11-12","2026-11-16"])
        self.assertFalse(verify(s,p,sha,h).independent_external_tail_witness_verified)

    def test_16_legacy_v1_must_reach_256_not_promote_early(self):
        store, actual = v1_state("4h")
        p=propose_native_v2_shard_handoff(
            actual,symbol="EUR/USD",interval="4h",
            expected_v1_manifest_sha256=digest(actual.last_manifest))
        with self.assertRaisesRegex(ValueError,
                                    "V1_NOT_FULL_OR_PROPOSAL_NOT_INERT"):
            append(actual,p,digest(actual.last_manifest),(),[H4[0]])
        self.assertTrue(store.data["manifest"])

    def test_17_shard_capacity_bound_and_exact_max(self):
        s,p,sha=fake_full_v1("4h")
        for cap in (0,65,-1,True):
            with self.subTest(cap=cap),self.assertRaisesRegex(
                    ValueError,"INVALID_SHARD_CAPACITY"):
                append(s,p,sha,(),[H4[0]],cap=cap)
        h=[]
        for label in H4[:MAX_RESEARCH_SHARDS]:
            h.append(append(s,p,sha,h,[label],cap=1))
        self.assertEqual(verify(s,p,sha,h,cap=1).shard_count,
                         MAX_RESEARCH_SHARDS)
        with self.assertRaisesRegex(ValueError,
                                    "MAX_RESEARCH_SHARDS_EXCEEDED"):
            append(s,p,sha,h,[H4[MAX_RESEARCH_SHARDS]],cap=1)

    def test_18_bad_append_history_tip_blocked(self):
        s,p,sha,h=chain(labels=H4[:1])
        with self.assertRaisesRegex(ValueError,"TIP_ROLLBACK_OR_FORK"):
            plan_v2_append(
                p,s,expected_v1_manifest_sha256=sha,
                history=h,expected_history_tip_sha256="d"*64,
                batch=native("4h",(H4[1],)),now_utc=NOW,shard_capacity=2)

    def test_19_tail_truncation_without_external_head_is_not_trusted(self):
        s,p,sha,h=chain()
        # A malicious source could shorten a perfectly SHA-valid chain and
        # ALSO replace the caller-supplied expected head. Never call this
        # an externally authenticated anti-rollback proof.
        shortened=verify(s,p,sha,h[:1],tip=h[0].manifest_sha256)
        self.assertEqual(shortened.pair_count,1)
        self.assertFalse(shortened.independent_external_tail_witness_verified)
        with self.assertRaisesRegex(ValueError,"TIP_ROLLBACK_OR_FORK"):
            verify(s,p,sha,h[:1],tip=h[-1].manifest_sha256)

    def test_20_wrong_legacy_tip_cannot_be_used(self):
        s,p,sha,h=chain()
        with self.assertRaises(ValueError):
            verify(s,p,"e"*64,h)

    def test_21_bars_and_manifest_labels_are_monotonic(self):
        s,p,sha=fake_full_v1("4h")
        with self.assertRaisesRegex(
                ValueError,"DUPLICATE_OR_ROLLBACK_NATIVE_LABEL"):
            append(s,p,sha,(),[H4[1],H4[0]])
        with self.assertRaisesRegex(
                ValueError,"DUPLICATE_OR_ROLLBACK_NATIVE_LABEL"):
            append(s,p,sha,(),[H4[0],H4[0]])

    def test_22_no_mutation_of_v1_runner_or_cache_schedule(self):
        self.assertIn("P75",SCHEMA)
        workflow=Path(".github/workflows/mfx-native-htf-incremental-commit.yml"
                     ).read_text(encoding="utf-8")
        self.assertIn('cron: "25 * * * *"',workflow)
        self.assertIn("MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED",workflow)
        self.assertNotIn("mfx_native_v2_shard_chain",workflow)
        audit=Path("tools/run_mfx_native_htf_cache_audit.py"
                   ).read_text(encoding="utf-8")
        self.assertNotIn("mfx_native_v2_shard_chain",audit)

    def test_23_unknown_extra_metadata_fails_exact_rebuild(self):
        s,p,sha,h=chain()
        modified=copy.deepcopy(h[0])
        modified.manifest["unexpected_field"]=1
        with self.assertRaisesRegex(ValueError,
                                    "IMMUTABLE_V2_SHA_OR_PARENT_MISMATCH"):
            verify(s,p,sha,(modified,*h[1:]))

    def test_24_all_outputs_research_only(self):
        s,p,sha,h=chain("4h",H4[:4])
        report=verify(s,p,sha,h)
        self.assertEqual(report.status,
                         "OFFLINE_CHAIN_RECOMPUTED_NO_EXTERNAL_WITNESS")
        self.assertEqual((report.real_drive_writes,report.provider_requests,
                          report.broker_orders),(0,0,0))
        self.assertFalse(report.v2_live_activation_authorized)
        self.assertEqual(report.shard_count,2)


if __name__=="__main__":
    unittest.main()

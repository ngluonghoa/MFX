"""P0.195: B2/S2 real-source F2 seam honors owner's 18-Nov D1 cutoff.

All inputs below are hermetic synthetic SHA fixtures, not licensed market
data or evidence of a manual GitHub OAuth six-timeframe run.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json
from unittest import TestCase
from unittest.mock import patch

from mfx_cache.td_m5_codec import digest
from mfx_research.p184_paired_f2_owner_review import (
    compile_paired_f2_owner_proposals,
)
from mfx_research.p187_b2s2_six_tf_signal_only_gate import (
    compose_b2s2_signal_only_gate, from_sealed_stores_b2s2_signal_only,
)
from test_mfx_p187_b2s2_six_tf_signal_only_gate import proposal
from test_mfx_p193_owner_nov18_source_readonly import seeded
from test_mfx_p193_six_tf_owner_nov18_no_splice import (
    ASOF, make_inputs,
)
from test_mfx_v1_signal_only_six_tf_response import (
    sealed as constructed_sealed,
)


def b2s2_nov18(*, with_p192=True, old_active=None, wrong_root=False,
               tamper_chunk=False, asof=ASOF):
    m5, h4, original_v1, pins = make_inputs()
    old_tip = digest(original_v1.read(
        "manifest", original_v1.list_names("manifest")[-1]))
    p192 = seeded(old_sha=old_tip) if with_p192 else None
    if p192 is not None and tamper_chunk:
        p192.files["chunk"][next(iter(p192.files["chunk"]))]["bars"][0][
            "high"] = "9.9999"
    root = (digest(p192.read("manifest", p192.list_names("manifest")[0]))
            if p192 is not None else "0"*64)
    snapshots = deepcopy((
        m5.objects, h4.objects, original_v1.objects,
        p192.files if p192 is not None else None,
    ))
    with patch.multiple(
        "mfx_research.six_tf_sealed_archive_consumer",
        ROOT_UTC=pins.root_hour_utc,
        ROOT_MANIFEST_SHA256=pins.root_sha256,
        REVIEWED_CHECKPOINT_UTC=pins.checkpoint_hour_utc,
        REVIEWED_CHECKPOINT_SHA256=pins.checkpoint_sha256,
        REVIEWED_CHECKPOINT_PAIRS=pins.checkpoint_pairs,
    ), patch.multiple(
        "mfx_research.p193_owner_nov18_active_d1_reader",
        PINNED_ORIGINAL_D1_V1_HEAD_SHA256=old_tip,
        PINNED_P192_20261118_ROOT_SHA256=("0"*64 if wrong_root else root),
    ):
        result = from_sealed_stores_b2s2_signal_only(
            m5, h4, original_v1, asof_utc=asof,
            owner_proposal_packet=proposal(),
            active_d1_epoch_store=old_active,
            owner_nov18_d1_epoch_store=p192,
        )
    assert snapshots == (
        m5.objects, h4.objects, original_v1.objects,
        p192.files if p192 is not None else None,
    ), "P195 source read unexpectedly changed sealed storage"
    return result


class P195B2S2P192OwnerD1CutoverTests(TestCase):
    def test_01_new_owner_d1_reaches_actual_b2s2_source_seam(self):
        r = b2s2_nov18()
        self.assertEqual(r.active_d1_source_epoch,
                         "P192_D1_FRESH_20261118")
        self.assertEqual((r.action, r.stage),
                         ("NO_SIGNAL", "UNVERIFIED"))
        self.assertEqual((r.numeric_original_approvals,
                          r.numeric_original_pending), (0, 36))
        self.assertEqual((r.provider_price_requests,
                          r.drive_market_writes, r.broker_orders),
                         (0, 0, 0))

    def test_02_public_receipt_names_only_owner_epoch_not_private_prices(self):
        r = b2s2_nov18()
        output = r.public_summary()
        self.assertEqual(output["active_d1_source_epoch"],
                         "P192_D1_FRESH_20261118")
        self.assertIsNone(output["entry_price"])
        self.assertIsNone(output["stop_loss"])
        self.assertIsNone(output["take_profit"])
        self.assertIsNone(output["net_risk_reward"])
        self.assertFalse(output["may_publish_buy_sell"])
        serialized = json.dumps(output, sort_keys=True)
        for private in ('"open"', '"high"', '"low"', '"close"',
                        '"raw_ohlc"', "1.1000", "1.1020"):
            self.assertNotIn(private, serialized)

    def test_03_missing_new_d1_does_not_fallback_to_old_source(self):
        class Spy:
            calls = 0
            def list_names(self, bucket):
                self.calls += 1
                raise AssertionError("Must not access legacy store")
            def read(self, bucket, name):
                self.calls += 1
                raise AssertionError("Must not access legacy store")
        spy = Spy()
        with self.assertRaisesRegex(
            ValueError, "P195_B2S2_REAL_SOURCE_REQUIRES_P192_OWNER_D1"
        ):
            from_sealed_stores_b2s2_signal_only(
                spy, spy, spy, asof_utc=ASOF,
                owner_proposal_packet=proposal(),
            )
        self.assertEqual(spy.calls, 0)

    def test_04_old_and_new_epoch_simultaneously_rejected(self):
        with self.assertRaisesRegex(ValueError, "REJECTS_HISTORICAL"):
            b2s2_nov18(old_active=seeded())

    def test_05_wrong_root_sha_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "ROOT_SHA_MISMATCH"):
            b2s2_nov18(wrong_root=True)

    def test_06_modified_closed_d1_chunk_fails_closed(self):
        with self.assertRaises(ValueError):
            b2s2_nov18(tamper_chunk=True)

    def test_07_not_yet_observed_owner_candle_is_denied(self):
        with self.assertRaises(ValueError):
            b2s2_nov18(asof=ASOF-timedelta(hours=1))

    def test_08_forged_d1_pre_cutoff_splice_cannot_reach_public_f2(self):
        signed = compile_paired_f2_owner_proposals(proposal())
        forged = replace(
            constructed_sealed(),
            active_d1_source_epoch="P192_D1_FRESH_20261118",
            original_preincident_d1_rows_verified=119,
            new_epoch_d1_rows_in_context=1,
            active_d1_composed_history_sha256="a"*64,
            archived_v1_d1_manifest_tip_sha256="b"*64,
        )
        with self.assertRaisesRegex(ValueError, "P195_B2S2_OWNER_NOV18_D1"):
            compose_b2s2_signal_only_gate(
                forged, owner_proposal=signed)

    def test_09_one_nov18_daily_bar_is_never_a_confirmed_source_buy_sell(self):
        r = b2s2_nov18()
        self.assertEqual(r.action, "NO_SIGNAL")
        self.assertFalse(r.may_trade)
        self.assertFalse(r.may_publish_buy_sell)
        self.assertIn("ORIGINAL_36_NUMERIC_SOURCE_DECISIONS_UNAPPROVED",
                      r.blockers)
        self.assertIn("UNTAMPERED_CHRONOLOGICAL_OOS_NOT_QUALIFIED",
                      r.blockers)

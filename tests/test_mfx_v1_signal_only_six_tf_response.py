"""Hermetic tests of signal-only six-TF rendering: never BUY/SELL or fills."""
from dataclasses import replace
from unittest import TestCase

from mfx_cache.td_m5_codec import PROVIDER
from mfx_research.six_tf_readonly_context import (
    FRAMES, VERSION as TECH_VERSION, ReadonlyTimeframeEvidence,
    SixTimeframeResearchReceipt,
)
from mfx_research.six_tf_sealed_archive_consumer import (
    VERSION as SEALED_VERSION, SealedArchiveSixTFReceipt,
)
from mfx_research.signal_only_six_tf_response import (
    FULL_MODE, ROLLING_MODE, build_signal_only_research_response,
)

HEX = "a" * 64
ASOF = "2026-11-12T12:01:00+00:00"


def technical(frames=FRAMES):
    evidence = tuple(ReadonlyTimeframeEvidence(
        frame=frame, source_provider=PROVIDER, source_price_side="MID",
        time_basis="EXCHANGE_LOCAL_SESSION_DATE" if frame == "D1"
                   else "UTC_INTRADAY_WINDOW",
        source_label="2026-11-11" if frame == "D1"
                     else "2026-11-12T11:00:00+00:00",
        end_utc=None if frame == "D1" else "2026-11-12T12:00:00+00:00",
        open="1.1", high="1.2", low="1.0", close="1.1",
        source_bar_count=1, evidence_sha256=HEX, native=frame in ("M5","H4","D1"),
    ) for frame in frames)
    complete = len(frames) == 6
    return SixTimeframeResearchReceipt(
        version=TECH_VERSION, action="NO_SIGNAL", stage="UNVERIFIED",
        status=("SIX_TF_TECHNICAL_RESEARCH_READY_NO_SIGNAL" if complete
                else "SIX_TF_MISSING_OR_STALE_NO_SIGNAL"),
        asof_utc=ASOF, instrument="EUR/USD", source_provider=PROVIDER,
        input_m5_sha256=HEX, frames=evidence,
        missing_or_stale_frames=tuple(f for f in FRAMES if f not in frames),
        total_frames=len(frames), research_technical_context_complete=complete,
    )


def sealed(t=None, **kwargs):
    base = SealedArchiveSixTFReceipt(
        version=SEALED_VERSION,
        status="SEALED_READONLY_CACHE_TECHNICAL_RESEARCH_ONLY_NO_SIGNAL",
        technical=technical() if t is None else t,
        m5_manifest_pairs_full_sha=2, h4_manifest_pairs_full_sha=2,
        d1_manifest_pairs_full_sha=2, m5_manifest_tip_sha256=HEX,
        h4_manifest_tip_sha256="b"*64, d1_manifest_tip_sha256="c"*64,
        all_three_bounded_sha_chains_verified=True,
        github_reviewed_m5_anchors_checked=True,
        m5_sha_audit_mode=FULL_MODE,
        m5_total_manifest_parent_chain_verified=2,
        m5_total_archived_manifest_pairs=2,
        m5_historical_raw_chunks_not_reread=0,
        m5_full_historical_raw_sha_verified=True,
        m5_recent_raw_sha_verified=True,
    )
    return replace(base, **kwargs)


class SignalOnlySixTFResponseTests(TestCase):
    def test_complete_research_does_not_publish_market_action(self):
        r = build_signal_only_research_response(sealed())
        self.assertEqual((r.action, r.stage), ("NO_SIGNAL", "UNVERIFIED"))
        self.assertEqual(r.frames_present, FRAMES)
        self.assertEqual(r.frames_missing_or_stale, ())
        self.assertEqual(r.technical_status, "SIX_TF_COMPLETE_RESEARCH_ONLY")
        self.assertFalse(r.may_publish_buy_sell)
        self.assertFalse(r.may_trade)

    def test_no_invented_zone_prices_costs_first_known(self):
        r = build_signal_only_research_response(sealed())
        self.assertIsNone(r.zone_label)
        self.assertIsNone(r.entry_price)
        self.assertIsNone(r.stop_loss)
        self.assertIsNone(r.take_profit)
        self.assertIsNone(r.net_risk_reward)
        self.assertIsNone(r.publisher_first_known_utc)

    def test_independent_external_gates_are_explicit(self):
        r = build_signal_only_research_response(sealed())
        self.assertIn("ORIGINAL_SOURCE_NUMERIC_RULES_UNAPPROVED",r.reason_codes)
        self.assertIn("ACCOUNT_SPECIFIC_DATA_RIGHTS_UNVERIFIED",r.reason_codes)
        self.assertIn("BID_ASK_SPREAD_COST_SL_TP_NET_RR_UNVERIFIED",r.reason_codes)
        self.assertIn("CAUSAL_OOS_AND_RELEASE_NOT_ACCEPTED",r.reason_codes)
        self.assertIn("PUBLISHER_FIRST_KNOWN_UNVERIFIED",r.reason_codes)

    def test_empty_provider_drive_broker_side_effects(self):
        r = build_signal_only_research_response(sealed())
        self.assertEqual((r.provider_requests,r.drive_cache_writes,r.broker_orders),
                         (0,0,0))

    def test_missing_m5_m15_explicit_and_not_silent_completion(self):
        t=technical(("M30","H1","H4","D1"))
        r=build_signal_only_research_response(sealed(t))
        self.assertEqual(r.frames_missing_or_stale,("M5","M15"))
        self.assertIn("FRAME_MISSING_OR_STALE_M5",r.reason_codes)
        self.assertIn("FRAME_MISSING_OR_STALE_M15",r.reason_codes)
        self.assertEqual(r.technical_status,"SIX_TF_INCOMPLETE_RESEARCH_ONLY")

    def test_rolling_sha_cannot_claim_full_historical_raw(self):
        rec=sealed(
            m5_sha_audit_mode=ROLLING_MODE,
            m5_manifest_pairs_full_sha=256,
            m5_total_manifest_parent_chain_verified=300,
            m5_total_archived_manifest_pairs=300,
            m5_historical_raw_chunks_not_reread=44,
            m5_full_historical_raw_sha_verified=False,
            all_three_bounded_sha_chains_verified=False,
        )
        r=build_signal_only_research_response(rec)
        self.assertIn("OLDER_M5_RAW_CHUNKS_NOT_REREAD",r.reason_codes)
        self.assertEqual(r.action,"NO_SIGNAL")

    def test_synthetic_source_anchors_marked(self):
        r=build_signal_only_research_response(
            sealed(github_reviewed_m5_anchors_checked=False))
        self.assertIn("M5_SOURCE_ANCHORS_SYNTHETIC_OR_UNREVIEWED",r.reason_codes)

    def test_response_fingerprint_deterministic_and_sha_changed(self):
        r=build_signal_only_research_response(sealed())
        self.assertEqual(r.evidence_fingerprint_sha256,
                         build_signal_only_research_response(sealed()).evidence_fingerprint_sha256)
        other=build_signal_only_research_response(sealed(d1_manifest_tip_sha256="d"*64))
        self.assertNotEqual(r.evidence_fingerprint_sha256,other.evidence_fingerprint_sha256)

    def test_forged_buy_action_rejected(self):
        with self.assertRaisesRegex(ValueError,"FORGED_SOURCE_OR_SIGNAL_AUTHORITY"):
            build_signal_only_research_response(sealed(replace(technical(),action="BUY")))

    def test_forged_permission_or_numeric_gate_rejected(self):
        for key in ("may_publish_buy_sell","provider_account_data_rights_verified",
                    "source_first_known_time_proven","source_numeric_entry_rules_approved",
                    "bidask_costs_and_sl_tp_net_rr_approved","may_trade"):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError,"FORGED_SOURCE"):
                build_signal_only_research_response(sealed(**{key:True}))

    def test_typed_frame_bid_injection_rejected(self):
        t=technical()
        bad=replace(t.frames[0],source_price_side="BID")
        with self.assertRaisesRegex(ValueError,"FRAME_AUTHORITY_OR_SIDE"):
            build_signal_only_research_response(sealed(replace(t,frames=(bad,)+t.frames[1:])))

    def test_fake_six_frame_coverage_rejected(self):
        t=technical(("M5","M15","M30","H1","H4"))
        with self.assertRaisesRegex(ValueError,"SIX_FRAME_COVERAGE_DRIFT"):
            build_signal_only_research_response(
                sealed(replace(t,missing_or_stale_frames=())))

    def test_malformed_manifest_sha_rejected(self):
        with self.assertRaisesRegex(ValueError,"INVALID_SOURCE_SHA"):
            build_signal_only_research_response(sealed(m5_manifest_tip_sha256="abc"))

    def test_invalid_utc_asof_rejected(self):
        for stamp in ("2026-11-12T19:01:00+07:00","2026-11-12T12:01:00"):
            with self.subTest(stamp=stamp), self.assertRaisesRegex(ValueError,"ASOF"):
                build_signal_only_research_response(sealed(replace(technical(),asof_utc=stamp)))

    def test_forged_full_sha_mode_rejected(self):
        with self.assertRaisesRegex(ValueError,"FORGED_FULL_SHA_MODE"):
            build_signal_only_research_response(
                sealed(m5_full_historical_raw_sha_verified=False))

    def test_forged_rolling_historical_sha_rejected(self):
        with self.assertRaisesRegex(ValueError,"FORGED_ROLLING_SHA_MODE"):
            build_signal_only_research_response(
                sealed(m5_sha_audit_mode=ROLLING_MODE,
                       m5_total_manifest_parent_chain_verified=300,
                       m5_total_archived_manifest_pairs=300,
                       m5_manifest_pairs_full_sha=256,
                       m5_historical_raw_chunks_not_reread=44))

    def test_invalid_chain_counts_rejected(self):
        with self.assertRaisesRegex(ValueError,"INVALID_SEALED_CHAIN_COUNTS"):
            build_signal_only_research_response(
                sealed(m5_total_manifest_parent_chain_verified=1))

    def test_immutable_result(self):
        r=build_signal_only_research_response(sealed())
        with self.assertRaises(Exception):
            r.action="BUY"

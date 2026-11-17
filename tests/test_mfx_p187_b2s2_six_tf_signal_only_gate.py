"""P0.187 end-to-end sealed six-TF -> two-sided F2 owner proposal NO_SIGNAL.

Hermetic test stores use pure in-memory immutable SHA objects, never actual
vendor/OAuth/Drive. SIM price examples cannot become verified actions.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import json
from unittest import TestCase

from mfx_research.p184_paired_f2_owner_review import (
    compile_paired_f2_owner_proposals, TEMPLATE,
)
from mfx_research.p187_b2s2_six_tf_signal_only_gate import (
    VERSION, compose_b2s2_signal_only_gate,
    from_sealed_stores_b2s2_signal_only,
)
from test_mfx_v1_six_tf_sealed_archive_consumer import (
    ASOF, consume, fixtures,
)
from test_mfx_v1_signal_only_six_tf_response import sealed as constructed_sealed
from mfx_research.six_tf_sealed_archive_consumer import (
    D1_HOLD_PUBLIC_STATUS, D1_KNOWN_SOURCE_REVISION_INCIDENT,
)


def proposal():
    return json.loads(TEMPLATE.read_text(encoding="utf-8"))


def proposed_pair():
    packet = proposal()
    x = packet["paired_rows"][0]
    x.update({
        "review_intent": "PROPOSE_FORMULA",
        "b2_formula": "draft B2 close above known high with unknown K",
        "s2_formula": "draft S2 close below known low with unknown K",
        "units": "unapproved candidate units",
        "causal_asof_notes": "CLOSED prefix only",
        "evidence_sha256": "a"*64,
        "rationale": None,
    })
    return packet


def fixture_run(*, owner=None, m5=None, h4=None, d1=None, pins=None,
                asof=ASOF):
    if m5 is None:
        m5,h4,d1,pins=fixtures()
    return from_sealed_stores_b2s2_signal_only(
        m5,h4,d1,asof_utc=asof,
        owner_proposal_packet=proposal() if owner is None else owner,
        fixture_pins=pins,
    )


class P187B2S2SealedSixTfToSignalOnlyTests(TestCase):
    def test_01_real_six_frame_derivation_pipeline_has_no_signal(self):
        r=fixture_run()
        self.assertEqual(r.version,VERSION)
        self.assertEqual(r.frames_present,("M5","M15","M30","H1","H4","D1"))
        self.assertEqual(r.frames_missing_or_stale,())
        self.assertEqual(r.source_technical_status,"SIX_TF_COMPLETE_RESEARCH_ONLY")
        self.assertEqual((r.action,r.stage),("NO_SIGNAL","UNVERIFIED"))
        self.assertEqual((r.numeric_original_approvals,
                          r.numeric_original_pending),(0,36))

    def test_02_explicit_design_mirror_entry_quote_side_not_real_orders(self):
        r=fixture_run()
        self.assertEqual(r.design_roles,(
            ("B2","LONG_DESIGN_ONLY","ASK","BID"),
            ("S2","SHORT_DESIGN_ONLY","BID","ASK"),
        ))
        self.assertIn("B2_S2_MIRRORED_NUMERIC_OWNER_AUTHORITY_UNVERIFIED",
                      r.blockers)
        self.assertEqual(r.broker_orders,0)

    def test_03_public_never_exposes_price_or_approved_side_action(self):
        out=fixture_run().public_summary()
        self.assertIsNone(out["entry_price"])
        self.assertIsNone(out["stop_loss"])
        self.assertIsNone(out["take_profit"])
        self.assertIsNone(out["net_risk_reward"])
        self.assertIsNone(out["publisher_first_known_utc"])
        self.assertFalse(out["may_publish_buy_sell"])
        self.assertEqual(out["action"],"NO_SIGNAL")
        as_json=json.dumps(out,sort_keys=True)
        self.assertNotIn('"open"',as_json)
        self.assertNotIn('"close"',as_json)
        self.assertNotIn('"quote_price"',as_json)

    def test_04_valid_draft_mirror_pair_counts_two_proposals_zero_approvals(self):
        r=fixture_run(owner=proposed_pair())
        self.assertEqual(r.numeric_pairs_proposed,1)
        self.assertEqual(r.numeric_original_pending,36)
        self.assertEqual(r.public_summary()["original_numeric_approvals"],0)
        self.assertEqual(r.action,"NO_SIGNAL")

    def test_05_all_18_drafted_pairs_still_cannot_mint_approval(self):
        x=proposed_pair()
        example=deepcopy(x["paired_rows"][0])
        for index,row in enumerate(x["paired_rows"]):
            if index:
                for k in ("review_intent","b2_formula","s2_formula","units",
                          "causal_asof_notes","evidence_sha256","rationale"):
                    row[k]=example[k]
        r=fixture_run(owner=x)
        self.assertEqual(r.numeric_pairs_proposed,18)
        self.assertEqual(r.numeric_original_approvals,0)
        self.assertFalse(r.may_publish_buy_sell)

    def test_06_incomplete_two_sided_owner_formula_denied_pre_read(self):
        x=proposed_pair()
        x["paired_rows"][0]["s2_formula"]=None
        class Spy:
            reads=0
            def list_names(self,bucket):
                self.reads+=1
                raise AssertionError("Should not touch market source")
            def read(self,bucket,name):
                self.reads+=1
                raise AssertionError("Should not touch market source")
        spy=Spy()
        with self.assertRaises(ValueError):
            from_sealed_stores_b2s2_signal_only(
                spy,spy,spy,asof_utc=ASOF,
                owner_proposal_packet=x,
            )
        self.assertEqual(spy.reads,0)

    def test_07_wrong_source_dossier_is_denied_before_market_reads(self):
        x=proposal()
        x["source"]["original_forex_commit"]="0"*40
        with self.assertRaises(ValueError):
            fixture_run(owner=x)

    def test_08_sealed_real_d1_hold_suppresses_studies_and_actions(self):
        hold=constructed_sealed(
            status=D1_HOLD_PUBLIC_STATUS,
            native_d1_numeric_revision_quarantine_active=True,
            native_d1_numeric_revision_quarantine_incident=(
                D1_KNOWN_SOURCE_REVISION_INCIDENT),
            private_signal_research_suppressed_by_d1_hold=True,
        )
        r=compose_b2s2_signal_only_gate(
            hold,owner_proposal=compile_paired_f2_owner_proposals(proposal()),
        )
        self.assertIn("REAL_D1_SOURCE_REVISION_STILL_QUARANTINED",
                      r.blockers)
        self.assertEqual(r.action,"NO_SIGNAL")
        self.assertEqual(r.source_technical_status,
                         "SIX_TF_SOURCE_QUARANTINED_NO_SIGNAL")

    def test_09_m5_rollback_and_raw_chunk_tamper_never_reach_output(self):
        m,h,d,p=fixtures()
        k=sorted(m.objects["chunk"])[-1]
        m.objects["chunk"][k]["bars"][0]["high"]="1.9"
        with self.assertRaises(ValueError):
            fixture_run(m5=m,h4=h,d1=d,pins=p)

    def test_10_deep_immutable_source_objects_and_no_vendor_io(self):
        m,h,d,p=fixtures()
        before=deepcopy((m.objects,h.objects,d.objects))
        r=fixture_run(m5=m,h4=h,d1=d,pins=p)
        self.assertEqual((m.objects,h.objects,d.objects),before)
        self.assertEqual((r.provider_price_requests,r.drive_market_writes,
                          r.broker_orders),(0,0,0))
        with self.assertRaises(FrozenInstanceError):
            r.action="BUY"

    def test_11_future_and_non_utc_asof_denied(self):
        for asof in (
            ASOF-timedelta(hours=2),
            datetime(2026,11,12,12,1),
            datetime(2026,11,12,19,1,
                     tzinfo=timezone(timedelta(hours=7))),
        ):
            with self.subTest(asof=asof),self.assertRaises(ValueError):
                fixture_run(asof=asof)

    def test_12_source_signed_no_signal_cannot_be_spoofed_into_buy(self):
        with self.assertRaises(ValueError):
            compose_b2s2_signal_only_gate(
                constructed_sealed(may_publish_buy_sell=True),
                owner_proposal=compile_paired_f2_owner_proposals(proposal()),
            )

    def test_13_forged_owner_numeric_signoff_denied(self):
        good=compile_paired_f2_owner_proposals(proposal())
        for key,val in (
            ("original_numeric_rules_approved",36),
            ("mirrored_formula_authenticated",True),
            ("may_publish_buy_sell",True),
            ("action","BUY"),
        ):
            fake=replace(good,**{key:val})
            with self.subTest(key=key),self.assertRaises(ValueError):
                compose_b2s2_signal_only_gate(
                    constructed_sealed(),owner_proposal=fake,
                )

    def test_14_null_on_unknown_owner_not_assumed_as_approved(self):
        with self.assertRaises((ValueError,TypeError)):
            fixture_run(owner={"approved":True})

    def test_15_output_deterministic_and_changed_when_owner_proposes(self):
        a=fixture_run()
        b=fixture_run()
        c=fixture_run(owner=proposed_pair())
        self.assertEqual(a,b)
        self.assertNotEqual(a.owner_proposal_bundle_fingerprint_sha256,
                            c.owner_proposal_bundle_fingerprint_sha256)
        self.assertEqual(a.source_evidence_fingerprint_sha256,
                         c.source_evidence_fingerprint_sha256)

    def test_16_wrong_source_type_denied(self):
        with self.assertRaises(TypeError):
            compose_b2s2_signal_only_gate(
                "not a receipt",
                owner_proposal=compile_paired_f2_owner_proposals(proposal()),
            )

    def test_17_sim_b2s2_buy_sell_pattern_never_merges_into_real_gate(self):
        from test_mfx_v1_p152_sim_signal_risk_vertical_slice import run
        from mfx_research.offline_ema_signals import CandidateAction
        buy, sell = run("B2"), run("S2")
        self.assertIs(buy.experimental_pattern,CandidateAction.BUY)
        self.assertIs(sell.experimental_pattern,CandidateAction.SELL)
        r=fixture_run()
        self.assertEqual(r.action,"NO_SIGNAL")
        self.assertEqual((r.entry_price,r.stop_loss,r.take_profit,
                          r.net_risk_reward),(None,None,None,None))
        self.assertIn("ORIGINAL_36_NUMERIC_SOURCE_DECISIONS_UNAPPROVED",
                      r.blockers)

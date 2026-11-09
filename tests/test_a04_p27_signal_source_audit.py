"""A04/P0.27: 20 independent source-locked 18-zone evidence QA oracles.

Each case uses original Forex 03 paragraph references, frozen Git source
taxonomy or original P0.21 data and explicitly forbids numeric promotion.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest

from forex_trading.catalog import ZONES
from forex_trading.model import ActionIntent, SignalStage, ZonePurpose
from mfx_research.p022_policy_casebook import read_casebook
from mfx_research.p027_signal_source_audit import (
    MATRIX, SOURCE_ANCHORS, SourceEvidenceReceipt,
    _reject_duplicates, read_source_evidence_matrix,
    verify_source_evidence_matrix,
)

# Independently transcribed from the source-locked Forex 03 document readback.
HEADINGS = (
    ("B1",17,27),("B2",28,38),("B3",39,49),("B4",50,60),
    ("B5",61,71),("B6",72,82),("B7",83,93),("B8",94,104),
    ("S1",105,115),("S2",116,126),("S3",127,137),("S4",138,148),
    ("S5",149,159),("S6",160,170),("S7",171,181),("S8",182,192),
    ("FX-S9",231,242),("FX-S10",243,254),
)
LONG = {"B1","B2","B3","B4","B5","B6","B8"}
SHORT = {"S1","S2","S4","S5","S6","S7","FX-S9","FX-S10"}
NONENTRY = {"B7","S3","S8"}


def fixture() -> dict:
    obj=json.loads(Path(MATRIX).read_text(encoding="utf-8"))
    if not isinstance(obj,dict):
        raise AssertionError("P027_MATRIX_TEST_OBJECT_EXPECTED")
    return obj


def rows(v: dict) -> list:
    out=v["rows"]
    if not isinstance(out,list):
        raise AssertionError("P027_TYPED_SOURCE_ROWS")
    return out


def record(v: dict, label: str) -> dict:
    matches=[x for x in rows(v) if x["label"]==label]
    if len(matches)!=1:
        raise AssertionError("P027_TEST_REQUIRES_ONE_LABEL")
    return matches[0]


class P027SourceProofAndApprovalIsolationTests(unittest.TestCase):
    def test_01_original_102_blob_manifest_and_catalog_sha_verified(self):
        proof=read_source_evidence_matrix()
        self.assertIsInstance(proof,SourceEvidenceReceipt)
        self.assertEqual(proof.original_source_commit,
                         "7e1c1c012b1b189be5ad7b9d07756eac012a8309")
        self.assertEqual(proof.original_tree_sha,
                         "5df2058346f6dc96ed5bb02581b139fe2aa2d803")
        self.assertEqual(proof.frozen_catalog_sha,
                         "dc0cd0d7eab7f8603071401aa51723f7e4b8ef20")
        self.assertEqual(len(proof.matrix_git_blob_sha),40)
        self.assertEqual(len(proof.matrix_sha256),64)

    def test_02_catalog_order_18_unique_source_labels_no_fxb9(self):
        proof=read_source_evidence_matrix()
        labels=tuple(x.label for x in proof.entries)
        self.assertEqual(labels,tuple(x.label for x in ZONES))
        self.assertEqual(labels,tuple(x[0] for x in HEADINGS))
        self.assertEqual(len(set(labels)),18)
        self.assertNotIn("FX-B9",labels)
        self.assertEqual(SOURCE_ANCHORS,HEADINGS)

    def test_03_exact_7_long_8_short_3_nonentry_taxonomy(self):
        proof=read_source_evidence_matrix()
        buys={x.label for x in proof.entries if x.catalog_purpose
              is ZonePurpose.ENTRY_LONG_CANDIDATE}
        sells={x.label for x in proof.entries if x.catalog_purpose
               is ZonePurpose.ENTRY_SHORT_CANDIDATE}
        others={x.label for x in proof.entries
                if x.entry_intent_if_later_source_approved is None}
        self.assertEqual(buys,LONG)
        self.assertEqual(sells,SHORT)
        self.assertEqual(others,NONENTRY)
        self.assertEqual((proof.long_entry_candidate_count,
                          proof.short_entry_candidate_count,
                          proof.protective_or_watch_count),(7,8,3))

    def test_04_b7_countertrend_is_watch_not_buy(self):
        item=next(x for x in read_source_evidence_matrix().entries
                  if x.label=="B7")
        self.assertIs(item.catalog_purpose,ZonePurpose.WATCH_ONLY)
        self.assertIsNone(item.entry_intent_if_later_source_approved)
        self.assertEqual(item.action_if_later_approved,"NONE")
        self.assertEqual(item.current_action,"NO_SIGNAL")
        self.assertFalse(item.may_publish)

    def test_05_s3_s8_exit_long_warning_not_short(self):
        for label in ("S3","S8"):
            item=next(x for x in read_source_evidence_matrix().entries
                      if x.label==label)
            self.assertIs(item.catalog_purpose,
                          ZonePurpose.EXIT_LONG_WARNING_ONLY)
            self.assertIsNone(item.entry_intent_if_later_source_approved)
            self.assertEqual(item.entry_quote_side_if_later_approved,"NONE")
            self.assertNotIn(item.label,SHORT)
            self.assertIs(item.stage_now,SignalStage.UNVERIFIED)
            self.assertFalse(item.may_publish)

    def test_06_b2_and_s2_exact_source_audit_phase_indices(self):
        d=fixture()
        for label,start,status in (("B2",28,38),("S2",116,126)):
            v=record(d,label)
            self.assertEqual(v["source_heading"]["paragraph_index"],start)
            self.assertEqual(v["source_status"]["paragraph_index"],status)
            self.assertEqual(tuple(v["phases"][k]["paragraph_index"]
                                   for k in ("R0","R_C","R_E","R_F")),
                             (start+1,start+2,start+3,start+4))
            self.assertIn("Pullback",v["source_heading"]["text"])
            # Independent original 03 directional semantic guard: a changed
            # but plausible-looking R0/CONFIRM text is not source parity.
            context=v["phases"]["R0"]["text"]
            confirm=v["phases"]["R_F"]["text"]
            if label=="B2":
                self.assertIn("HH/HL",context)
                self.assertIn("micro-high",confirm)
            else:
                self.assertIn("LH/LL",context)
                self.assertIn("micro-low",confirm)
            self.assertIn("H1",v["phases"]["R_C"]["text"])
            self.assertIn("M15",v["phases"]["R_E"]["text"])

    def test_07_first_sixteen_manifest_pending_not_approved(self):
        d=fixture()
        for v in rows(d)[:16]:
            s=v["source_status"]["text"]
            self.assertIn("MANIFEST_DRAFT",s)
            self.assertIn("PREDICATES=SPEC_PENDING",s)
            self.assertIn("ACTION_ELIGIBLE=FALSE",s)
        self.assertEqual(len(rows(d)[:16]),16)

    def test_08_fx_s9_s10_design_only_formula_pending(self):
        d=fixture()
        for label in ("FX-S9","FX-S10"):
            v=record(d,label)
            self.assertEqual(v["action_if_later_approved"],"SELL")
            self.assertIn("APPROVED_DESIGN_SCOPE",v["source_status"]["text"])
            self.assertIn("FORMULA_PENDING",v["source_status"]["text"])
            self.assertIn("ACTION_ELIGIBLE=FALSE",v["source_status"]["text"])
            self.assertFalse(v["source_numeric_approved"])

    def test_09_all_four_phases_have_source_anchored_qualitative_quotes(self):
        d=fixture()
        for v in rows(d):
            for phase in ("R0","R_C","R_E","R_F"):
                row=v["phases"][phase]
                self.assertTrue(row["text"].startswith(phase+" "))
                self.assertGreater(len(row["text"]),30)
            self.assertFalse(v["actual_source_qualification"])
        self.assertEqual(len(rows(d)),18)

    def test_10_p21_36_pending_and_14_sim_not_source_approved(self):
        proof=read_source_evidence_matrix()
        self.assertEqual(proof.b2_s2_source_numeric_pending,36)
        self.assertEqual(proof.unapproved_sim_examples,14)
        self.assertEqual(proof.approved_numeric_entry_rules,0)
        self.assertFalse(proof.may_send_verified_buy_sell)

    def test_11_13_non_b2_s2_entry_candidates_unindexed(self):
        proof=read_source_evidence_matrix()
        unmapped=[x for x in proof.entries
                  if x.entry_intent_if_later_source_approved is not None
                  and x.review_scope=="NUMERIC_SOURCE_CASE_NOT_INDEXED"]
        self.assertEqual(len(unmapped),13)
        self.assertEqual(proof.other_entry_candidate_numeric_unmapped,13)
        self.assertEqual(
            {x.label for x in unmapped},(LONG|SHORT)-{"B2","S2"},
        )
        for x in unmapped:
            self.assertFalse(x.source_numeric_approved)

    def test_12_buy_ask_sell_bid_are_entry_not_exit_warning(self):
        proof=read_source_evidence_matrix()
        for x in proof.entries:
            if x.label in LONG:
                self.assertIs(x.entry_intent_if_later_source_approved,
                              ActionIntent.ENTRY_LONG)
                self.assertEqual(x.entry_quote_side_if_later_approved,"ASK")
            elif x.label in SHORT:
                self.assertIs(x.entry_intent_if_later_source_approved,
                              ActionIntent.ENTRY_SHORT)
                self.assertEqual(x.entry_quote_side_if_later_approved,"BID")
            else:
                self.assertIsNone(x.entry_intent_if_later_source_approved)

    def test_13_every_entry_now_unverified_no_signal(self):
        proof=read_source_evidence_matrix()
        for x in proof.entries:
            self.assertEqual(x.current_action,"NO_SIGNAL")
            self.assertIs(x.stage_now,SignalStage.UNVERIFIED)
            self.assertFalse(x.may_publish)
            self.assertFalse(x.source_verified)
        self.assertFalse(proof.may_trade)
        self.assertFalse(proof.may_release)

    def test_14_forged_source_document_or_commit_denied(self):
        for field in ("source_doc_id","commit","tree_sha",
                      "catalog_git_blob_sha","source_doc_approval_class"):
            d=fixture()
            d["source"][field]="FORGED"
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError,
                                            "SOURCE_MATRIX_MISMATCH"):
                    verify_source_evidence_matrix(d)

    def test_15_wrong_phase_and_heading_positions_denied(self):
        for label in ("B2","S2","FX-S9"):
            for key in ("source_heading","source_status"):
                d=fixture()
                record(d,label)[key]["paragraph_index"]+=1
                with self.subTest(label=label,key=key):
                    with self.assertRaisesRegex(ValueError,
                                                "SOURCE_MATRIX_MISMATCH"):
                        verify_source_evidence_matrix(d)
            d=fixture()
            record(d,label)["phases"]["R_F"]["paragraph_index"]+=1
            with self.assertRaisesRegex(ValueError,"SOURCE_MATRIX_MISMATCH"):
                verify_source_evidence_matrix(d)

    def test_16_missing_phase_marker_or_status_action_false_denied(self):
        d=fixture()
        record(d,"B2")["phases"]["R_C"]["text"]="fake"
        with self.assertRaisesRegex(ValueError,"MISSING_QUALITATIVE_PHASE"):
            verify_source_evidence_matrix(d)
        d=fixture()
        record(d,"S2")["source_status"]["text"]=(
            "STATUS: APPROVED NUMERIC; ACTION_ELIGIBLE=TRUE")
        with self.assertRaisesRegex(ValueError,
                                    "NOT_EXECUTABLE_SOURCE_STATUS"):
            verify_source_evidence_matrix(d)

    def test_17_missing_duplicate_or_reordered_source_rows_denied(self):
        d=fixture()
        rows(d).pop()
        with self.assertRaisesRegex(ValueError,"EXACT_18_ZONE_ROWS"):
            verify_source_evidence_matrix(d)
        d=fixture()
        rows(d)[2]=deepcopy(rows(d)[1])
        with self.assertRaisesRegex(ValueError,"SOURCE_MATRIX_MISMATCH"):
            verify_source_evidence_matrix(d)
        d=fixture()
        rows(d).reverse()
        with self.assertRaisesRegex(ValueError,"SOURCE_MATRIX_MISMATCH"):
            verify_source_evidence_matrix(d)

    def test_18_forged_numeric_approval_or_schema_change_denied(self):
        for field,value in (
            ("source_numeric_approved",True),
            ("actual_source_qualification",True),
            ("may_publish",True),
            ("signal_stage_now","CONFIRMED_SIGNAL"),
            ("action_now","BUY"),
        ):
            d=fixture()
            record(d,"B2")[field]=value
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError,"SOURCE_MATRIX_MISMATCH"):
                    verify_source_evidence_matrix(d)
        d=fixture()
        record(d,"B2")["atr_multiple"]=0.5
        with self.assertRaisesRegex(ValueError,"EXACT_KEYS"):
            verify_source_evidence_matrix(d)
        d=fixture()
        d["permissions"]["source_verified_real_buy_sell"]=True
        with self.assertRaisesRegex(ValueError,"SOURCE_MATRIX_MISMATCH"):
            verify_source_evidence_matrix(d)

    def test_19_duplicate_json_key_and_tampered_P21_source_denied(self):
        with self.assertRaisesRegex(ValueError,"DUPLICATE_JSON_KEY"):
            json.loads('{"name":1,"name":2}',object_pairs_hook=_reject_duplicates)
        d=fixture()
        d["source_review"]["b2_s2_number_obligations_pending"]=0
        with self.assertRaisesRegex(ValueError,"SOURCE_MATRIX_MISMATCH"):
            verify_source_evidence_matrix(d)
        d=fixture()
        d["source_review"]["approved_numerical_strategy_count"]=1
        with self.assertRaisesRegex(ValueError,"SOURCE_MATRIX_MISMATCH"):
            verify_source_evidence_matrix(d)

    def test_20_sim_casebook_cannot_upgrade_or_cause_real_io(self):
        proof=read_source_evidence_matrix()
        casebook,_=read_casebook()
        self.assertEqual(casebook["source_rules_approved"],0)
        self.assertEqual(casebook["unapproved_numeric_obligations"],36)
        self.assertFalse(casebook["confirmed_signals_allowed"])
        self.assertEqual(proof.external_provider_calls,0)
        self.assertEqual(proof.actual_drive_price_writes,0)
        self.assertEqual(proof.broker_orders,0)
        self.assertFalse(proof.may_write_real_drive_market_cache)
        self.assertEqual(proof.as_record(),
                         read_source_evidence_matrix().as_record())

"""A04/P0.29 — twenty-two preregistered 8+3 symmetry audit QA gates.

Evidence-only, no live FX data, market inference, executable entry or broker.
"""
from __future__ import annotations

from hashlib import sha1
import json
from pathlib import Path
import unittest

from forex_trading.catalog import ZONES, catalog_counts, validate_catalog
from forex_trading.model import ZonePurpose
from mfx_research.p028e_fxb9_design_overlay import read_fxb9_design_manifest


ROOT = Path("docs")
AUDIT = ROOT / "MFX_A04_P29_ELEVEN_PAIR_SYMMETRY_AUDIT.json"
P27 = ROOT / "MFX_A04_P27_SOURCE_EVIDENCE_MATRIX.json"
P28E = ROOT / "MFX_A04_P28E_FXB9_DESIGN_OVERLAY.json"
P28F = ROOT / "MFX_A04_P28F_S6_FXB9_SYMMETRY_SCOPE.json"
STAGES = {"R0", "R_C", "R_E", "R_F"}


def read(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("P029_REQUIRES_DOCUMENT_OBJECT")
    return document


def git_blob(path: Path) -> str:
    raw = path.read_bytes()
    return sha1(b"blob " + str(len(raw)).encode("ascii") + bytes([0]) + raw).hexdigest()


class P029ElevenPairSymmetryAudit(unittest.TestCase):
    def setUp(self) -> None:
        self.audit = read(AUDIT)
        self.original = read(P27)
        self.old = {r["label"]: r for r in self.original["rows"]}
        self.pairs = self.audit["entry_pairs"]
        self.proposals = self.audit["nonentry_missing_mirrors"]

    def test_01_frozen_original_18_unchanged(self) -> None:
        validate_catalog(ZONES)
        self.assertEqual(len(ZONES), 18)
        self.assertEqual(len(self.original["rows"]), 18)
        self.assertEqual(self.audit["frozen_source"]["source_locked_docs_unchanged"], 11)

    def test_02_p028e_current_mfx_19_unchanged(self) -> None:
        r = read_fxb9_design_manifest()
        self.assertEqual(len(r.extended_labels), 19)
        self.assertEqual((r.extended_buy_candidates, r.short_candidates), (8, 8))
        self.assertEqual(r.non_entry_labels, ("B7", "S3", "S8"))
        self.assertEqual(self.audit["current_mfx_design"]["approved_mfx_design_labels"], 19)

    def test_03_eight_unique_pairs_cover_sixteen_entries(self) -> None:
        self.assertEqual(len(self.pairs), 8)
        self.assertEqual([p["pair_id"] for p in self.pairs],
                         ["E01", "E02", "E03", "E04", "E05", "E06", "E07", "E08"])
        self.assertEqual(
            [(p["buy"]["label"], p["sell"]["label"]) for p in self.pairs],
            [("B1", "S1"), ("B2", "S2"), ("B3", "S4"),
             ("B4", "S5"), ("B5", "S7"), ("B6", "FX-S9"),
             ("B8", "FX-S10"), ("FX-B9", "S6")],
        )
        self.assertEqual(len({p["buy"]["label"] for p in self.pairs}), 8)
        self.assertEqual(len({p["sell"]["label"] for p in self.pairs}), 8)

    def test_04_source_purpose_counts_7_8_3(self) -> None:
        c = catalog_counts(ZONES)
        self.assertEqual(c[ZonePurpose.ENTRY_LONG_CANDIDATE], 7)
        self.assertEqual(c[ZonePurpose.ENTRY_SHORT_CANDIDATE], 8)
        self.assertIs(next(z for z in ZONES if z.label == "B7").purpose,
                      ZonePurpose.WATCH_ONLY)
        self.assertTrue(all(
            next(z for z in ZONES if z.label == k).purpose
            is ZonePurpose.EXIT_LONG_WARNING_ONLY for k in ("S3", "S8")))

    def test_05_exact_source_headings_and_stage_anchors(self) -> None:
        for pair in self.pairs:
            for side in ("buy", "sell"):
                zone = pair[side]
                if zone["label"] == "FX-B9":
                    self.assertFalse(zone["inherited"])
                    self.assertIsNone(zone["source_heading"]["paragraph_index"])
                    continue
                ref = self.old[zone["label"]]
                self.assertTrue(zone["inherited"])
                self.assertEqual(zone["source_heading"], ref["source_heading"])
                self.assertEqual(zone["phases"], ref["phases"])
                self.assertEqual(zone["catalog_purpose"], ref["catalog_purpose"])

    def test_06_all_8_pairs_have_four_source_stages(self) -> None:
        for pair in self.pairs:
            for side in ("buy", "sell"):
                phases = pair[side]["phases"]
                self.assertEqual(set(phases), STAGES)
                self.assertTrue(all(v["text"].strip() for v in phases.values()))
                self.assertEqual(pair["research_signal"], "NO_SIGNAL")

    def test_07_b2_s2_36_unsigned_obligations(self) -> None:
        b2s2 = self.pairs[1]
        self.assertEqual((b2s2["buy"]["label"], b2s2["sell"]["label"]),
                         ("B2", "S2"))
        self.assertEqual(b2s2["blocking_review_topic"],
                         "NUMERIC_SOURCE_OWNER_36_PENDING")
        self.assertEqual(self.audit["strict_gates"][
            "all_pending_original_b2_s2_numeric_requirements"], 36)

    def test_08_b3_s4_predeclared_range_ownership(self) -> None:
        p = self.pairs[2]
        self.assertEqual((p["buy"]["label"], p["sell"]["label"]),
                         ("B3", "S4"))
        for side in ("buy", "sell"):
            self.assertIn("range", p[side]["phases"]["R0"]["text"])
        self.assertEqual(p["blocking_review_topic"],
                         "PREDECLARED_RANGE_REQUIRED")

    def test_09_s6_original_rc_return_to_range_ambiguous(self) -> None:
        p = self.pairs[7]
        self.assertIn("return to range", p["sell"]["phases"]["R_C"]["text"])
        self.assertEqual(p["blocking_review_topic"],
                         "SOURCE_AMBIGUOUS_OUTSIDE_RANGE_S6")
        self.assertEqual(read(P28F)["interpretation"][
            "original_s6_outside_sideways_range_authority"],
            "NOT_PROVEN_FROM_SOURCE")

    def test_10_b4_s5_causal_right_bar_nonidentity(self) -> None:
        p = self.pairs[3]
        self.assertIn("right-bars", p["buy"]["phases"]["R_F"]["text"])
        self.assertIn("Causal first LH", p["sell"]["phases"]["R_F"]["text"])
        self.assertEqual(p["blocking_review_topic"],
                         "FIRST_PIVOT_SYMMETRY_UNPROVEN")

    def test_11_b6_fxs9_near_vs_closed_break(self) -> None:
        p = self.pairs[5]
        self.assertIn("gần upper", p["buy"]["phases"]["R_E"]["text"])
        self.assertIn("M15 CLOSED + VERIFIED", p["sell"]["phases"]["R_E"]["text"])
        self.assertEqual(p["blocking_review_topic"],
                         "EARLY_STAGE_NEAR_VERSUS_BREAK_DELTA")

    def test_12_fxb9_s6_not_numerically_mirrored(self) -> None:
        p = self.pairs[7]
        self.assertEqual(p["family"], "F8_FALSE_BREAK")
        self.assertEqual(p["buy"]["label"], read(P28E)["extension"]["label"])
        self.assertIs(p["numeric_mirror_authorized"], False)
        self.assertIs(p["future_broker_order_authorized"], False)
        self.assertFalse(p["buy"]["source_numeric_approved"])
        self.assertFalse(p["sell"]["source_numeric_approved"])

    def test_13_fx_s11_is_watch_only_mirror_b7(self) -> None:
        p = self.proposals[0]
        self.assertEqual((p["existing"], p["proposed"], p["purpose"]),
                         ("B7", "FX-S11", "WATCH_ONLY"))
        self.assertIn("D1/H4 UPTREND", p["phases"]["R0"])
        self.assertEqual(self.old["B7"]["catalog_purpose"], "WATCH_ONLY")
        self.assertFalse(p["entry_candidate"])

    def test_14_fx_b10_is_exit_short_mirror_s3(self) -> None:
        p = self.proposals[1]
        self.assertEqual((p["existing"], p["proposed"], p["purpose"]),
                         ("S3", "FX-B10", "EXIT_SHORT_WARNING_ONLY"))
        self.assertTrue(p["requires_verified_open_position"])
        self.assertEqual(p["protects"], "SHORT")
        self.assertIn("OPEN_SHORT", p["phases"]["R0"])
        self.assertEqual(self.old["S3"]["catalog_purpose"],
                         "EXIT_LONG_WARNING_ONLY")

    def test_15_fx_b11_is_downside_exhaustion_exit_short(self) -> None:
        p = self.proposals[2]
        self.assertEqual((p["existing"], p["proposed"], p["purpose"]),
                         ("S8", "FX-B11", "EXIT_SHORT_WARNING_ONLY"))
        self.assertEqual(p["protects"], "SHORT")
        self.assertTrue(p["requires_verified_open_position"])
        self.assertIn("acceleration", p["phases"]["R0"])
        self.assertEqual(self.old["S8"]["catalog_purpose"],
                         "EXIT_LONG_WARNING_ONLY")

    def test_16_three_proposals_absent_from_approved_19(self) -> None:
        proposed = {p["proposed"] for p in self.proposals}
        self.assertEqual(proposed, {"FX-S11", "FX-B10", "FX-B11"})
        self.assertFalse(proposed.intersection(
            read_fxb9_design_manifest().extended_labels))
        self.assertTrue(all(p["owner_label_approval"] == "PENDING"
                            for p in self.proposals))
        self.assertEqual(self.audit["authority"]["proposed_label_approval"],
                         "PENDING")

    def test_17_conditional_22_equals_8_8_2_4(self) -> None:
        c = self.audit["conditional_only_if_owner_approves"]
        self.assertEqual((c["entry_long_candidates"],
                          c["entry_short_candidates"],
                          c["watch_only_count"],
                          c["protective_only_count"]), (8, 8, 2, 4))
        self.assertEqual(c["mfx_extended_labels"], 22)
        self.assertEqual(c["total_nonentry_count"], 6)
        self.assertFalse(c["active_design_updated"])

    def test_18_each_proposed_has_four_qualitative_stages(self) -> None:
        for p in self.proposals:
            self.assertEqual(set(p["phases"]), STAGES)
            self.assertTrue(all(v.strip() for v in p["phases"].values()))
            self.assertFalse(p["numeric_predicates_approved"])
            self.assertFalse(p["action_eligible"])

    def test_19_causal_closed_asof_not_future(self) -> None:
        for p in self.proposals:
            self.assertIn("CLOSED M15", p["phases"]["R_E"])
            self.assertTrue(any(
                term in " ".join(p["phases"].values()).lower()
                for term in ("first-known", "as-of", "causal", "known")))
        self.assertTrue(all(p["mirror_classification"] == "QUALITATIVE_ONLY"
                            for p in self.pairs))

    def test_20_watch_protection_overlap_does_not_duplicate_entry(self) -> None:
        x = " ".join(self.audit["cross_overlap_precedence"])
        for token in ("B7", "FX-B11", "S8", "FX-S11", "FX-B10",
                      "S3/S8", "NO_SIGNAL", "research opportunity"):
            self.assertIn(token, x)
        self.assertTrue(all(not p["entry_candidate"] for p in self.proposals))

    def test_21_all_market_publishing_and_broker_gates_closed(self) -> None:
        gates = self.audit["strict_gates"]
        for key in ("source_numeric_approval", "real_data_provider_rights_confirmed",
                    "drive_raw_quote_cache_rights_confirmed",
                    "action_eligible", "publish_alerts", "release_ready"):
            self.assertIs(gates[key], False)
        self.assertEqual(gates["market_provider_calls"], 0)
        self.assertEqual(gates["real_drive_quote_cache_writes"], 0)
        self.assertEqual(gates["broker_orders"], 0)
        self.assertEqual(self.audit["current_mfx_design"][
            "approved_numerical_entry_rules"], 0)

    def test_22_exact_blobs_and_external_blockers_preserved(self) -> None:
        s = self.audit["frozen_source"]
        self.assertEqual(s["commit"],
                         "7e1c1c012b1b189be5ad7b9d07756eac012a8309")
        self.assertEqual(s["tree"], "5df2058346f6dc96ed5bb02581b139fe2aa2d803")
        self.assertEqual(s["evidence_matrix_blob_sha"], git_blob(P27))
        m = self.audit["current_mfx_design"]
        self.assertEqual(m["fxb9_overlay_blob_sha"], git_blob(P28E))
        self.assertEqual(m["s6_review_blob_sha"], git_blob(P28F))
        self.assertIn("/issues/50", self.audit["related_issue"])
        self.assertTrue(all(p["source_numeric_approved"] is False
                            for pair in self.pairs
                            for p in (pair["buy"], pair["sell"])))


if __name__ == "__main__":
    unittest.main()

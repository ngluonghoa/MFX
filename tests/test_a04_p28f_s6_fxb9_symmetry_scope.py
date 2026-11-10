"""A04/P0.28F: Static source-safe S6/FX-B9 symmetry review gates.

No market data, executable signal classifier, or source numeric formulas.
"""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from forex_trading.catalog import ZONES, catalog_counts, validate_catalog
from forex_trading.model import ZonePurpose

HERE = Path("docs")
SCOPE = HERE / "MFX_A04_P28F_S6_FXB9_SYMMETRY_SCOPE.json"
ORIGINAL = HERE / "MFX_A04_P27_SOURCE_EVIDENCE_MATRIX.json"
FXB9 = HERE / "MFX_A04_P28E_FXB9_DESIGN_OVERLAY.json"


def read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("P028F_JSON_OBJECT_REQUIRED")
    return value


def row(label: str) -> dict:
    found = [x for x in read(ORIGINAL)["rows"] if x["label"] == label]
    if len(found) != 1:
        raise ValueError("P028F_SOURCE_ROW_MISSING_OR_DUPLICATED")
    return found[0]


class P028FDirectionalScopeReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.m = read(SCOPE)

    def test_01_frozen_original_count_and_catalog(self) -> None:
        validate_catalog(ZONES)
        self.assertEqual(len(ZONES), 18)
        self.assertEqual(self.m["source"]["original_catalog_count"], 18)
        self.assertEqual(len(read(ORIGINAL)["rows"]), 18)

    def test_02_unchanged_extended_8_8_3(self) -> None:
        counts = catalog_counts(ZONES)
        self.assertEqual(counts[ZonePurpose.ENTRY_LONG_CANDIDATE], 7)
        self.assertEqual(counts[ZonePurpose.ENTRY_SHORT_CANDIDATE], 8)
        x = self.m["counts"]
        self.assertEqual(
            (x["mfx_buy_entry_design_candidates"],
             x["mfx_sell_entry_design_candidates"],
             x["mfx_watch_protective_labels"]),
            (8, 8, 3),
        )
        self.assertEqual(x["mfx_extended_catalog_labels"], 19)

    def test_03_four_exact_polarity_roles(self) -> None:
        items = self.m["ownership_matrix"]
        self.assertEqual(len(items), 4)
        self.assertEqual(
            [(x["key"], x["owner"], x["direction"]) for x in items],
            [
                ("LOWER_RANGE", "B3", "LONG"),
                ("LOWER_STRUCTURAL_OUTSIDE", "FX-B9", "LONG"),
                ("UPPER_RANGE", "S4", "SHORT"),
                ("UPPER_STRUCTURAL_OUTSIDE", "S6", "SHORT"),
            ],
        )

    def test_04_no_additional_short_label(self) -> None:
        x = self.m["interpretation"]
        self.assertTrue(x["do_not_create_ninth_short"])
        self.assertTrue(x["do_not_replace_original_s6"])
        self.assertEqual(set(z.label for z in ZONES if z.label.startswith("S")),
                         {"S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"})

    def test_05_original_s6_wording_remains_ambiguous(self) -> None:
        s6 = row("S6")
        self.assertEqual(s6["source_heading"]["paragraph_index"], 160)
        self.assertEqual(s6["phases"]["R_C"]["paragraph_index"], 162)
        self.assertIn("return to range", s6["phases"]["R_C"]["text"])
        x = self.m["interpretation"]
        self.assertEqual(x["original_s6_rc_phrase"], "return to range")
        self.assertEqual(x["original_s6_outside_sideways_range_authority"],
                         "NOT_PROVEN_FROM_SOURCE")

    def test_06_original_s4_range_ownership(self) -> None:
        s4 = row("S4")
        self.assertEqual(s4["source_heading"]["paragraph_index"], 138)
        self.assertIn("range", s4["phases"]["R0"]["text"])
        self.assertEqual(s4["action_now"], "NO_SIGNAL")

    def test_07_original_b3_range_ownership(self) -> None:
        b3 = row("B3")
        self.assertEqual(b3["source_heading"]["paragraph_index"], 39)
        self.assertIn("range", b3["phases"]["R0"]["text"])
        self.assertEqual(b3["action_now"], "NO_SIGNAL")

    def test_08_original_mfx_fxb9_scope_preserved(self) -> None:
        fx = read(FXB9)
        self.assertEqual(fx["extension"]["label"], "FX-B9")
        self.assertEqual(
            fx["extension"]["mechanism"],
            "BEAR_TRAP_FALSE_BREAKDOWN_OUTSIDE_PREDECLARED_RANGE",
        )
        self.assertFalse(fx["extension"]["action_eligible"])

    def test_09_all_s6_phase_numbers_are_pending(self) -> None:
        descriptions = self.m["proposed_s6_review_phases"]
        self.assertEqual(set(descriptions), {"R0", "R_C", "R_E", "R_F"})
        self.assertEqual(
            self.m["interpretation"]["proposed_scope_status"],
            "DESIGN_REVIEW_ONLY_OWNER_NUMERIC_APPROVAL_PENDING",
        )
        self.assertFalse(self.m["authority"]["numeric_formula_approved"])

    def test_10_no_extrapolated_symmetric_economics(self) -> None:
        self.assertTrue(self.m["interpretation"]["no_numeric_threshold_copied_from_fxb9"])
        self.assertTrue(self.m["interpretation"]["no_symmetric_expectancy_claim"])
        self.assertIn("NO_AUTOMATIC_SYMMETRIC_THRESHOLDS",
                      self.m["overlaps"]["no_copying"])

    def test_11_fail_closed_conflicting_context_and_dedup(self) -> None:
        self.assertEqual(self.m["overlaps"]["unclear_range_context"],
                         "UNKNOWN_NO_SIGNAL")
        self.assertEqual(self.m["overlaps"]["duplicate_origin_event"],
                         "ONE_RESEARCH_OPPORTUNITY_ONLY_NO_PUBLISH")

    def test_12_hard_stop_authority_and_source_identity(self) -> None:
        original = self.m["source"]
        self.assertEqual(
            original["frozen_commit"],
            "7e1c1c012b1b189be5ad7b9d07756eac012a8309",
        )
        self.assertEqual(
            original["frozen_tree"],
            "5df2058346f6dc96ed5bb02581b139fe2aa2d803",
        )
        self.assertFalse(self.m["authority"]["original_forex_rule_changed"])
        self.assertEqual(self.m["counts"]["numeric_approved_mfx_entry_rules"], 0)
        self.assertEqual(self.m["counts"]["b2_s2_pending_numerical_requirements"], 36)
        gates = self.m["stop_gates"]
        for name in ("source_numeric_approved", "action_eligible",
                     "may_publish", "licensed_forex_market_feed",
                     "real_market_drive_cache_enabled",
                     "broker_orders_enabled", "release_ready"):
            self.assertIs(gates[name], False)
        self.assertEqual(gates["current_action"], "NO_SIGNAL")
        self.assertEqual(gates["signal_stage"], "UNVERIFIED")


if __name__ == "__main__":
    unittest.main()

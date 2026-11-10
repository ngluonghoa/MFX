"""P043 source-review inventory tests; no real providers or numeric strategy approval."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from mfx_research.p043_remaining_entry_source_gaps import (
    EXPECTED_PAIRS, P029_FILE, PHASES, VERSION,
    read_remaining_entry_gap_report, review_14_unapproved_entries,
)

def source() -> dict[str, object]:
    return json.loads(P029_FILE.read_text(encoding="utf-8"))


class P043RemainingEntryGapTests(unittest.TestCase):
    def test_01_exact_14_remaining_entries_and_56_phase_slots(self) -> None:
        r = read_remaining_entry_gap_report()
        self.assertEqual((len(r.rules), r.remaining_entry_labels,
                          r.qualitative_phase_review_slots), (14, 14, 56))
        self.assertEqual(sum(len(x.phases) for x in r.rules), 56)

    def test_02_seven_exact_pairs_and_design_roles(self) -> None:
        r = read_remaining_entry_gap_report()
        actual = tuple((a.pair_id, a.label, b.label)
                       for a, b in zip(r.rules[::2], r.rules[1::2]))
        self.assertEqual(actual, EXPECTED_PAIRS)
        self.assertTrue(all(a.side == "BUY" for a in r.rules[::2]))
        self.assertTrue(all(b.side == "SELL" for b in r.rules[1::2]))

    def test_03_b2_s2_remain_distinct_36_source_decisions(self) -> None:
        r = read_remaining_entry_gap_report()
        self.assertNotIn("B2", {x.label for x in r.rules})
        self.assertNotIn("S2", {x.label for x in r.rules})
        self.assertEqual(r.separately_indexed_b2_s2_labels, 2)
        self.assertEqual(r.original_b2_s2_numeric_owner_decisions_pending, 36)
        self.assertEqual(r.total_mfx_entry_labels, 16)

    def test_04_thirteen_frozen_original_one_mfx_only_b9(self) -> None:
        r = read_remaining_entry_gap_report()
        original = [x for x in r.rules if x.source_scope == "ORIGINAL_FOREX_FROZEN_03"]
        extensions = [x for x in r.rules if x.source_scope == "MFX_APPROVED_DESIGN_ONLY"]
        self.assertEqual(len(original), 13)
        self.assertEqual([x.label for x in extensions], ["FX-B9"])
        self.assertIsNone(extensions[0].source_heading_paragraph_index)
        self.assertTrue(all(p.original_source_paragraph_index is None
                            for p in extensions[0].phases))

    def test_05_original_52_phase_anchors_are_causal_source_indices(self) -> None:
        r = read_remaining_entry_gap_report()
        self.assertEqual(r.original_source_anchored_phases, 52)
        self.assertEqual(r.mfx_design_only_phases_without_original_anchor, 4)
        for rule in r.rules:
            with self.subTest(label=rule.label):
                self.assertEqual(tuple(p.phase for p in rule.phases), PHASES)
                if rule.source_heading_paragraph_index is not None:
                    self.assertEqual(
                        tuple(p.original_source_paragraph_index
                              for p in rule.phases),
                        tuple(rule.source_heading_paragraph_index + i
                              for i in range(1, 5)),
                    )

    def test_06_all_formula_units_evidence_empty_not_signed(self) -> None:
        r = read_remaining_entry_gap_report()
        for rule in r.rules:
            with self.subTest(label=rule.label):
                self.assertFalse(rule.source_numeric_approval)
                self.assertFalse(rule.eligible_for_confirmed_signal)
                self.assertEqual(rule.action, "NO_SIGNAL")
                for p in rule.phases:
                    self.assertEqual(p.quantitative_predicate_status,
                                     "PENDING_OWNER_POLICY")
                    self.assertIsNone(p.approved_numeric_formula)
                    self.assertIsNone(p.approved_units)
                    self.assertIsNone(p.verified_owner_evidence)
                    self.assertEqual(p.action, "NO_SIGNAL")

    def test_07_total_safety_is_no_market_cache_or_orders(self) -> None:
        r = read_remaining_entry_gap_report()
        self.assertEqual((r.owner_signed_numeric_approvals_across_all_entries,
                          r.real_market_provider_calls,
                          r.real_drive_market_quote_writes,
                          r.published_confirmed_signals, r.broker_orders),
                         (0, 0, 0, 0, 0))
        self.assertEqual(r.action, "NO_SIGNAL")
        self.assertFalse(r.release_ready)

    def test_08_qualitative_asymmetry_is_preserved(self) -> None:
        r = read_remaining_entry_gap_report()
        pairs = {x.pair_id: x for x in r.rules}
        self.assertEqual(pairs["E06"].unresolved_source_topic,
                         "EARLY_STAGE_NEAR_VERSUS_BREAK_DELTA")
        self.assertIn("near", pairs["E06"].pair_qualitative_difference)
        self.assertEqual(pairs["E08"].unresolved_source_topic,
                         "SOURCE_AMBIGUOUS_OUTSIDE_RANGE_S6")
        self.assertIn("outside", pairs["E08"].pair_qualitative_difference)

    def test_09_strict_snapshot_version_not_promotion(self) -> None:
        r = read_remaining_entry_gap_report()
        self.assertEqual(r.version, VERSION)
        self.assertEqual(r.original_forex_source_labels, 18)
        self.assertEqual(r.approved_mfx_design_labels, 22)
        self.assertEqual({x.label for x in r.rules},
                         {z for _, a, b in EXPECTED_PAIRS for z in (a, b)})

    def test_10_forged_numeric_mirror_approval_rejected(self) -> None:
        s = deepcopy(source())
        s["entry_pairs"][2]["numeric_mirror_authorized"] = True
        with self.assertRaisesRegex(ValueError, "P043_NO_NUMERIC_MIRROR"):
            review_14_unapproved_entries(s)

    def test_11_fake_original_b9_source_claim_rejected(self) -> None:
        s = deepcopy(source())
        s["entry_pairs"][7]["buy"]["inherited"] = True
        with self.assertRaisesRegex(ValueError, "P043_FAKE_ORIGINAL_SOURCE"):
            review_14_unapproved_entries(s)

    def test_12_fake_mfx_extension_source_anchor_rejected(self) -> None:
        s = deepcopy(source())
        s["entry_pairs"][7]["buy"]["phases"]["R_F"]["paragraph_index"] = 165
        with self.assertRaisesRegex(ValueError, "P043_FORGED_EXTENSION"):
            review_14_unapproved_entries(s)

    def test_13_original_phase_misaligned_source_index_rejected(self) -> None:
        s = deepcopy(source())
        s["entry_pairs"][3]["sell"]["phases"]["R_E"]["paragraph_index"] += 1
        with self.assertRaisesRegex(ValueError, "P043_SOURCE_PHASE_PARAGRAPH"):
            review_14_unapproved_entries(s)

    def test_14_missing_required_phase_rejected(self) -> None:
        s = deepcopy(source())
        del s["entry_pairs"][4]["buy"]["phases"]["R0"]
        with self.assertRaisesRegex(ValueError, "P043_EXACT_FOUR_SOURCE"):
            review_14_unapproved_entries(s)

    def test_15_label_substitution_that_falsifies_role_rejected(self) -> None:
        s = deepcopy(source())
        s["entry_pairs"][6]["sell"]["label"] = "B7"
        with self.assertRaisesRegex(ValueError, "P043_EXACT_MIRROR_PAIR"):
            review_14_unapproved_entries(s)

    def test_16_frozen_source_revision_drift_rejected(self) -> None:
        s = deepcopy(source())
        s["frozen_source"]["commit"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "P043_FROZEN_SOURCE"):
            review_14_unapproved_entries(s)

    def test_17_pinned_file_byte_drift_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / "audit.json"
            file.write_bytes(P029_FILE.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "P043_PINNED_P029"):
                read_remaining_entry_gap_report(file)

    def test_18_original_source_numeric_approval_forgery_rejected(self) -> None:
        s = deepcopy(source())
        s["entry_pairs"][3]["buy"]["source_numeric_approved"] = True
        with self.assertRaisesRegex(ValueError, "P043_NO_NUMERIC_MIRROR"):
            review_14_unapproved_entries(s)


if __name__ == "__main__":
    unittest.main()

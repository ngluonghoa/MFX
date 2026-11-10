"""A04/P0.30: 24 preregistered owner-approved 22-zone DESIGN gates.

No numerical entry predicate or executable user alert is authorized.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest

from forex_trading.catalog import ZONES, catalog_counts, validate_catalog
from forex_trading.model import ZonePurpose
from mfx_research.p028e_fxb9_design_overlay import read_fxb9_design_manifest
from mfx_research.p030_approved_nonentry_design import (
    ADDITIONS, CONTRACT, CONTRACT_SHA, MIRRORS, P028E_OVERLAY, P028E_SHA,
    P029_AUDIT, P029_AUDIT_SHA, ROLES, SCHEMA, SOURCE_CATALOG_SHA,
    VERSION, _blob, _pairs_unique, nonentry_design_preview,
    read_22_zone_design_manifest, verify_22_zone_design_manifest,
)

LONG = ZonePurpose.ENTRY_LONG_CANDIDATE.value
SHORT = ZonePurpose.ENTRY_SHORT_CANDIDATE.value
WATCH = ZonePurpose.WATCH_ONLY.value
EXIT_LONG = ZonePurpose.EXIT_LONG_WARNING_ONLY.value
EXIT_SHORT = "EXIT_SHORT_WARNING_ONLY"


def original_manifest() -> dict:
    return json.loads(Path(CONTRACT).read_text(encoding="utf-8"))


class P030ApprovedNonEntryMirrors(unittest.TestCase):
    def setUp(self) -> None:
        self.receipt = read_22_zone_design_manifest()
        self.raw = original_manifest()

    def test_01_original_18_catalog_unmodified(self) -> None:
        validate_catalog(ZONES)
        self.assertEqual(len(ZONES), 18)
        self.assertEqual(self.receipt.original_labels,
                         tuple(x.label for x in ZONES))

    def test_02_prior_19_overlay_is_still_historical_and_valid(self) -> None:
        prior = read_fxb9_design_manifest()
        self.assertEqual(len(prior.extended_labels), 19)
        self.assertEqual(prior.non_entry_labels, ("B7", "S3", "S8"))
        self.assertEqual(self.receipt.previous_mfx_19_labels,
                         prior.extended_labels)

    def test_03_exact_22_approved_design_labels(self) -> None:
        zones = self.receipt.zones
        self.assertEqual(len(zones), 22)
        self.assertEqual(len({x.label for x in zones}), 22)
        self.assertEqual(self.raw["counts"]["effective_mfx_design_labels"], 22)

    def test_04_long_entry_candidate_count_stays_eight(self) -> None:
        self.assertEqual(len(self.receipt.entry_long_labels), 8)
        self.assertEqual(
            self.receipt.entry_long_labels,
            ("B1", "B2", "B3", "B4", "B5", "B6", "B8", "FX-B9"),
        )
        self.assertEqual(catalog_counts(ZONES)[
            ZonePurpose.ENTRY_LONG_CANDIDATE], 7)

    def test_05_short_entry_candidate_count_stays_eight(self) -> None:
        self.assertEqual(len(self.receipt.entry_short_labels), 8)
        self.assertEqual(
            self.receipt.entry_short_labels,
            ("S1", "S2", "S4", "S5", "S6", "S7", "FX-S9", "FX-S10"),
        )

    def test_06_watch_labels_exact_b7_and_fx_s11(self) -> None:
        self.assertEqual(self.receipt.watch_labels, ("B7", "FX-S11"))
        self.assertEqual(
            self.raw["counts"]["watch_only_labels"], ["B7", "FX-S11"])

    def test_07_four_protective_labels_two_per_side(self) -> None:
        self.assertEqual(self.receipt.exit_long_warning_labels, ("S3", "S8"))
        self.assertEqual(self.receipt.exit_short_warning_labels,
                         ("FX-B10", "FX-B11"))
        self.assertEqual(self.raw["counts"]["total_protection_labels"], 4)

    def test_08_only_three_new_names_are_added(self) -> None:
        self.assertEqual(self.receipt.approved_new_labels, ADDITIONS)
        diff = {x.label for x in self.receipt.zones} - set(
            self.receipt.previous_mfx_19_labels)
        self.assertEqual(diff, set(ADDITIONS))
        self.assertEqual(self.raw["counts"][
            "newly_approved_mfx_design_labels"], 3)

    def test_09_original_18_and_previous_19_order_are_subsequences(self) -> None:
        self.assertEqual(
            tuple(x.label for x in self.receipt.zones[:19]),
            self.receipt.previous_mfx_19_labels,
        )
        self.assertEqual(
            tuple(x.label for x in self.receipt.zones
                  if x.label in self.receipt.original_labels),
            self.receipt.original_labels,
        )

    def test_10_fx_s11_mirrors_b7_and_cannot_sell_to_open(self) -> None:
        x = self.receipt.zones[19]
        self.assertEqual((x.label, x.mirror_of, x.purpose),
                         ("FX-S11", "B7", WATCH))
        self.assertFalse(x.can_open_new_position)
        self.assertFalse(x.requires_verified_open_short)
        self.assertEqual(nonentry_design_preview(
            "FX-S11", False).action, "NO_SIGNAL")

    def test_11_fx_b10_mirrors_s3_and_is_not_buy_entry(self) -> None:
        x = self.receipt.zones[20]
        self.assertEqual((x.label, x.mirror_of, x.purpose),
                         ("FX-B10", "S3", EXIT_SHORT))
        self.assertTrue(x.requires_verified_open_short)
        self.assertFalse(x.can_open_new_position)

    def test_12_fx_b11_mirrors_s8_and_is_not_buy_entry(self) -> None:
        x = self.receipt.zones[21]
        self.assertEqual((x.label, x.mirror_of, x.purpose),
                         ("FX-B11", "S8", EXIT_SHORT))
        self.assertTrue(x.requires_verified_open_short)
        self.assertFalse(x.can_open_new_position)

    def test_13_no_verified_short_claim_means_research_watch_only(self) -> None:
        for label in ("FX-B10", "FX-B11"):
            r = nonentry_design_preview(label, False)
            self.assertFalse(r.position_gate_satisfied_by_claim)
            self.assertEqual(r.research_display, "NO_POSITION_WATCH_ONLY")
            self.assertEqual(r.action, "NO_SIGNAL")
            self.assertFalse(r.may_publish)
            self.assertFalse(r.may_auto_exit)
            r2 = nonentry_design_preview(label, True)
            self.assertTrue(r2.position_gate_satisfied_by_claim)
            self.assertFalse(r2.source_verified)
            self.assertEqual(r2.action, "NO_SIGNAL")
            self.assertFalse(r2.may_auto_exit)
            self.assertEqual(r2.broker_orders, 0)

    def test_14_original_long_exit_s3_s8_stay_unchanged(self) -> None:
        old = {z.label: z for z in ZONES}
        self.assertIs(old["S3"].purpose, ZonePurpose.EXIT_LONG_WARNING_ONLY)
        self.assertIs(old["S8"].purpose, ZonePurpose.EXIT_LONG_WARNING_ONLY)
        self.assertEqual([z.label for z in self.receipt.zones
                          if z.purpose == EXIT_LONG], ["S3", "S8"])

    def test_15_all_three_have_four_qualitative_stages(self) -> None:
        for zone in self.raw["new_nonentry_design_labels"]:
            self.assertEqual(zone["stage_names"], ["R0", "R_C", "R_E", "R_F"])
            self.assertEqual(set(zone["stage_hypotheses"]),
                             {"R0", "R_C", "R_E", "R_F"})
            self.assertEqual(zone["numeric_thresholds"], {})
            self.assertFalse(zone["approved_numeric_formula"])

    def test_16_closed_candle_and_asof_caveats_are_preserved(self) -> None:
        for zone in self.raw["new_nonentry_design_labels"]:
            self.assertIn("CLOSED M15", zone["stage_hypotheses"]["R_E"])
            self.assertTrue(any(term in
                                " ".join(zone["stage_hypotheses"].values())
                                for term in ("as-of", "causal", "first-known")))
            self.assertIn(
                "UNVERIFIED_CLOSED_CANDLE_OR_FUTURE_KNOWN_PIVOT",
                zone["invalid_if"])

    def test_17_research_event_dedup_and_no_role_promotion(self) -> None:
        c = self.raw["cross_zone_governance"]
        self.assertTrue(c["same_instrument_calendar_origin_one_research_opportunity"])
        self.assertTrue(c["no_opposite_entry_from_protection"])
        self.assertTrue(c["entry_and_position_protection_are_distinct_roles"])
        self.assertTrue(c["source_context_unknown_no_signal"])

    def test_18_exact_original_forex_frozen_ids_and_catalog_blob(self) -> None:
        p = self.raw["provenance"]
        self.assertEqual(p["original_forex_commit"],
                         "7e1c1c012b1b189be5ad7b9d07756eac012a8309")
        self.assertEqual(p["original_forex_tree"],
                         "5df2058346f6dc96ed5bb02581b139fe2aa2d803")
        self.assertEqual(p["original_catalog_git_blob_sha"],
                         SOURCE_CATALOG_SHA)
        catalog = Path("src/forex_trading/catalog.py")
        self.assertEqual(_blob(catalog.read_bytes()), SOURCE_CATALOG_SHA)

    def test_19_exact_previous_p028e_and_p029_golden_sha(self) -> None:
        p = self.raw["provenance"]
        self.assertEqual(_blob(P028E_OVERLAY.read_bytes()), P028E_SHA)
        self.assertEqual(_blob(P029_AUDIT.read_bytes()), P029_AUDIT_SHA)
        self.assertEqual(p["legacy_fxb9_design_overlay_git_blob_sha"],
                         P028E_SHA)
        self.assertEqual(p["p029_audit_git_blob_sha"], P029_AUDIT_SHA)

    def test_20_duplicate_extra_or_missing_json_fields_denied(self) -> None:
        with self.assertRaisesRegex(ValueError, "P030_DUPLICATE_JSON_KEY"):
            json.loads('{"schema":"a","schema":"b"}',
                       object_pairs_hook=_pairs_unique)
        extra = deepcopy(self.raw)
        extra["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "P030_EXACT_KEYS_REQUIRED"):
            verify_22_zone_design_manifest(extra)
        missing = deepcopy(self.raw)
        missing["new_nonentry_design_labels"][0].pop("purpose")
        with self.assertRaisesRegex(ValueError, "P030_EXACT_KEYS_REQUIRED"):
            verify_22_zone_design_manifest(missing)

    def test_21_manifest_self_blob_sha_is_pinned(self) -> None:
        self.assertEqual(_blob(CONTRACT.read_bytes()), CONTRACT_SHA)
        wrong = deepcopy(self.raw)
        wrong["counts"]["effective_mfx_design_labels"] = 23
        with self.assertRaisesRegex(ValueError, "P030_APPROVED_SCOPE_MISMATCH"):
            verify_22_zone_design_manifest(wrong)

    def test_22_no_live_quote_drive_broker_or_user_alert_rights(self) -> None:
        x = self.raw["stop_gates"]
        self.assertEqual(x["all_research_stage"], "UNVERIFIED")
        self.assertEqual(x["current_action"], "NO_SIGNAL")
        for name in ("eligible_for_trading", "eligible_for_live_signal",
                     "eligible_for_live_exit_warning", "release_ready"):
            self.assertFalse(x[name])
        for name in ("live_data_provider_calls",
                     "real_drive_market_quote_cache_writes", "broker_orders"):
            self.assertEqual(x[name], 0)
        for zone in self.raw["new_nonentry_design_labels"]:
            self.assertFalse(zone["may_warn_live"])
            self.assertFalse(zone["may_automate_exit"])
            self.assertFalse(zone["may_create_broker_order"])

    def test_23_all_entry_numerics_stay_unapproved_and_36_pending(self) -> None:
        self.assertEqual(self.receipt.numerical_rules_approved, 0)
        self.assertEqual(self.receipt.b2_s2_source_obligations_pending, 36)
        self.assertEqual(self.raw["counts"]["approved_entry_numeric_predicates"], 0)
        self.assertEqual(self.raw["counts"][
            "original_b2_s2_numeric_requirements_pending"], 36)
        self.assertFalse(self.raw["approval"]["numeric_formula_approved"])
        self.assertEqual(self.receipt.live_signals, 0)

    def test_24_version_anti_rollback_and_typed_preview_is_non_actionable(self) -> None:
        self.assertEqual(self.raw["schema"], SCHEMA)
        self.assertEqual(self.raw["version"], VERSION)
        self.assertEqual(
            self.raw["approval"]["authority"],
            "USER_APPROVED_THREE_NONENTRY_MFX_DESIGN_MIRRORS",
        )
        self.assertEqual(tuple(z["label"] for z in
                               self.raw["new_nonentry_design_labels"]), ADDITIONS)
        self.assertEqual(tuple(z["purpose"] for z in
                               self.raw["new_nonentry_design_labels"]), ROLES)
        self.assertEqual(tuple(z["mirror_of"] for z in
                               self.raw["new_nonentry_design_labels"]), MIRRORS)
        for label in ADDITIONS:
            r = nonentry_design_preview(label, True)
            self.assertFalse(r.may_open_position)
            self.assertFalse(r.may_auto_exit)
            self.assertFalse(r.may_publish)
        for denied in ("B1", "S6", "FX-B9", "BAD", ""):
            with self.assertRaisesRegex(ValueError,
                                        "P030_ONLY_APPROVED_NONENTRY_NEW_LABELS"):
                nonentry_design_preview(denied, False)
        with self.assertRaisesRegex(TypeError, "P030_TYPED_DESIGN_PREVIEW_REQUIRED"):
            nonentry_design_preview("FX-B10", 1)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()

"""P0.180: hermetic price-redacted fresh-epoch overlap reason classification."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from unittest import TestCase

from mfx_cache.native_d1_fresh_epoch import audit_fresh_epoch
from mfx_cache.p180_d1_overlap_diagnosis import (
    VERSION, diagnose_p171_overlap_source,
)
from test_mfx_p168_independent_h4_d1_hold_cache import D1_LABELS, batch
from test_mfx_p171_d1_fresh_epoch import fresh, original_sha, prepared


def audited():
    store, _ = prepared()
    state = audit_fresh_epoch(store, origin_v1_sha=original_sha())
    return store, state


def changed_refetch():
    # This is a real native typed source fixture, not forged stored SHA metadata.
    return batch(
        "1day", D1_LABELS + ("2026-11-12", "2026-11-13"),
        amend="2026-11-12",
    )


class P180FreshEpochOverlapDiagnosisTests(TestCase):
    def test_01_identical_sha_overlap_is_not_a_quarantine_diagnosis(self):
        _, state = audited()
        with self.assertRaisesRegex(ValueError, "REQUIRES_CONFIRMED_OVERLAP"):
            diagnose_p171_overlap_source(fresh(), state=state)

    def test_02_revised_native_bar_is_changed_not_missing(self):
        store, state = audited()
        before = deepcopy(store.files)
        r = diagnose_p171_overlap_source(changed_refetch(), state=state)
        self.assertEqual(r["schema"], VERSION)
        self.assertEqual(r["conflict_classification"], "CHANGED_OVERLAP_SHA")
        self.assertEqual(r["overlap_labels_missing_count"], 0)
        self.assertGreater(r["overlap_sha_changed_count"], 0)
        self.assertEqual(sum(r[k] for k in (
            "overlap_labels_missing_count", "overlap_sha_changed_count",
            "overlap_sha_unchanged_count",
        )), r["previous_indexed_labels"])
        self.assertEqual(store.files, before)
        self.assertEqual(store.puts, 2)

    def test_03_missing_previous_label_is_not_claimed_vendor_revision(self):
        _, state = audited()
        supplied = batch(
            "1day", ("2026-11-12", "2026-11-13", "2026-11-14"),
        )
        r = diagnose_p171_overlap_source(supplied, state=state)
        self.assertEqual(r["conflict_classification"], "MISSING_OVERLAP_LABELS")
        self.assertGreater(r["overlap_labels_missing_count"], 0)
        self.assertEqual(r["source_vendor_correction_cause_proven"], False)

    def test_04_missing_and_sha_changed_are_independently_counted(self):
        _, state = audited()
        x = changed_refetch()
        x = replace(x, closed_bars=tuple(
            b for b in x.closed_bars if b.native_open_label != "2026-11-11"
        ))
        r = diagnose_p171_overlap_source(x, state=state)
        self.assertEqual(r["conflict_classification"], "MISSING_AND_CHANGED")
        self.assertGreater(r["overlap_labels_missing_count"], 0)
        self.assertGreater(r["overlap_sha_changed_count"], 0)

    def test_05_no_private_ohlc_sha_or_per_day_label_in_public_receipt(self):
        _, state = audited()
        r = diagnose_p171_overlap_source(changed_refetch(), state=state)
        rendered = json.dumps(r, sort_keys=True)
        for forbidden in (
            "2026-11-11", "2026-11-12", "EUR/USD",
            '"open"', '"high"', '"low"', '"close"',
            "raw_price", "source_object_id", "refresh_token",
        ):
            self.assertNotIn(forbidden, rendered)
        for k in ("provider_price_requests_added", "drive_reads_added",
                  "drive_writes", "broker_orders"):
            self.assertEqual(r[k], 0)
        for k in ("source_vendor_correction_cause_proven",
                  "source_publisher_first_known_verified",
                  "original_numeric_rules_approved",
                  "may_publish_buy_sell", "source_promotion_authorized",
                  "source_quarantine_bypassed"):
            self.assertIs(r[k], False)

    def test_06_unverified_state_and_invalid_source_fail_closed(self):
        _, state = audited()
        for bad in (None, "unknown", replace(state, last_manifest=None)):
            with self.assertRaisesRegex(ValueError, "STATE_REQUIRED"):
                diagnose_p171_overlap_source(changed_refetch(), state=bad)
        with self.assertRaises(ValueError):
            diagnose_p171_overlap_source(
                replace(changed_refetch(), source="INVALID"), state=state,
            )

    def test_07_malformed_sha_and_duplicate_index_rejected(self):
        _, state = audited()
        m = deepcopy(state.last_manifest)
        m["recent_native_bar_index"][0]["sha256"] = "INVALID_SHA"
        with self.assertRaisesRegex(ValueError, "MALFORMED"):
            diagnose_p171_overlap_source(
                changed_refetch(), state=replace(state, last_manifest=m))
        m = deepcopy(state.last_manifest)
        m["recent_native_bar_index"].append(
            deepcopy(m["recent_native_bar_index"][0]))
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            diagnose_p171_overlap_source(
                changed_refetch(), state=replace(state, last_manifest=m))

    def test_08_existing_fail_closed_writer_catches_only_exact_code(self):
        source = Path("tools/run_mfx_native_htf_incremental_commit.py").read_text()
        self.assertIn(
            'str(error) == "P171_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE"',
            source,
        )
        self.assertIn("diagnose_p171_overlap_source(", source)
        self.assertIn("MFX_P180_D1_OVERLAP_SHA_DIAGNOSED_FAIL_CLOSED", source)
        self.assertIn("MFX_P180_DIAGNOSTIC_UNAVAILABLE_FAIL_CLOSED", source)
        self.assertIn("            raise\n", source)
        self.assertNotIn("MFX_P180_D1_AUTO_REBASE", source)

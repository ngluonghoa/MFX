"""P0.59 MFX native SHA revision forensic witness, no extra Drive/vendor calls.

All tests use the real full SHA archive auditor with synthetic in-memory data.
No new scheduled job, REST, Google Drive credentials, price log, or broker.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
from unittest import TestCase

from mfx_cache.native_htf_sha_forensics import (
    NativeAuditReadThroughWitness, classify_stored_vs_refetched_native,
)
from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.native_htf_incremental import (
    IncrementalFetchPlan, validate_incremental_source,
)
from tools.mfx_native_htf_drive_seal import (
    NativeArchiveState, audit_native_archive,
)
from test_mfx_v1_six_tf_sealed_archive_consumer import (
    ReadOnlyStore, _native, _seed_native,
)

H4 = ("2026-11-12 00:00:00", "2026-11-12 04:00:00",
      "2026-11-12 08:00:00", "2026-11-12 12:00:00")
D1 = ("2026-11-09", "2026-11-10", "2026-11-11")
REVISION = "P059_SOURCE_NATIVE_REVISION_QUARANTINE"
MISSING = "P059_SOURCE_MISSING_SHA_OVERLAP"


class SpyStore(ReadOnlyStore):
    def __init__(self):
        super().__init__()
        self.list_count = 0
        self.read_count = 0

    def list_names(self, bucket):
        self.list_count += 1
        return super().list_names(bucket)

    def read(self, bucket, name):
        self.read_count += 1
        return super().read(bucket, name)


def audited_scope(interval="4h", labels=None):
    if labels is None:
        labels = H4 if interval == "4h" else D1
    store = SpyStore()
    _seed_native(store, interval, labels)
    capture = NativeAuditReadThroughWitness(store)
    archive = audit_native_archive(
        capture, symbol="EUR/USD", interval=interval)
    recent = capture.verified_recent_rows(
        archive, symbol="EUR/USD", interval=interval)
    batch = _native(interval, labels)
    return store, archive, recent, batch, capture


def plan(interval):
    return IncrementalFetchPlan(
        symbol="EUR/USD", interval=interval,
        status="INCREMENTAL_FETCH_REQUIRED",
        request={"symbol": "EUR/USD", "interval": interval},
        last_native_open_label=None,
        latest_expected_closed_label="2026-11-12",
        calendar_slots_behind=1, overlap_bar_count=2,
        provider_requests_planned=1,
    )


def classify(interval="4h", changed=None, labels=None, error=REVISION):
    _, state, old, fresh, _ = audited_scope(interval, labels)
    if changed is not None:
        fresh = replace(fresh, closed_bars=tuple(
            changed(bar) for bar in fresh.closed_bars))
    return classify_stored_vs_refetched_native(
        previous=state.last_manifest, old_verified=old,
        fresh=fresh, quarantine_error=error)


class NativeForensicWitnessTests(TestCase):
    def test_01_actual_full_sha_audited_h4_witness_exact(self):
        _, s, old, _, _ = audited_scope()
        self.assertEqual(len(old), len(H4))
        self.assertEqual([r.native_open_label for r in old], list(H4))
        self.assertEqual(
            [r.sha256() for r in old],
            [e["sha256"] for e in s.last_manifest["recent_native_bar_index"]])

    def test_02_actual_full_sha_audited_d1_witness_exact(self):
        _, s, old, _, _ = audited_scope("1day")
        self.assertEqual([r.native_open_label for r in old], list(D1))
        self.assertEqual(
            [r.sha256() for r in old],
            [e["sha256"] for e in s.last_manifest["recent_native_bar_index"]])

    def test_03_witness_adds_no_underlying_drive_list_or_read(self):
        spy_a = SpyStore()
        spy_b = SpyStore()
        _seed_native(spy_a, "4h", H4)
        _seed_native(spy_b, "4h", H4)
        archive_a = audit_native_archive(
            spy_a, symbol="EUR/USD", interval="4h")
        wrapper = NativeAuditReadThroughWitness(spy_b)
        archive_b = audit_native_archive(
            wrapper, symbol="EUR/USD", interval="4h")
        wrapper.verified_recent_rows(
            archive_b, symbol="EUR/USD", interval="4h")
        self.assertEqual(spy_a.read_count, spy_b.read_count)
        self.assertEqual(spy_a.list_count, spy_b.list_count)
        self.assertEqual(archive_a, archive_b)

    def test_04_witness_has_no_put_or_mutation_method(self):
        _, _, _, _, observer = audited_scope()
        self.assertFalse(hasattr(observer, "put_if_absent"))
        self.assertFalse(hasattr(observer, "post"))
        self.assertFalse(hasattr(observer, "patch"))
        self.assertFalse(hasattr(observer, "delete"))

    def test_05_witness_without_a_completed_audit_fails_closed(self):
        _, state, _, _, _ = audited_scope()
        naked = NativeAuditReadThroughWitness(ReadOnlyStore())
        with self.assertRaisesRegex(ValueError, "RECENT_RAW_INDEX_MISSING"):
            naked.verified_recent_rows(
                state, symbol="EUR/USD", interval="4h")

    def test_06_witness_wrong_symbol_does_not_attest(self):
        _, state, _, _, obs = audited_scope()
        with self.assertRaises(ValueError):
            obs.verified_recent_rows(
                state, symbol="GBP/USD", interval="4h")

    def test_07_witness_wrong_interval_does_not_attest(self):
        _, state, _, _, obs = audited_scope()
        with self.assertRaises(ValueError):
            obs.verified_recent_rows(
                state, symbol="EUR/USD", interval="1day")

    def test_08_witness_wrong_state_type_denied(self):
        _, _, _, _, obs = audited_scope()
        with self.assertRaisesRegex(ValueError, "FULL_SHA_AUDIT_REQUIRED"):
            obs.verified_recent_rows(
                {}, symbol="EUR/USD", interval="4h")

    def test_09_witness_forged_index_shas_denied(self):
        _, state, _, _, obs = audited_scope()
        tampered = dict(state.last_manifest)
        tampered["recent_native_bar_index"] = [
            dict(x) for x in tampered["recent_native_bar_index"]]
        tampered["recent_native_bar_index"][-1]["sha256"] = "0"*64
        with self.assertRaisesRegex(ValueError, "NOT_ATTESTED"):
            obs.verified_recent_rows(
                replace(state, last_manifest=tampered),
                symbol="EUR/USD", interval="4h")

    def test_10_silent_source_chunk_mutation_fails_original_SHA_audit(self):
        store = ReadOnlyStore()
        _seed_native(store, "4h", H4)
        name = next(iter(store.objects["chunk"]))
        store.objects["chunk"][name]["bars"][0]["close"] = "1.1100"
        obs = NativeAuditReadThroughWitness(store)
        with self.assertRaises(ValueError):
            audit_native_archive(obs, symbol="EUR/USD", interval="4h")

    def test_11_empty_archive_attestation_safe(self):
        store = ReadOnlyStore()
        obs = NativeAuditReadThroughWitness(store)
        state = audit_native_archive(obs, symbol="EUR/USD", interval="4h")
        self.assertEqual(
            obs.verified_recent_rows(
                state, symbol="EUR/USD", interval="4h"), ())

    def test_12_empty_archive_with_untrusted_rows_denied(self):
        _, _, _, _, obs = audited_scope()
        state = NativeArchiveState(None, None, 0, 0, ())
        with self.assertRaisesRegex(ValueError, "EMPTY_ARCHIVE_INCONSISTENT"):
            obs.verified_recent_rows(
                state, symbol="EUR/USD", interval="4h")

    def test_13_same_numeric_OHLC_but_different_text_precision(self):
        report = classify(changed=lambda bar: replace(
            bar, open="1.100" if bar.native_open_label == H4[0] else bar.open))
        self.assertEqual(report["equal_numeric_text_only_count"], 1)
        self.assertEqual(report["numeric_ohlc_changed_count"], 0)
        self.assertFalse(
            report["stored_vs_refetched_numeric_ohlc_difference_observed"])

    def test_14_same_numeric_OHLC_but_timezone_provenance_differs(self):
        report = classify(changed=lambda bar: replace(
            bar, exchange_timezone_origin="PROVIDER_META"
            if bar.native_open_label == H4[1]
            else bar.exchange_timezone_origin))
        self.assertEqual(report["equal_numeric_metadata_only_count"], 1)
        self.assertEqual(report["numeric_ohlc_changed_count"], 0)

    def test_15_true_numeric_price_change_observed_in_already_fetched(self):
        report = classify(changed=lambda bar: replace(
            bar, close="1.1012" if bar.native_open_label == H4[2] else bar.close))
        self.assertEqual(report["numeric_ohlc_changed_count"], 1)
        self.assertTrue(
            report["stored_vs_refetched_numeric_ohlc_difference_observed"])
        self.assertFalse(
            report["source_vendor_revision_cause_independently_attributed"])
        self.assertFalse(report["actual_numeric_price_revision_confirmed"])

    def test_16_numeric_and_formatting_change_is_classified_numeric(self):
        report = classify(changed=lambda bar: replace(
            bar, close="1.1012", open="1.100"))
        self.assertEqual(report["numeric_ohlc_changed_count"], len(H4))
        self.assertEqual(report["equal_numeric_text_only_count"], 0)

    def test_17_text_and_metadata_both_change_without_numeric_price(self):
        report = classify(changed=lambda bar: replace(
            bar, open="1.100",
            exchange_timezone_origin="PROVIDER_META"))
        self.assertEqual(
            report["equal_numeric_text_and_metadata_count"], len(H4))
        self.assertEqual(report["numeric_ohlc_changed_count"], 0)

    def test_18_d1_nov11_single_numeric_change_vs_15_unmodified_model(self):
        report = classify(
            interval="1day", labels=D1,
            changed=lambda b: replace(
                b, high="1.1021" if b.native_open_label == "2026-11-11"
                else b.high))
        self.assertEqual(report["interval"], "1day")
        self.assertEqual(report["first_changed_label"], "2026-11-11")
        self.assertEqual(report["last_changed_label"], "2026-11-11")
        self.assertEqual(report["numeric_ohlc_changed_count"], 1)
        self.assertEqual(report["overlap_sha_unchanged_count"], 2)

    def test_19_d1_nov11_single_metadata_change_without_numeric(self):
        report = classify(
            interval="1day", labels=D1,
            changed=lambda b: replace(
                b, exchange_timezone_origin="PROVIDER_META"
                if b.native_open_label == "2026-11-11"
                else b.exchange_timezone_origin))
        self.assertEqual(report["interval"], "1day")
        self.assertEqual(report["equal_numeric_metadata_only_count"], 1)
        self.assertEqual(report["numeric_ohlc_changed_count"], 0)

    def test_20_multiple_different_sha_change_categories_sum_exactly(self):
        def change(bar):
            if bar.native_open_label == H4[0]:
                return replace(bar, open="1.100")
            if bar.native_open_label == H4[1]:
                return replace(bar, exchange_timezone_origin="PROVIDER_META")
            if bar.native_open_label == H4[2]:
                return replace(bar, low="1.0989")
            return bar
        report = classify(changed=change)
        self.assertEqual(report["overlap_sha_changed_count"], 3)
        self.assertEqual(report["equal_numeric_text_only_count"], 1)
        self.assertEqual(report["equal_numeric_metadata_only_count"], 1)
        self.assertEqual(report["numeric_ohlc_changed_count"], 1)

    def test_21_missing_prior_overlap_only_no_price_claim(self):
        _, state, old, batch, _ = audited_scope()
        new = replace(batch, closed_bars=batch.closed_bars[1:])
        report = classify_stored_vs_refetched_native(
            previous=state.last_manifest, old_verified=old,
            fresh=new, quarantine_error=MISSING)
        self.assertEqual(report["overlap_labels_missing_count"], 1)
        self.assertEqual(report["overlap_sha_changed_count"], 0)
        self.assertEqual(report["numeric_ohlc_changed_count"], 0)
        self.assertFalse(
            report["stored_vs_refetched_numeric_ohlc_difference_observed"])

    def test_22_invalid_quarantine_code_fails_closed(self):
        _, state, old, batch, _ = audited_scope()
        with self.assertRaises(ValueError):
            classify_stored_vs_refetched_native(
                previous=state.last_manifest, old_verified=old,
                fresh=batch, quarantine_error="P059_ALLOW_REVISION")

    def test_23_untampered_batch_cannot_be_classified_as_quarantine(self):
        _, state, old, batch, _ = audited_scope()
        with self.assertRaisesRegex(ValueError, "DIAGNOSTIC_MISMATCH"):
            classify_stored_vs_refetched_native(
                previous=state.last_manifest, old_verified=old,
                fresh=batch, quarantine_error=REVISION)

    def test_24_fake_old_sha_row_rejected(self):
        _, state, old, batch, _ = audited_scope()
        bad = (replace(old[0], close="1.1012"),)+old[1:]
        with self.assertRaisesRegex(ValueError, "OLD_ROWS_NOT_SHA_ATTESTED"):
            classify_stored_vs_refetched_native(
                previous=state.last_manifest, old_verified=bad,
                fresh=replace(batch, closed_bars=(
                    replace(batch.closed_bars[0], close="1.1013"),)
                    +batch.closed_bars[1:]),
                quarantine_error=REVISION)

    def test_25_malformed_price_nan_never_classified(self):
        _, state, old, batch, _ = audited_scope()
        new = replace(batch, closed_bars=(
            replace(batch.closed_bars[0], close="NaN"),)
            +batch.closed_bars[1:])
        with self.assertRaisesRegex(ValueError, "PRICE_COMPARISON_INVALID|SOURCE_SCOPE_INVALID"):
            classify_stored_vs_refetched_native(
                previous=state.last_manifest, old_verified=old,
                fresh=new, quarantine_error=REVISION)

    def test_26_bad_returned_symbol_never_classified(self):
        _, state, old, batch, _ = audited_scope()
        changed = replace(batch, closed_bars=(
            replace(batch.closed_bars[0], symbol="GBP/USD"),)
            +batch.closed_bars[1:])
        with self.assertRaisesRegex(ValueError, "SOURCE_SCOPE_INVALID"):
            classify_stored_vs_refetched_native(
                previous=state.last_manifest, old_verified=old,
                fresh=changed, quarantine_error=REVISION)

    def test_27_summary_no_price_leaks_for_numeric_comparison(self):
        report = classify(changed=lambda b: replace(
            b, close="1.1012"))
        out = json.dumps(report, sort_keys=True)
        for token in ("1.1000", "1.1010", "1.1012",
                      "refresh_token", "apikey", "chunk_name"):
            self.assertNotIn(token, out)
        self.assertFalse(report["raw_old_or_new_price_in_output"])

    def test_28_classification_does_not_add_provider_or_drive_calls(self):
        store, state, old, fresh, _ = audited_scope()
        before = (store.read_count, store.list_count)
        fresh = replace(fresh, closed_bars=tuple(
            replace(b, open="1.100") for b in fresh.closed_bars))
        report = classify_stored_vs_refetched_native(
            previous=state.last_manifest, old_verified=old,
            fresh=fresh, quarantine_error=REVISION)
        self.assertEqual((store.read_count, store.list_count), before)
        self.assertEqual(report["additional_vendor_calls"], 0)
        self.assertEqual(report["additional_drive_gets"], 0)
        self.assertEqual(report["drive_writes"], 0)
        self.assertEqual(report["broker_orders"], 0)

    def test_29_original_validate_source_quarantine_is_still_enforced(self):
        _, state, old, batch, _ = audited_scope()
        del old
        fresh = replace(batch, closed_bars=(
            replace(batch.closed_bars[0], close="1.1012"),)
            +batch.closed_bars[1:])
        with self.assertRaisesRegex(ValueError, REVISION):
            validate_incremental_source(
                fresh, previous=state.last_manifest, plan=plan("4h"))

    def test_30_source_wiring_rethrows_quarantine_without_writes(self):
        source = Path("tools/run_mfx_native_htf_incremental_commit.py").read_text()
        self.assertIn("NativeAuditReadThroughWitness", source)
        self.assertIn("classify_stored_vs_refetched_native(", source)
        self.assertIn("MFX_P059_NATIVE_OVERLAP_FORENSICS_NO_DRIVE_WRITE", source)
        self.assertIn("            raise\n        proposal =", source)
        self.assertNotIn("P059_RETRY_WITHOUT_SHA", source)

    def test_31_github_scheduled_source_requests_unchanged(self):
        source = Path("tools/run_mfx_native_htf_incremental_commit.py").read_text()
        self.assertEqual(source.count("_read_payload("), 1)
        self.assertIn('os.environ.get("MFX_REAL_CACHE_ENABLED")', source)
        self.assertIn("GITHUB_EVENT_NAME", source)

    def test_32_metadata_change_not_overstated_as_vendor_root_cause(self):
        report = classify(changed=lambda b: replace(
            b, exchange_timezone_origin="PROVIDER_META"))
        self.assertFalse(
            report["source_vendor_revision_cause_independently_attributed"])
        self.assertFalse(
            report["source_mutation_or_quarantine_override_authorized"])
        self.assertFalse(report["source_numeric_signals_approved"])

    def test_33_buffer_preserves_only_latest_16_for_long_h4_chunk(self):
        labels = tuple(
            f"2026-11-{day:02d} {hour:02d}:00:00"
            for day in (10, 11, 12) for hour in (0, 4, 8, 12, 16, 20)
        )
        _, state, old, _, _ = audited_scope("4h", labels)
        self.assertEqual(len(old), 16)
        self.assertEqual(old[0].native_open_label, labels[-16])
        self.assertEqual(old[-1].native_open_label, labels[-1])
        self.assertEqual(len(state.last_manifest["recent_native_bar_index"]), 16)

    def test_34_witness_read_passthrough_does_not_change_price_payload(self):
        store, _, _, _, _ = audited_scope()
        witness = NativeAuditReadThroughWitness(store)
        name = store.list_names("chunk")[0]
        self.assertEqual(witness.read("chunk", name), store.read("chunk", name))

    def test_35_errors_and_immutable_archive_have_no_trade_authority(self):
        report = classify(changed=lambda b: replace(b, close="1.1012"))
        self.assertEqual(report["status"],
                         "NATIVE_SOURCE_SHA_QUARANTINE_UNRESOLVED_NO_SIGNAL")
        self.assertFalse(report["source_numeric_signals_approved"])
        self.assertTrue(report["quarantine_still_enforced"])

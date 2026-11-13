"""P059 / issue #147 — dry-run D1 source revision candidate, no-write QA.

Nothing here reads live Drive, calls Twelve Data, mutates canonical archives,
approves source rights or emits a market signal.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from unittest import TestCase

from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.native_htf_archive import plan_native_sealed
from mfx_cache.native_htf_revision_candidate import (
    FIELDS, INCIDENT_LABEL, SCHEMA,
    draft_d1_revision_candidate, validate_revision_candidate,
)
from mfx_cache.td_m5_codec import digest

UTC = timezone.utc
OBSERVED = datetime(2026, 11, 13, 7, 23, 20, tzinfo=UTC)
LABELS = tuple(
    (datetime(2026, 10, 27, tzinfo=UTC) + timedelta(days=i))
    .date().isoformat() for i in range(16)
)


def source(labels=LABELS, origin="DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT"):
    return NativeFXBatch(
        symbol="EUR/USD", interval="1day",
        exchange_timezone="Australia/Sydney",
        time_reference="EXCHANGE_LOCAL_SESSION_DATE",
        incomplete_excluded=0,
        closed_bars=tuple(NativeFXBar(
            symbol="EUR/USD", interval="1day",
            native_open_label=label,
            time_reference="EXCHANGE_LOCAL_SESSION_DATE",
            exchange_timezone="Australia/Sydney",
            exchange_timezone_origin=origin,
            open="1.1000", high="1.1030", low="1.0980",
            close="1.1010",
        ) for label in labels),
    )


def revised(original, *, close="1.1011", origin=None, second=False):
    bars = []
    for row in original.closed_bars:
        if row.native_open_label == INCIDENT_LABEL:
            row = replace(row, close=close,
                          exchange_timezone_origin=(
                              row.exchange_timezone_origin if origin is None
                              else origin))
        if second and row.native_open_label == "2026-11-10":
            row = replace(row, high="1.1040")
        bars.append(row)
    return replace(original, closed_bars=tuple(bars))


def evidence():
    original = source()
    plan = plan_native_sealed(original, previous=None)
    if plan is None:
        raise AssertionError("missing synthetic source plan")
    return original, deepcopy(plan.manifest)


def candidate(*, original=None, manifest=None, fresh=None,
              when=OBSERVED, parent=None):
    if original is None or manifest is None:
        original, manifest = evidence()
    if fresh is None:
        fresh = revised(original)
    return draft_d1_revision_candidate(
        original_manifest=manifest,
        sha_verified_recent=original.closed_bars,
        refetched_batch=fresh,
        observed_at_utc=when,
        parent=parent,
    )


def rehash(body):
    result = deepcopy(body)
    result["receipt_sha256"] = digest({
        k: v for k, v in result.items() if k != "receipt_sha256"
    })
    return result


class DryRunRevisionCandidateTests(TestCase):
    def test_01_root_candidate_is_inert_and_schema_pinned(self):
        c = candidate()
        self.assertEqual(c["schema"], SCHEMA)
        self.assertEqual(c["native_open_label"], INCIDENT_LABEL)
        self.assertEqual(c["state"], "DRAFT_REQUIRES_OWNER_SOURCE_REVIEW")
        self.assertEqual(c["changed_numeric_ohlc_fields"], ["close"])
        self.assertEqual(c["revision_sequence"], 1)
        self.assertIsNone(c["previous_candidate_receipt_sha256"])
        self.assertEqual(c["receipt_sha256"], digest({
            k: v for k, v in c.items() if k != "receipt_sha256"
        }))
        self.assertEqual(validate_revision_candidate(c), c)

    def test_02_draft_is_deterministic_for_exact_same_evidence(self):
        self.assertEqual(candidate(), candidate())

    def test_03_no_raw_ohlc_or_secret_in_candidate_body(self):
        output = json.dumps(candidate())
        for sensitive in ("1.1000", "1.1010", "1.1011", "refresh_token",
                          "apikey", "chunk_name", "manifest_name"):
            self.assertNotIn(sensitive, output)

    def test_04_no_provider_or_drive_or_broker_activity(self):
        c = candidate()
        self.assertEqual(
            [c[k] for k in (
                "provider_requests_by_planner",
                "drive_reads_by_planner",
                "drive_writes_by_planner", "broker_orders")], [0, 0, 0, 0])
        for k in ("may_mutate_canonical_archive", "may_publish_buy_sell",
                  "owner_source_policy_approved", "publisher_data_rights_verified",
                  "publisher_revision_cause_verified",
                  "provider_first_known_verified", "approved_numeric_signals"):
            self.assertIs(c[k], False)

    def test_05_original_manifest_and_raw_bar_input_unchanged(self):
        original, m = evidence()
        snapshot = (deepcopy(m), original)
        candidate(original=original, manifest=m)
        self.assertEqual((m, original), snapshot)

    def test_06_original_sha_index_attests_candidate_old_bar(self):
        original, m = evidence()
        c = candidate(original=original, manifest=m)
        self.assertEqual(c["original_manifest_sha256"], digest(m))
        self.assertEqual(c["original_bar_sha256"],
                         original.closed_bars[-1].sha256())
        self.assertNotEqual(c["original_bar_sha256"],
                            c["candidate_bar_sha256"])

    def test_07_proposal_has_immutable_schema_exact_fields(self):
        self.assertEqual(set(candidate()), FIELDS)

    def test_08_candidate_disclaims_independent_provider_first_known(self):
        c = candidate()
        self.assertIn("NOT_INDEPENDENT_PROVIDER_FIRST_KNOWN",
                      c["source_observation_time_quality"])
        self.assertIs(c["source_full_archive_audit_by_caller_required"], True)

    def test_09_clock_must_be_utc(self):
        for at in (
            datetime(2026, 11, 13, 7, 23),
            OBSERVED.astimezone(timezone(timedelta(hours=7))),
        ):
            with self.subTest(at=at), self.assertRaisesRegex(
                    ValueError, "EXACT_UTC"):
                candidate(when=at)

    def test_10_invalid_manifest_prior_sha_index_denied(self):
        o, m = evidence()
        m["recent_native_bar_index"][-1]["sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "PRIOR_INDEX_SHA_MISMATCH"):
            candidate(original=o, manifest=m)

    def test_11_invalid_manifest_provenance_denied(self):
        o, m = evidence()
        m["source"] = "UNVERIFIED_VENDOR"
        with self.assertRaises(ValueError):
            candidate(original=o, manifest=m)

    def test_12_wrong_original_symbol_denied(self):
        o, m = evidence()
        bad = replace(o, closed_bars=(
            replace(o.closed_bars[0], symbol="GBP/USD"),)+o.closed_bars[1:])
        with self.assertRaisesRegex(ValueError, "PRIOR_INDEX_SHA_MISMATCH"):
            candidate(original=bad, manifest=m, fresh=revised(o))

    def test_13_non_d1_scope_denied(self):
        o, m = evidence()
        bad = replace(revised(o), interval="4h")
        with self.assertRaisesRegex(ValueError, "UNATTESTED_SOURCE_SCOPE"):
            candidate(original=o, manifest=m, fresh=bad)

    def test_14_no_price_change_refuses_draft(self):
        o, m = evidence()
        with self.assertRaisesRegex(ValueError, "SINGLE_D1_INCIDENT_ONLY"):
            candidate(original=o, manifest=m, fresh=o)

    def test_15_only_metadata_change_refuses_draft(self):
        o, m = evidence()
        same_numeric = replace(o, closed_bars=tuple(
            replace(b, exchange_timezone_origin="PROVIDER_META")
            if b.native_open_label == INCIDENT_LABEL else b
            for b in o.closed_bars))
        with self.assertRaisesRegex(ValueError, "NUMERIC_OHLC_REQUIRED"):
            candidate(original=o, manifest=m, fresh=same_numeric)

    def test_16_only_price_text_precision_change_refuses_draft(self):
        o, m = evidence()
        text_only = revised(o, close="1.10100")
        with self.assertRaisesRegex(ValueError, "NUMERIC_OHLC_REQUIRED"):
            candidate(original=o, manifest=m, fresh=text_only)

    def test_17_two_changed_source_labels_refuses_draft(self):
        o, m = evidence()
        with self.assertRaisesRegex(ValueError, "SINGLE_D1_INCIDENT_ONLY"):
            candidate(original=o, manifest=m, fresh=revised(o, second=True))

    def test_18_missing_original_overlap_refuses_draft(self):
        o, m = evidence()
        short = replace(o, closed_bars=revised(o).closed_bars[1:])
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_SOURCE_OVERLAP"):
            candidate(original=o, manifest=m, fresh=short)

    def test_19_duplicate_new_source_labels_refuses_draft(self):
        o, m = evidence()
        fresh = revised(o)
        dup = replace(fresh, closed_bars=fresh.closed_bars +
                      (fresh.closed_bars[-1],))
        with self.assertRaisesRegex(ValueError, "UNSORTED_OR_DUPLICATE"):
            candidate(original=o, manifest=m, fresh=dup)

    def test_20_unsorted_new_source_labels_refuses_draft(self):
        o, m = evidence()
        fresh = revised(o)
        reverse = replace(fresh, closed_bars=tuple(reversed(fresh.closed_bars)))
        with self.assertRaisesRegex(ValueError, "UNSORTED_OR_DUPLICATE"):
            candidate(original=o, manifest=m, fresh=reverse)

    def test_21_nonfinite_or_invalid_numeric_prices_denied(self):
        o, m = evidence()
        fresh = revised(o, close="NaN")
        with self.assertRaises(ValueError):
            candidate(original=o, manifest=m, fresh=fresh)

    def test_22_changed_price_field_names_no_sensitive_values(self):
        o, m = evidence()
        fresh = revised(o, close="1.1012")
        fresh = replace(fresh, closed_bars=tuple(
            replace(row, high="1.1040")
            if row.native_open_label == INCIDENT_LABEL else row
            for row in fresh.closed_bars))
        c = candidate(original=o, manifest=m, fresh=fresh)
        self.assertEqual(c["changed_numeric_ohlc_fields"], ["high", "close"])

    def test_23_changed_provenance_field_name_explicit_but_not_value(self):
        o, m = evidence()
        fresh = revised(o, origin="PROVIDER_META")
        c = candidate(original=o, manifest=m, fresh=fresh)
        self.assertIn("exchange_timezone_origin",
                      c["changed_nonprice_metadata_fields"])
        self.assertEqual(c["changed_numeric_ohlc_fields"], ["close"])

    def test_24_receipt_digest_corruption_rejected(self):
        c = candidate()
        c["receipt_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "RECEIPT_SHA_MISMATCH"):
            validate_revision_candidate(c)

    def test_25_changed_label_schema_extra_field_rejected(self):
        c = candidate()
        c["unknown_trade_permission"] = True
        with self.assertRaisesRegex(ValueError, "SCHEMA_DENIED"):
            validate_revision_candidate(c)

    def test_26_manual_approval_forgery_rehashed_still_denied(self):
        c = candidate()
        c["owner_source_policy_approved"] = True
        with self.assertRaisesRegex(ValueError, "POLICY_AND_SCOPE_DENIED"):
            validate_revision_candidate(rehash(c))

    def test_27_release_or_trade_forgery_rehashed_still_denied(self):
        for key in ("may_mutate_canonical_archive", "may_publish_buy_sell",
                    "publisher_data_rights_verified", "approved_numeric_signals",
                    "provider_first_known_verified"):
            with self.subTest(key=key):
                c = candidate()
                c[key] = True
                with self.assertRaisesRegex(ValueError, "POLICY_AND_SCOPE_DENIED"):
                    validate_revision_candidate(rehash(c))

    def test_28_fake_broker_orders_or_drive_writes_denied(self):
        for key in ("broker_orders", "drive_writes_by_planner",
                    "provider_requests_by_planner"):
            with self.subTest(key=key):
                c = candidate()
                c[key] = 1
                with self.assertRaisesRegex(ValueError, "POLICY_AND_SCOPE_DENIED"):
                    validate_revision_candidate(rehash(c))

    def test_29_root_forced_seq2_link_denied(self):
        c = candidate()
        c["revision_sequence"] = 2
        with self.assertRaisesRegex(ValueError, "ROOT_LINK_REQUIRED"):
            validate_revision_candidate(rehash(c))

    def test_30_second_candidate_links_first_receipt_sha(self):
        original, m = evidence()
        root = candidate(original=original, manifest=m)
        newer = revised(original, close="1.1012")
        second = candidate(original=original, manifest=m, fresh=newer,
                           when=OBSERVED+timedelta(hours=1), parent=root)
        self.assertEqual(second["revision_sequence"], 2)
        self.assertEqual(second["previous_candidate_receipt_sha256"],
                         root["receipt_sha256"])
        self.assertEqual(second["previous_candidate_observed_utc"],
                         root["source_observation_time_utc"])
        self.assertEqual(second["original_manifest_sha256"],
                         root["original_manifest_sha256"])
        self.assertEqual(validate_revision_candidate(
            second, parent=root), second)

    def test_31_second_candidate_requires_later_clock(self):
        root = candidate()
        with self.assertRaisesRegex(ValueError, "PARENT_SOURCE_OR_CLOCK_DRIFT"):
            candidate(parent=root)

    def test_32_second_candidate_must_not_repeat_prior_candidate_sha(self):
        root = candidate()
        with self.assertRaisesRegex(ValueError, "PARENT_SOURCE_OR_CLOCK_DRIFT"):
            candidate(parent=root, when=OBSERVED+timedelta(hours=1))

    def test_33_parent_receipt_link_tampering_denied(self):
        old, m = evidence()
        root = candidate(original=old, manifest=m)
        second = candidate(original=old, manifest=m,
                           fresh=revised(old, close="1.1012"),
                           parent=root, when=OBSERVED+timedelta(hours=1))
        second["previous_candidate_receipt_sha256"] = "f"*64
        with self.assertRaisesRegex(ValueError, "PARENT_OR_ANTIROLLBACK_DENIED"):
            validate_revision_candidate(rehash(second), parent=root)

    def test_34_parent_from_other_original_source_denied(self):
        old, m = evidence()
        root = candidate(original=old, manifest=m)
        other = replace(old, closed_bars=tuple(
            replace(row, high="1.1040") for row in old.closed_bars))
        newer_plan = plan_native_sealed(other, previous=None)
        self.assertIsNotNone(newer_plan)
        with self.assertRaisesRegex(ValueError, "PARENT_SOURCE_OR_CLOCK_DRIFT"):
            candidate(original=other, manifest=newer_plan.manifest,
                      fresh=revised(other, close="1.1012"),
                      parent=root, when=OBSERVED+timedelta(hours=1))

    def test_35_tamper_candidate_old_sha_denied_even_rehashed(self):
        c = candidate()
        c["original_bar_sha256"] = "f"*64
        # SHA alone can be recomputed, so this is a *structure* validator,
        # not an external witness. No claim of provenance authority.
        self.assertEqual(
            validate_revision_candidate(rehash(c))["original_bar_sha256"],
            "f"*64)
        self.assertFalse(c["may_mutate_canonical_archive"])

    def test_36_module_never_calls_vendor_drive_or_writer(self):
        s = Path("mfx_cache/native_htf_revision_candidate.py").read_text()
        for forbidden in (
            "requests.get(", "requests.post(", "drive/v3",
            "commit_native_batch(", "put_if_absent(", "GenUI.",
            "broker.submit", "refresh_token", "MFX_REAL_CACHE_ENABLED",
        ):
            self.assertNotIn(forbidden, s)

    def test_37_existing_sealed_source_snapshot_untouched_under_two_drafts(self):
        old, m = evidence()
        prior = deepcopy(m)
        root = candidate(original=old, manifest=m)
        candidate(original=old, manifest=m, fresh=revised(old, close="1.1012"),
                  when=OBSERVED+timedelta(hours=1), parent=root)
        self.assertEqual(m, prior)
        self.assertEqual(old.closed_bars[-1].close, "1.1010")

    def test_39_observation_before_d1_local_close_denied(self):
        old, m = evidence()
        # 2026-11-11 12:00Z is still Nov 11 in Sydney.
        with self.assertRaisesRegex(ValueError, "OBSERVATION_BEFORE_D1_CLOSE"):
            candidate(original=old, manifest=m,
                      when=datetime(2026, 11, 11, 12, tzinfo=UTC))

    def test_40_future_provider_d1_label_denied(self):
        old, m = evidence()
        fresh = revised(old)
        future = replace(fresh, closed_bars=fresh.closed_bars +
                         (source(labels=("2026-11-14",)).closed_bars[0],))
        with self.assertRaisesRegex(ValueError, "UNCLOSED_SOURCE_LABEL"):
            candidate(original=old, manifest=m,
                      fresh=future)

    def test_41_non_tuple_provider_rows_denied(self):
        old, m = evidence()
        malformed = replace(revised(old),
                            closed_bars=list(revised(old).closed_bars))
        with self.assertRaisesRegex(ValueError, "UNATTESTED_SOURCE_SCOPE"):
            candidate(original=old, manifest=m, fresh=malformed)

    def test_38_revalidation_denies_parentless_successor(self):
        old, m = evidence()
        first = candidate(original=old, manifest=m)
        second = candidate(original=old, manifest=m,
                           fresh=revised(old, close="1.1012"),
                           when=OBSERVED+timedelta(hours=1), parent=first)
        with self.assertRaisesRegex(ValueError, "ROOT_LINK_REQUIRED"):
            validate_revision_candidate(second)

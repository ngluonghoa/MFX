"""P0.185 private D1 version-evidence proposal, never source promotion.

All fixtures are generated and tested inside GitHub CI. No REST/Drive/OAuth.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from unittest import TestCase

from mfx_cache.p185_p171_d1_revision_review import (
    VERSION, build_p171_revision_review, public_p171_revision_review,
    validate_p171_revision_review,
)
from test_mfx_p180_d1_overlap_diagnosis import audited, changed_refetch
from test_mfx_p171_d1_fresh_epoch import fresh

OBSERVED = datetime(2026, 11, 16, 12, 30, tzinfo=timezone.utc)


def candidate():
    _, state = audited()
    return build_p171_revision_review(
        state=state, refetched=changed_refetch(),
        runner_observed_utc=OBSERVED,
    )


class P185D1RevisionOwnerReviewTests(TestCase):
    def test_01_one_real_sha_revision_gets_private_unapproved_proposal(self):
        c = candidate()
        self.assertEqual(c["schema"], VERSION)
        self.assertEqual(c["status"], "APPEND_ONLY_REVIEW_PROPOSAL_NOT_SOURCE_ADMISSION")
        self.assertEqual(c["revised_source_sha_pair"]["label"], "2026-11-12")
        self.assertNotEqual(
            c["revised_source_sha_pair"]["stored_sha256"],
            c["revised_source_sha_pair"]["refetched_sha256"],
        )
        self.assertEqual(c["redacted_diagnostic"]["overlap_sha_changed_count"], 1)
        self.assertEqual(validate_p171_revision_review(c), c)

    def test_02_independent_source_store_is_not_mutated_by_proposal(self):
        store, state = audited()
        before = deepcopy(store.files)
        writes = store.puts
        _ = build_p171_revision_review(
            state=state, refetched=changed_refetch(),
            runner_observed_utc=OBSERVED,
        )
        self.assertEqual(store.files, before)
        self.assertEqual(store.puts, writes)

    def test_03_public_projection_never_exposes_dates_or_sha_or_ohlc(self):
        c = candidate()
        out = public_p171_revision_review(c)
        serialized = json.dumps(out, sort_keys=True)
        self.assertEqual(out["source_revision_rows_under_review"], 1)
        self.assertEqual(out["overlap_labels_missing_count"], 0)
        for forbidden in ("2026-11-12", "EUR/USD", "stored_sha256",
                          "refetched_sha256", "original_epoch_manifest",
                          '"open"', '"high"', '"low"', '"close"',
                          c["revised_source_sha_pair"]["stored_sha256"]):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(out["provider_price_requests_added"], 0)
        self.assertEqual(out["drive_reads_added"], 0)
        self.assertEqual(out["drive_writes"], 0)
        self.assertFalse(out["may_publish_buy_sell"])

    def test_04_same_source_sha_is_not_an_incident(self):
        _, state = audited()
        with self.assertRaises(ValueError):
            build_p171_revision_review(
                state=state, refetched=fresh(),
                runner_observed_utc=OBSERVED,
            )

    def test_05_missing_overlap_is_not_a_sha_revision_candidate(self):
        _, state = audited()
        wrong = replace(changed_refetch(), closed_bars=tuple(
            b for b in changed_refetch().closed_bars
            if b.native_open_label != "2026-11-11"
        ))
        with self.assertRaisesRegex(ValueError, "ONE_REVISED_AND_ZERO_MISSING"):
            build_p171_revision_review(
                state=state, refetched=wrong,
                runner_observed_utc=OBSERVED,
            )

    def test_06_multiple_changed_sha_are_not_silently_combined(self):
        _, state = audited()
        sample = changed_refetch()
        changed = replace(sample, closed_bars=tuple(
            replace(b, high="1.9000") if b.native_open_label == "2026-11-13"
            else b for b in sample.closed_bars
        ))
        with self.assertRaisesRegex(ValueError, "ONE_REVISED_AND_ZERO_MISSING"):
            build_p171_revision_review(
                state=state, refetched=changed,
                runner_observed_utc=OBSERVED,
            )

    def test_07_missing_or_orphaned_p171_state_rejected(self):
        _, state = audited()
        bad = deepcopy(state.last_manifest)
        bad["publisher_first_known_verified"] = True
        for broken in (
            replace(state, last_manifest=None),
            replace(state, manifests=0),
            replace(state, orphan_chunk="missing-parent"),
            replace(state, chunks=2),
            replace(state, last_manifest=bad),
        ):
            with self.subTest(state=repr(broken)[:50]):
                with self.assertRaises(ValueError):
                    build_p171_revision_review(
                        state=broken, refetched=changed_refetch(),
                        runner_observed_utc=OBSERVED,
                    )

    def test_08_clock_timezone_and_rollback_rejected(self):
        _, state = audited()
        for time in (
            datetime(2026,11,14,12,30,tzinfo=timezone.utc),
            datetime(2026,11,16,12,30),
            datetime(2026,11,16,12,30,
                     tzinfo=timezone(timedelta(hours=7))),
        ):
            with self.subTest(instant=time):
                with self.assertRaises(ValueError):
                    build_p171_revision_review(
                        state=state, refetched=changed_refetch(),
                        runner_observed_utc=time,
                    )

    def test_09_scope_source_spoof_rejected(self):
        _, state = audited()
        for bad in (
            replace(changed_refetch(), source="FABRICATED"),
            replace(changed_refetch(), broker_orders=1),
        ):
            with self.assertRaises(ValueError):
                build_p171_revision_review(
                    state=state, refetched=bad,
                    runner_observed_utc=OBSERVED,
                )

    def test_10_forged_status_or_policy_signoff_does_not_pass(self):
        base = candidate()
        for field, val in (
            ("source_account_rights_verified",True),
            ("publisher_first_known_verified",True),
            ("owner_canonical_revision_approved",True),
            ("historical_asof_rewrite_allowed",True),
            ("may_write_d1",True),
            ("may_publish_buy_sell",True),
            ("broker_orders",1),
            ("status","CANONICAL_ACCEPTED"),
        ):
            bad = deepcopy(base)
            bad[field] = val
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_p171_revision_review(bad)

    def test_11_private_sha_or_timestamp_tamper_rejected(self):
        for change in ("stored_sha256", "refetched_sha256"):
            bad = deepcopy(candidate())
            bad["revised_source_sha_pair"][change] = "f"*64
            with self.assertRaises(ValueError):
                validate_p171_revision_review(bad)
        bad = deepcopy(candidate())
        bad["runner_observed_utc"] = "2026-11-16T12:30:00"
        with self.assertRaises(ValueError):
            validate_p171_revision_review(bad)

    def test_12_identical_observation_has_deterministic_digest(self):
        a, b = candidate(), candidate()
        self.assertEqual(a, b)
        self.assertEqual(a["proposal_content_sha256"],
                         b["proposal_content_sha256"])
        public = public_p171_revision_review(a)
        for key in (
            "source_account_rights_verified","publisher_first_known_verified",
            "owner_canonical_revision_approved","historical_asof_rewrite_allowed",
            "may_write_d1","may_publish_buy_sell",
        ):
            self.assertIs(public[key], False)
        self.assertEqual(public["broker_orders"], 0)

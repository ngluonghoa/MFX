"""P0.204: review-only P192 D1 numeric SHA variant; redaction and no authority."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json
from unittest import TestCase

from mfx_cache.p204_p192_d1_revision_review import (
    VERSION, build_p192_revision_review,
    public_p192_revision_review, validate_p192_revision_review,
)
from mfx_cache.td_m5_codec import digest
from test_mfx_p171_d1_fresh_epoch import original_sha
from test_mfx_p192_d1_nov18_cutoff import AFTER, NEXT, source
from test_mfx_p192_native_writer_nov18 import P192RealWriterCutoffTests
from test_mfx_p200_p192_d1_redacted_sha_forensics import fixture


def candidate(*, batch=None, clock=NEXT):
    _, state, chunk = fixture()
    return build_p192_revision_review(
        state=state, sealed_chunk=chunk,
        refetched=(batch if batch is not None
                   else source(include19=True, revised="2026-11-18")),
        origin_v1_sha=original_sha(), runner_observed_utc=clock,
    )


class P204P192D1PrivateNumericReviewTests(TestCase):
    def test_01_private_one_sha_pair_is_sha_bound_but_never_approved(self):
        r = candidate()
        self.assertEqual(r["schema"], VERSION)
        self.assertEqual(r["status"],
                         "RESEARCH_ONLY_REVISION_PROPOSAL_NO_SOURCE_ADMISSION")
        self.assertEqual(r["private_revised_source_sha_pair"]["label"],
                         "2026-11-18")
        self.assertNotEqual(
            r["private_revised_source_sha_pair"]["stored_sha256"],
            r["private_revised_source_sha_pair"]["refetched_sha256"],
        )
        self.assertEqual(r["proposal_content_sha256"], digest({
            k: v for k,v in r.items() if k != "proposal_content_sha256"
        }))
        self.assertFalse(r["owner_canonical_revision_approved"])
        self.assertFalse(r["may_write_d1"])
        self.assertFalse(r["may_publish_buy_sell"])
        self.assertFalse(r["may_trade"])
        self.assertEqual((r["provider_price_requests_added"],
                          r["drive_reads_added_by_candidate"],
                          r["drive_writes"], r["broker_orders"]), (0,0,0,0))

    def test_02_public_projection_hides_private_sha_date_price_and_runner_time(self):
        r = candidate()
        pub = public_p192_revision_review(r)
        text = json.dumps(pub, sort_keys=True)
        for secret in (
            "2026-11-18", "2026-11-19",
            r["private_revised_source_sha_pair"]["stored_sha256"],
            r["private_revised_source_sha_pair"]["refetched_sha256"],
            r["original_epoch_manifest_sha256"],
            r["origin_v1_manifest_sha256"],
            r["runner_observed_utc"],
            '"open":', '"close":', '"high":', '"low":',
        ):
            self.assertNotIn(secret, text)
        self.assertEqual(pub["revision_numeric_ohlc_rows_under_review"], 1)
        self.assertFalse(pub["may_write_d1"])
        self.assertFalse(pub["may_publish_buy_sell"])

    def test_03_wrong_metadata_only_or_unchanged_source_refused(self):
        with self.assertRaises(ValueError):
            candidate(batch=source(include19=True))
        original = source(include19=True)
        modified = replace(original, closed_bars=tuple(
            replace(b, exchange_timezone_origin="PROVIDER_CHANGED")
            if b.native_open_label == "2026-11-18" else b
            for b in original.closed_bars
        ))
        # The original native source-provenance guard may reject this
        # forged timezone metadata even before P204's own numeric-only gate.
        # Either way a metadata-only variant must never be admitted.
        with self.assertRaises(ValueError):
            candidate(batch=modified)

    def test_04_missing_original_overlap_refused(self):
        with self.assertRaises(ValueError):
            candidate(batch=source(include18=False, include19=True))

    def test_05_cannot_forge_owner_permission_even_with_rehashed_private_digest(self):
        original = candidate()
        for key, val in (
            ("may_write_d1", True),
            ("owner_canonical_revision_approved", True),
            ("source_account_rights_verified", True),
            ("source_publisher_first_known_verified", True),
            ("historical_asof_rewrite_allowed", True),
            ("may_trade", True),
            ("provider_price_requests_added", 1),
            ("drive_writes", 1),
            ("broker_orders", 1),
        ):
            r = deepcopy(original)
            r[key] = val
            r["proposal_content_sha256"] = digest({
                k:v for k,v in r.items() if k != "proposal_content_sha256"
            })
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_p192_revision_review(r)

    def test_06_private_sha_pair_or_proposal_digest_tamper_denied(self):
        original = candidate()
        r = deepcopy(original)
        r["private_revised_source_sha_pair"]["refetched_sha256"] = "b"*64
        with self.assertRaises(ValueError):
            validate_p192_revision_review(r)
        r = deepcopy(original)
        r["proposal_content_sha256"] = "a"*64
        with self.assertRaises(ValueError):
            public_p192_revision_review(r)
        r = deepcopy(original)
        r["extra_private_price"] = "1.234"
        with self.assertRaises(ValueError):
            validate_p192_revision_review(r)

    def test_07_clock_before_initial_sha_seal_denied(self):
        with self.assertRaisesRegex(ValueError, "CLOCK_BEFORE"):
            candidate(clock=AFTER-timedelta(days=1))
        with self.assertRaises(ValueError):
            candidate(clock=NEXT.replace(tzinfo=None))

    def test_08_tampered_original_chunk_or_origin_denied(self):
        _,state,chunk = fixture()
        chunk["bars"][0]["close"] = "2.0"
        with self.assertRaises(ValueError):
            build_p192_revision_review(
                state=state, sealed_chunk=chunk,
                refetched=source(include19=True, revised="2026-11-18"),
                origin_v1_sha=original_sha(), runner_observed_utc=NEXT)
        _,state,chunk = fixture()
        with self.assertRaises(ValueError):
            build_p192_revision_review(
                state=state, sealed_chunk=chunk,
                refetched=source(include19=True, revised="2026-11-18"),
                origin_v1_sha="a"*64, runner_observed_utc=NEXT)

    def test_09_real_writer_path_emits_only_review_projection_and_stays_red(self):
        err, logs, calls, store = P192RealWriterCutoffTests().run_job(
            clock=NEXT, revision=True)
        self.assertEqual(err, "P192_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE")
        self.assertEqual(store.puts, 2)
        self.assertEqual([tf for kind,tf in calls if kind=="vendor"], ["1day"])
        marker = "MFX_P204_P192_REDACTED_OWNER_REVIEW_ONLY"
        lines = logs.splitlines()
        self.assertEqual(lines.count(marker), 1)
        public = json.loads(lines[lines.index(marker)+1])
        self.assertEqual(public["schema"], VERSION)
        self.assertEqual(public["revision_numeric_ohlc_rows_under_review"], 1)
        self.assertFalse(public["may_write_d1"])
        self.assertFalse(public["owner_canonical_revision_approved"])
        self.assertIn("MFX_P200_P192_D1_SHA_DIFF_REDACTED_NO_COMMIT",logs)
        self.assertNotIn('"private_revised_source_sha_pair"', logs)
        self.assertNotIn("fake-key", logs)

    def test_10_existing_h4_isolation_is_not_a_canonical_d1_approval(self):
        r = candidate()
        pub = public_p192_revision_review(r)
        self.assertFalse(pub["source_account_rights_verified"])
        self.assertFalse(pub["source_publisher_first_known_verified"])
        self.assertFalse(pub["historical_asof_rewrite_allowed"])
        self.assertFalse(pub["may_publish_buy_sell"])
        self.assertFalse(pub["may_trade"])
        self.assertEqual(pub["broker_orders"], 0)

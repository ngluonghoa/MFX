"""P0.170 hermetic second-reader SHA audit of existing P0.169 D1 sidecar.

No real vendor, OAuth, Drive mutation or broker endpoint is invoked.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import json
from unittest import TestCase

from mfx_cache.native_d1_quarantine_readonly import audit_d1_quarantine_readonly
from mfx_cache.native_d1_quarantine_stage import (
    MAX_OBSERVATIONS, PREFIX, stage_d1_quarantine_snapshot,
)
from mfx_cache.td_m5_codec import digest
from test_mfx_p169_d1_quarantine_staging import FakeStore, NOW, source_input


def prepared() -> tuple[FakeStore, str]:
    store = FakeStore()
    src = source_input()
    stage_d1_quarantine_snapshot(store, **src)
    return store, digest(src["previous"])


def verify(store: FakeStore, sha: str, offset: int = 1):
    return audit_d1_quarantine_readonly(
        store, canonical_d1_manifest_sha256=sha,
        now_utc=NOW+timedelta(hours=offset))


class P170D1QuarantineReadonlyTests(TestCase):
    def test_01_actual_sha_record_content_and_parent_pass(self):
        store, sha = prepared()
        original = deepcopy(store.data)
        result = verify(store, sha)
        self.assertEqual(result["observation_objects_verified"], 1)
        self.assertEqual(result["raw_closed_rows_across_observations"], 17)
        self.assertTrue(result["canonical_old_d1_parent_sha_matched"])
        self.assertEqual(result["earliest_runner_observed_utc"], NOW.isoformat())
        self.assertEqual(result["status"],
                         "D1_QUARANTINE_RAW_OBSERVATIONS_SHA_READONLY_PASS")
        self.assertEqual(store.data, original)
        self.assertEqual(store.create_calls, 1)

    def test_02_repeat_second_read_does_not_create_anything(self):
        store, sha = prepared()
        first = verify(store, sha)
        second = verify(store, sha)
        self.assertEqual(first, second)
        self.assertEqual(store.create_calls, 1)

    def test_03_missing_source_object_is_not_reported_as_pass(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_NOT_FOUND"):
            verify(FakeStore(), "a"*64)

    def test_04_wrong_original_canonical_d1_sha_denied(self):
        store, _ = prepared()
        with self.assertRaisesRegex(ValueError, "OLD_CANONICAL_SHA_CHANGED"):
            verify(store, "a"*64)

    def test_05_sha_argument_must_be_lowercase_hex64(self):
        store, _ = prepared()
        for invalid in ("bad", "F"*64, "", None):
            with self.subTest(value=invalid), self.assertRaisesRegex(
                    ValueError, "CANONICAL_D1_SHA_REQUIRED"):
                verify(store, invalid)

    def test_06_swapped_sha_filename_denied(self):
        store, sha = prepared()
        old = next(iter(store.data))
        store.data[PREFIX+"f"*64+".json"] = store.data.pop(old)
        with self.assertRaisesRegex(ValueError, "FILENAME_OR_IDENTITY"):
            verify(store, sha)

    def test_07_modified_price_content_denied_without_rewriting(self):
        store, sha = prepared()
        name = next(iter(store.data))
        store.data[name]["source_batch"]["closed_bars"][-1]["close"] = "0.01"
        with self.assertRaises(ValueError):
            verify(store, sha)
        self.assertEqual(store.create_calls, 1)

    def test_08_flag_promotion_or_licence_forgery_rejected(self):
        for key in ("may_publish_buy_sell", "source_licence_approved",
                    "publisher_first_known_verified",
                    "owner_canonical_revision_approved"):
            store, sha = prepared()
            store.data[next(iter(store.data))][key] = True
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify(store, sha)

    def test_09_record_sha_corruption_rejected(self):
        store, sha = prepared()
        store.data[next(iter(store.data))]["record_sha256"] = "a"*64
        with self.assertRaisesRegex(ValueError, "RECORD_SHA"):
            verify(store, sha)

    def test_10_future_observation_not_trusted(self):
        store, sha = prepared()
        with self.assertRaisesRegex(ValueError, "FUTURE_OBSERVATION_CLOCK"):
            audit_d1_quarantine_readonly(
                store, canonical_d1_manifest_sha256=sha,
                now_utc=NOW-timedelta(seconds=1))

    def test_11_utc_clock_required(self):
        store, sha = prepared()
        with self.assertRaisesRegex(ValueError, "UTC_AUDIT_CLOCK_REQUIRED"):
            audit_d1_quarantine_readonly(
                store, canonical_d1_manifest_sha256=sha,
                now_utc=NOW.replace(tzinfo=None))

    def test_12_unscoped_names_and_duplicate_listing_denied(self):
        store, sha = prepared()
        name = next(iter(store.data))

        class BadStore:
            def __init__(self, names):
                self.names = names

            def list_names(self, bucket):
                self_bucket = bucket
                assert self_bucket == "chunk"
                return self.names

            def read(self, bucket, requested):
                return store.read(bucket, requested)

        for names in ((name, name), ("NATIVE_D1_OTHER.json",),
                      [name], (name, 123)):
            with self.subTest(names=names), self.assertRaisesRegex(
                    ValueError, "LISTING_NOT_UNIQUE_OR_SCOPED"):
                audit_d1_quarantine_readonly(
                    BadStore(names),
                    canonical_d1_manifest_sha256=sha,
                    now_utc=NOW+timedelta(hours=1))

    def test_13_more_than_256_objects_denied_before_any_read(self):
        store, sha = prepared()
        store.data = {PREFIX+f"{i:064x}.json": {}
                      for i in range(MAX_OBSERVATIONS+1)}
        with self.assertRaisesRegex(ValueError, "READER_CAPACITY_EXCEEDED"):
            verify(store, sha)

    def test_14_missing_read_or_list_methods_denied(self):
        _, sha = prepared()
        with self.assertRaisesRegex(ValueError, "READ_ONLY_SOURCE_STORE"):
            audit_d1_quarantine_readonly(
                object(), canonical_d1_manifest_sha256=sha,
                now_utc=NOW+timedelta(hours=1))

    def test_15_two_versions_still_keep_first_canonical_parent(self):
        store, sha = prepared()
        later = source_input(NOW+timedelta(days=1))
        from test_mfx_p168_independent_h4_d1_hold_cache import D1_LABELS, batch
        later["refetched"] = batch(
            "1day", D1_LABELS+("2026-11-12", "2026-11-13"),
            amend="2026-11-11")
        stage_d1_quarantine_snapshot(store, **later)
        receipt = verify(store, sha, offset=26)
        self.assertEqual(receipt["observation_objects_verified"], 2)
        self.assertGreater(receipt["raw_closed_rows_across_observations"], 17)
        self.assertEqual(store.create_calls, 2)

    def test_16_public_receipt_contains_no_ohlc_or_approval(self):
        store, sha = prepared()
        output = json.dumps(verify(store, sha), sort_keys=True)
        for forbidden in ("1.1000", "1.1030", "source_batch",
                          "candidate_receipt", "apikey", "BUY", "SELL"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, output)
        self.assertIn('"may_publish_buy_sell": false', output)
        self.assertIn('"drive_writes": 0', output)

    def test_17_no_filename_alias_for_same_identity(self):
        store, sha = prepared()
        name = next(iter(store.data))
        store.data[PREFIX+"0"*64+".json"] = deepcopy(store.data[name])
        with self.assertRaisesRegex(ValueError, "FILENAME_OR_IDENTITY"):
            verify(store, sha)

    def test_18_canonical_or_h4_store_is_never_reached(self):
        store, sha = prepared()
        # The verifier has only list/read operations; no write-capable
        # method is invoked even when its in-memory store exposes one.
        before = deepcopy(store.data)
        verify(store, sha)
        self.assertEqual(store.create_calls, 1)
        self.assertEqual(store.data, before)

    def test_19_invalid_runner_first_known_claim_is_rejected(self):
        store, sha = prepared()
        name = next(iter(store.data))
        store.data[name]["observation_time_quality"] = "PUBLISHER_SIGNED"
        with self.assertRaises(ValueError):
            verify(store, sha)

    def test_20_missing_duplicate_or_wrong_bucket_fail_closed(self):
        store, sha = prepared()
        name = next(iter(store.data))

        class WrongBucket:
            def list_names(self, bucket):
                if bucket != "chunk":
                    raise AssertionError("reader tried another bucket")
                return (name,)

            def read(self, bucket, filename):
                if bucket != "chunk":
                    raise AssertionError("reader tried another bucket")
                return store.read(bucket, filename)

        self.assertEqual(
            audit_d1_quarantine_readonly(
                WrongBucket(), canonical_d1_manifest_sha256=sha,
                now_utc=NOW+timedelta(hours=1))["drive_writes"], 0)

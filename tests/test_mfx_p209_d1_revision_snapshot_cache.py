"""P209 private D1 cache: isolated custody, no signal or canonical changes."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json
from unittest import TestCase
from unittest.mock import patch

from mfx_cache.p209_d1_revision_snapshot_cache import (
    PREFIX, PrivateP209D1Store, cache_revised_d1_snapshot,
)
from mfx_cache.native_d1_epoch_20261118 import PREFIX as P192_PREFIX
from test_mfx_p171_d1_fresh_epoch import MemoryEpochStore
from test_mfx_p192_d1_nov18_cutoff import NEXT
from test_mfx_p192_native_writer_nov18 import P192RealWriterCutoffTests
from test_mfx_p208_p192_revision_vintage_dryrun import candidate

MODULE = "tools.run_mfx_native_htf_incremental_commit"


def stage(sidecar, *, clock=NEXT, forged=False):
    original, state, batch, review, fork, proposal = candidate(clock=clock)
    if forged:
        proposal = replace(proposal, source_admission=True)
    receipt = cache_revised_d1_snapshot(
        sidecar, proposal=proposal, fork=fork, state=state,
        refetched=batch, validated_review=review, now_utc=clock,
    )
    return original, receipt


class P209PrivateCacheTests(TestCase):
    def test_01_new_snapshot_contains_closed_rows_and_original_root(self):
        sidecar = MemoryEpochStore()
        original, receipt = stage(sidecar)
        self.assertEqual(sidecar.puts, 1)
        self.assertEqual(original.puts, 2)
        name, record = next(iter(sidecar.files["chunk"].items()))
        self.assertTrue(name.startswith(PREFIX))
        self.assertFalse(name.startswith(P192_PREFIX))
        self.assertEqual(len(record["rows"]), 2)
        self.assertEqual(record["rows"][0]["native_open_label"], "2026-11-18")
        self.assertEqual(receipt["new_snapshot_objects"], 1)
        self.assertEqual(receipt["canonical_d1_writes"], 0)
        self.assertFalse(record["source_admission"])
        self.assertFalse(record["publisher_first_known_verified"])
        self.assertTrue(record["owner_cache_collection_authorized"])
        self.assertFalse(record["vendor_retention_rights_verified"])

    def test_02_repeat_exact_content_preserves_first_observation(self):
        sidecar = MemoryEpochStore()
        stage(sidecar)
        before = deepcopy(sidecar.files)
        _, receipt = stage(sidecar, clock=NEXT + timedelta(hours=1))
        self.assertEqual(sidecar.files, before)
        self.assertEqual(sidecar.puts, 1)
        self.assertEqual(receipt["new_snapshot_objects"], 0)

    def test_03_tampered_record_is_never_rewritten(self):
        sidecar = MemoryEpochStore()
        stage(sidecar)
        record = next(iter(sidecar.files["chunk"].values()))
        record["rows"][0]["close"] = "0.01"
        with self.assertRaisesRegex(ValueError, "CONTENT_OR_SHA_DRIFT"):
            stage(sidecar)
        self.assertEqual(sidecar.puts, 1)

    def test_04_forged_source_admission_rejected_before_io(self):
        sidecar = MemoryEpochStore()
        with self.assertRaises(ValueError):
            stage(sidecar, forged=True)
        self.assertEqual(sidecar.puts, 0)

    def test_05_clock_rollback_rejected_without_overwrite(self):
        sidecar = MemoryEpochStore()
        stage(sidecar, clock=NEXT + timedelta(hours=1))
        with self.assertRaisesRegex(ValueError, "OBSERVATION_CLOCK_INVALID"):
            stage(sidecar)
        self.assertEqual(sidecar.puts, 1)

    def test_06_foreign_namespace_listing_rejected(self):
        sidecar = MemoryEpochStore()
        sidecar.files["chunk"][P192_PREFIX + "fake"] = {}
        with self.assertRaisesRegex(ValueError, "LISTING_INVALID"):
            stage(sidecar)
        self.assertEqual(sidecar.puts, 0)

    def test_07_only_private_chunk_bucket_is_allowed(self):
        store = PrivateP209D1Store(None)
        self.assertEqual(store._bucket("chunk")[1], PREFIX)
        with self.assertRaises(ValueError):
            store._bucket("manifest")

    def test_08_native_writer_saves_sidecar_but_keeps_original_red(self):
        sidecar = MemoryEpochStore()
        with patch(MODULE + ".PrivateP209D1Store", return_value=sidecar):
            err, logs, calls, original = P192RealWriterCutoffTests().run_job(
                clock=NEXT, revision=True)
        self.assertEqual(err, "P192_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE")
        self.assertEqual(sidecar.puts, 1)
        self.assertEqual(original.puts, 2)
        self.assertEqual([tf for kind, tf in calls if kind == "vendor"], ["1day"])
        lines = logs.splitlines()
        marker = "MFX_P209_PRIVATE_D1_SNAPSHOT_SHA_READBACK"
        self.assertEqual(lines.count(marker), 1)
        receipt = json.loads(lines[lines.index(marker) + 1])
        self.assertEqual(receipt["new_snapshot_objects"], 1)
        self.assertEqual(receipt["action"], "NO_SIGNAL")
        self.assertEqual(receipt["canonical_d1_writes"], 0)
        for secret in ('"rows"', '"row_sha256"', '"identity_sha256"', PREFIX):
            self.assertNotIn(secret, logs)

    def test_09_sidecar_failure_preserves_existing_quarantine(self):
        with patch(MODULE + ".PrivateP209D1Store",
                   side_effect=RuntimeError("PRIVATE ERROR DETAIL")):
            err, logs, calls, original = P192RealWriterCutoffTests().run_job(
                clock=NEXT, revision=True)
        self.assertEqual(err, "P192_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE")
        self.assertIn("MFX_P209_PRIVATE_SNAPSHOT_FAILED_D1_HELD", logs)
        self.assertNotIn("PRIVATE ERROR DETAIL", logs)
        self.assertEqual(original.puts, 2)
        self.assertEqual([tf for kind, tf in calls if kind == "vendor"], ["1day"])

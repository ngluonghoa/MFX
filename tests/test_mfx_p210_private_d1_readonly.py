"""P210 independent readback of P209 cache; no source promotion."""
from copy import deepcopy
from datetime import timedelta
from unittest import TestCase

from mfx_cache.td_m5_codec import digest
from mfx_cache.p209_d1_revision_snapshot_cache import PREFIX
from test_mfx_p209_d1_revision_snapshot_cache import stage
from test_mfx_p171_d1_fresh_epoch import MemoryEpochStore, original_sha
from test_mfx_p192_d1_nov18_cutoff import NEXT
from mfx_cache.native_d1_epoch_20261118 import audit_fresh_epoch
from tools.audit_mfx_p209_d1_private_cache import read_private_snapshots


class P210PrivateReadTests(TestCase):
    def setUp(self):
        self.cache = MemoryEpochStore()
        original, _ = stage(self.cache)
        self.original = audit_fresh_epoch(original, origin_v1_sha=original_sha())
        self.now = NEXT + timedelta(hours=2)

    def read(self, asof=None):
        return read_private_snapshots(
            self.cache, original=self.original, now_utc=self.now,
            asof_utc=asof or self.now,
        )

    def test_01_full_independent_read_no_writes(self):
        before = deepcopy(self.cache.files)
        receipt, snapshot = self.read()
        self.assertEqual(receipt["snapshot_objects_verified"], 1)
        self.assertEqual(receipt["private_selected_closed_rows"], 2)
        self.assertFalse(receipt["canonical_source_selected"])
        self.assertEqual(receipt["action"], "NO_SIGNAL")
        self.assertEqual(len(snapshot.rows), 2)
        self.assertEqual(self.cache.files, before)
        self.assertEqual(self.cache.puts, 1)

    def test_02_asof_before_observation_cannot_select(self):
        receipt, snapshot = self.read(NEXT - timedelta(seconds=1))
        self.assertIsNone(snapshot)
        self.assertEqual(receipt["snapshot_objects_verified"], 1)
        self.assertEqual(receipt["private_selected_closed_rows"], 0)

    def test_03_empty_store_is_not_success(self):
        self.cache = MemoryEpochStore()
        receipt, snapshot = self.read()
        self.assertIsNone(snapshot)
        self.assertEqual(receipt["status"], "P210_NO_SNAPSHOT_VISIBLE_AT_ASOF")

    def test_04_tampered_raw_row_rejected(self):
        value = next(iter(self.cache.files["chunk"].values()))
        value["rows"][0]["close"] = "0.01"
        with self.assertRaises(ValueError):
            self.read()

    def test_05_forged_permission_rejected_even_with_new_sha(self):
        name, value = self.cache.files["chunk"].popitem()
        value["source_admission"] = True
        core = {k: v for k, v in value.items()
                if k not in ("identity_sha256", "record_sha256",
                             "first_runner_observed_utc")}
        identity = digest(core)
        value["identity_sha256"] = identity
        value["record_sha256"] = digest({
            k: v for k, v in value.items() if k != "record_sha256"
        })
        self.cache.files["chunk"][PREFIX + identity + ".json"] = value
        self.assertNotEqual(name, PREFIX + identity + ".json")
        with self.assertRaisesRegex(ValueError, "AUTHORITY_DRIFT"):
            self.read()

    def test_06_future_asof_denied(self):
        with self.assertRaisesRegex(ValueError, "ASOF_AFTER_AUDIT"):
            self.read(self.now + timedelta(seconds=1))

    def test_07_wrong_filename_denied(self):
        _, value = self.cache.files["chunk"].popitem()
        self.cache.files["chunk"][PREFIX + "0" * 64 + ".json"] = value
        with self.assertRaisesRegex(ValueError, "FILENAME_SHA_DRIFT"):
            self.read()

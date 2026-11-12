"""A04/P0.85 hermetic two-anchor full bounded M5 SHA/rollback tests.

No live Drive, requests, API credits, broker, or production workflows.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import unittest

from mfx_cache.td_m5_codec import digest
from test_a04_p66_readonly_m5_h4_live_parity import (
    START, NOW, ReadOnlyStore, seed_m5,
)
from tools.mfx_m5_full_sha_two_anchor_audit import (
    SCHEMA, ROOT_UTC, ROOT_MANIFEST_SHA256,
    REVIEWED_CHECKPOINT_UTC, REVIEWED_CHECKPOINT_SHA256,
    REVIEWED_CHECKPOINT_PAIRS, audit_root_checkpoint_full_m5,
)

UTC = timezone.utc


def fixture(hours: int = 33) -> tuple[ReadOnlyStore, dict]:
    store = ReadOnlyStore()
    seed_m5(store, range(hours))
    keys = sorted(store.records["manifest"])
    checkpoint = store.records["manifest"][keys[30]]
    opts = {
        "now_utc": NOW,
        "root_hour_utc": START.isoformat(),
        "root_sha256": digest(store.records["manifest"][keys[0]]),
        "checkpoint_hour_utc": checkpoint["hour_utc"],
        "checkpoint_sha256": digest(checkpoint),
        "checkpoint_pairs": 31,
    }
    return store, opts


class M5TwoAnchorAuditTests(unittest.TestCase):
    def audit(self, store=None, opts=None):
        if store is None:
            store, opts = fixture()
        return audit_root_checkpoint_full_m5(store, **opts)

    def test_01_33_raw_chunks_checked_and_no_external_authority(self):
        out=self.audit()
        self.assertEqual(out["status"],
                         "FULL_BOUNDED_RAW_SHA_AND_TWO_GIT_PINS_VERIFIED")
        self.assertEqual(out["total_manifest_chunk_pairs_full_sha_verified"],33)
        self.assertEqual(out["total_closed_m5_full_sha_verified"],396)
        self.assertTrue(out["m5_full_bounded_chain_verified"])
        self.assertFalse(out["source_history_before_root_proven"])
        self.assertFalse(out["externally_authenticated_monotonic_witness"])
        self.assertFalse(out["vendor_license_and_session_calendar_verified"])
        self.assertFalse(out["source_h4_replacement_authorized"])
        self.assertFalse(out["live_v2_authorized"])
        self.assertFalse(out["numeric_trade_signals_authorized"])

    def test_02_source_approved_root_and_checkpoint_are_frozen_literals(self):
        self.assertEqual(ROOT_UTC,"2026-11-10T18:00:00+00:00")
        self.assertEqual(ROOT_MANIFEST_SHA256,
            "47320a77ba8a615cd043dbba55b6bc2d4e02ad0f88adf4b229143aca5dde93c0")
        self.assertEqual(REVIEWED_CHECKPOINT_UTC,"2026-11-12T00:00:00+00:00")
        self.assertEqual(REVIEWED_CHECKPOINT_SHA256,
            "9e27346ebcef2d292f0ce519acffd46d7c01e45b1e31906e31bbda12f38fc629")
        self.assertEqual(REVIEWED_CHECKPOINT_PAIRS,31)

    def test_03_31_pair_checkpoint_itself_is_acceptable_but_not_newer(self):
        s,o=fixture(31)
        r=self.audit(s,o)
        self.assertEqual(r["total_manifest_chunk_pairs_full_sha_verified"],31)
        self.assertFalse(r["externally_authenticated_monotonic_witness"])

    def test_04_defaults_do_not_accept_an_arbitrary_synthetic_archive(self):
        s,_=fixture()
        with self.assertRaisesRegex(ValueError,"REVIEWED_ROOT_OR_CHECKPOINT"):
            audit_root_checkpoint_full_m5(s,now_utc=NOW)

    def test_05_wrong_root_sha_denied(self):
        s,o=fixture()
        with self.assertRaisesRegex(ValueError,"REVIEWED_ROOT_OR_CHECKPOINT"):
            self.audit(s,{**o,"root_sha256":"f"*64})

    def test_06_wrong_reviewed_checkpoint_sha_denied(self):
        s,o=fixture()
        with self.assertRaisesRegex(ValueError,"REVIEWED_ROOT_OR_CHECKPOINT"):
            self.audit(s,{**o,"checkpoint_sha256":"f"*64})

    def test_07_removing_checkpoint_manifest_denied(self):
        s,o=fixture()
        name=sorted(s.records["manifest"])[30]
        del s.records["manifest"][name]
        with self.assertRaises(ValueError):
            self.audit(s,o)

    def test_08_rollback_to_30_pairs_denied(self):
        s,o=fixture()
        for name in sorted(s.records["manifest"])[30:]:
            del s.records["manifest"][name]
        for name in sorted(s.records["chunk"])[30:]:
            del s.records["chunk"][name]
        with self.assertRaisesRegex(ValueError,"ROLLBACK"):
            self.audit(s,o)

    def test_09_one_old_chunk_corrupted_fail_closed(self):
        s,o=fixture()
        s.records["chunk"][sorted(s.records["chunk"])[0]]["bars"][0]["open"]="9.9"
        with self.assertRaises(ValueError):
            self.audit(s,o)

    def test_10_one_new_chunk_corrupted_fail_closed(self):
        s,o=fixture()
        s.records["chunk"][sorted(s.records["chunk"])[-1]]["bars"][0]["close"]="9.9"
        with self.assertRaises(ValueError):
            self.audit(s,o)

    def test_11_old_manifest_rewritten_denied_despite_valid_shape(self):
        s,o=fixture()
        name=sorted(s.records["manifest"])[0]
        s.records["manifest"][name]["total_batches"]=77
        with self.assertRaises(ValueError):
            self.audit(s,o)

    def test_12_checkpoint_manifest_rewritten_denied(self):
        s,o=fixture()
        name=sorted(s.records["manifest"])[30]
        s.records["manifest"][name]["gap_prior_hours_unverified"]=1
        with self.assertRaises(ValueError):
            self.audit(s,o)

    def test_13_extra_orphan_chunk_denied(self):
        s,o=fixture()
        s.records["chunk"]["MFX_TD_EURUSD_M5_V2_chunk_orphan.json"]={}
        with self.assertRaisesRegex(ValueError,"ROLLBACK"):
            self.audit(s,o)

    def test_14_missing_historical_chunk_denied(self):
        s,o=fixture()
        del s.records["chunk"][sorted(s.records["chunk"])[3]]
        with self.assertRaisesRegex(ValueError,"ROLLBACK"):
            self.audit(s,o)

    def test_15_snapshot_list_mutates_during_audit_denied(self):
        class ChangingStore(ReadOnlyStore):
            def __init__(self):
                super().__init__()
                self.manifest_calls=0
            def list_names(self,bucket):
                result=super().list_names(bucket)
                if bucket=="manifest":
                    self.manifest_calls+=1
                    if self.manifest_calls>=3:
                        return result[:-1]
                return result
        s=ChangingStore()
        seed_m5(s,range(33))
        base,opts=fixture()
        # Recompute anchors from identical synthetic writer state.
        self.assertEqual(s.records,base.records)
        with self.assertRaisesRegex(ValueError,"SNAPSHOT_CHANGED"):
            self.audit(s,opts)

    def test_16_future_timestamp_rejected(self):
        s,o=fixture()
        with self.assertRaisesRegex(ValueError,"UTC_REQUIRED"):
            self.audit(s,{**o,"now_utc":datetime(2026,11,1)})

    def test_17_boolean_pair_count_rejected(self):
        s,o=fixture()
        with self.assertRaisesRegex(ValueError,"UTC_REQUIRED"):
            self.audit(s,{**o,"checkpoint_pairs":True})

    def test_18_malformed_pin_sha_rejected(self):
        s,o=fixture()
        with self.assertRaisesRegex(ValueError,"UTC_REQUIRED"):
            self.audit(s,{**o,"root_sha256":"invalid"})

    def test_19_non_hour_utc_pin_rejected(self):
        s,o=fixture()
        with self.assertRaisesRegex(ValueError,"GRID"):
            self.audit(s,{**o,"root_hour_utc":(
                START+timedelta(minutes=5)).isoformat()})

    def test_20_hard_257_pair_cap_denied_without_external_io(self):
        s,o=fixture()
        for i in range(33,257):
            s.records["manifest"][f"MFX_TD_EURUSD_M5_V2_manifest_fake_{i}"]={}
            s.records["chunk"][f"MFX_TD_EURUSD_M5_V2_chunk_fake_{i}"]={}
        with self.assertRaisesRegex(ValueError,"BOUND"):
            self.audit(s,o)

    def test_21_no_mutating_api_needed_and_no_raw_prices_in_receipt(self):
        s,o=fixture()
        self.assertFalse(hasattr(s,"put_if_absent"))
        old=copy.deepcopy(s.records)
        r=self.audit(s,o)
        self.assertEqual(s.records,old)
        self.assertEqual((r["provider_calls"],r["drive_writes"],r["broker_orders"]),
                         (0,0,0))
        self.assertNotIn("1.10000",str(r))
        self.assertEqual(r["schema"],SCHEMA)


if __name__=="__main__":
    unittest.main()

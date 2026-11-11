"""P0.69 hermetic M5 rooted manifest+rolling 256-Chunk SHA tests.

No credentials, HTTP, Drive mutations, broker, Forex numeric signals.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import unittest

from mfx_cache.td_m5_codec import digest
from tools.mfx_m5_rolling_manifest_audit import (
    MAX_ROOTED_MANIFESTS, ROLLING_HOURS, ROOT_UTC,
    ROOT_MANIFEST_SHA256, audit_rooted_rolling_m5,
)
from tools.run_mfx_m5_h4_live_parity_audit import audit_live_m5_h4_parity
from test_a04_p66_readonly_m5_h4_live_parity import (
    START, NOW, ReadOnlyStore, fixtures, seed_m5, seed_native,
)

UTC = timezone.utc


def seeded_257() -> tuple[ReadOnlyStore, str]:
    m=ReadOnlyStore()
    seed_m5(m,range(257))
    first=sorted(m.records["manifest"])[0]
    root=digest(m.records["manifest"][first])
    return m,root


class RootedRollingM5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.m5,cls.root=seeded_257()

    def audit(self, store:ReadOnlyStore|None=None, *,
              root:str|None=None):
        return audit_rooted_rolling_m5(
            store or self.m5,now_utc=NOW,
            root_sha256=root or self.root,
            root_hour_utc=START.isoformat())

    def test_01_257_manifest_full_parent_sha_256_raw_latest(self) -> None:
        rows,e=self.audit()
        self.assertEqual(len(rows),3072)
        self.assertEqual(e["m5_manifest_full_sha_parent_chain_verified"],257)
        self.assertEqual(e["m5_manifest_chunk_pairs_full_sha_verified"],256)
        self.assertEqual(e["m5_total_archived_closed_bars"],3084)
        self.assertEqual(e["m5_historical_unread_chunks"],1)
        self.assertFalse(e["m5_full_bounded_chain_verified"])
        self.assertTrue(e["m5_rolling_256_chunk_sha_verified"])
        self.assertTrue(e["m5_old_raw_chunks_not_reverified_this_run"])
        self.assertTrue(e["m5_full_history_raw_sha_not_approved_for_cutover"])
        self.assertEqual(rows[0].start_utc,
                         (START+timedelta(hours=1)).isoformat())

    def test_02_wrong_separately_pinned_root_denied(self) -> None:
        with self.assertRaisesRegex(ValueError,"TRUSTED_ROOT_SHA"):
            self.audit(root="0"*64)

    def test_03_historical_manifest_mutation_outside_tail_denied(self) -> None:
        m=copy.deepcopy(self.m5)
        name=sorted(m.records["manifest"])[0]
        m.records["manifest"][name]["total_batches"]=2
        with self.assertRaises(ValueError):
            self.audit(m)

    def test_04_historical_raw_not_claimed_freshly_audited(self) -> None:
        m=copy.deepcopy(self.m5)
        name=sorted(m.records["chunk"])[0]
        m.records["chunk"][name]["bars"][0]["open"]="9.12345"
        # Historical Chunk existence/manifest SHA links are checked, but
        # its bytes are deliberately NOT reread. The evidence flag must
        # never silently assert fresh verification of old content.
        _,e=self.audit(m)
        self.assertEqual(e["m5_historical_unread_chunks"],1)
        self.assertFalse(e["m5_full_bounded_chain_verified"])

    def test_05_corrupt_recent_M5_chunk_fails_closed(self) -> None:
        m=copy.deepcopy(self.m5)
        name=sorted(m.records["chunk"])[-1]
        m.records["chunk"][name]["bars"][0]["open"]="9.12345"
        with self.assertRaises(ValueError):
            self.audit(m)

    def test_06_extra_chunk_orphan_detected_in_all_history(self) -> None:
        m=copy.deepcopy(self.m5)
        m.records["chunk"]["MFX_TD_EURUSD_M5_V2_chunk_extra.json"]={}
        with self.assertRaisesRegex(ValueError,"ORPHAN_OR_MISSING_CHUNK"):
            self.audit(m)

    def test_07_missing_old_source_chunk_detected_in_enumeration(self) -> None:
        m=copy.deepcopy(self.m5)
        del m.records["chunk"][sorted(m.records["chunk"])[0]]
        with self.assertRaisesRegex(ValueError,"ORPHAN_OR_MISSING_CHUNK"):
            self.audit(m)

    def test_08_1025_manifest_bound_fails_before_content_reads(self) -> None:
        m=ReadOnlyStore()
        for i in range(MAX_ROOTED_MANIFESTS+1):
            m.records["manifest"][f"manifest_{i:05d}"]={}
            m.records["chunk"][f"chunk_{i:05d}"]={}
        with self.assertRaisesRegex(ValueError,"HISTORY_CAPACITY"):
            self.audit(m)

    def test_09_256_is_existing_full_sha_path_not_rolling(self) -> None:
        m=ReadOnlyStore()
        seed_m5(m,range(256))
        with self.assertRaisesRegex(ValueError,"USE_EXISTING_FULL"):
            self.audit(m)
        n=ReadOnlyStore()
        seed_native(n,64)
        r=audit_live_m5_h4_parity(m,n,now_utc=NOW)
        self.assertTrue(r["m5_full_bounded_chain_verified"])
        self.assertEqual(r["m5_h4_complete_windows"],64)
        self.assertEqual(r["m5_historical_unread_chunks"] if
                         "m5_historical_unread_chunks" in r else 0,0)

    def test_10_rolling_parity_wrapper_tracks_7day_but_denies_cutover(self) -> None:
        m=copy.deepcopy(self.m5)
        n=ReadOnlyStore()
        seed_native(n,65)
        def rolling_with_test_anchor(store, *, now_utc):
            return audit_rooted_rolling_m5(
                store,now_utc=now_utc,root_sha256=self.root,
                root_hour_utc=START.isoformat())
        with patch("tools.run_mfx_m5_h4_live_parity_audit.audit_rooted_rolling_m5",
                   side_effect=rolling_with_test_anchor):
            r=audit_live_m5_h4_parity(m,n,now_utc=NOW)
        self.assertEqual(r["m5_h4_complete_windows"],63)
        self.assertEqual(r["h4_compared_mismatch"],0)
        self.assertTrue(r["h4_parity_observation_threshold_met"])
        self.assertFalse(r["m5_full_bounded_chain_verified"])
        self.assertEqual(r["m5_historical_unread_chunks"],1)
        self.assertFalse(r["may_replace_native_h4"])
        self.assertFalse(r["may_reduce_native_h4_requests"])
        self.assertEqual((r["provider_api_calls"],r["drive_writes"],
                          r["broker_orders"]),(0,0,0))

    def test_11_source_native_mismatch_still_blocks_rolling(self) -> None:
        m=copy.deepcopy(self.m5)
        n=ReadOnlyStore()
        seed_native(n,65,high="1.10101")
        with patch(
            "tools.run_mfx_m5_h4_live_parity_audit.audit_rooted_rolling_m5",
            side_effect=lambda store,*,now_utc: audit_rooted_rolling_m5(
                store,now_utc=now_utc,root_sha256=self.root,
                root_hour_utc=START.isoformat())):
            r=audit_live_m5_h4_parity(m,n,now_utc=NOW)
        self.assertEqual(r["h4_compared_match"],0)
        self.assertGreater(r["h4_compared_mismatch"],0)
        self.assertFalse(r["h4_parity_observation_threshold_met"])
        self.assertEqual(r["status"],"SOURCE_PARITY_REVIEW_REQUIRED")

    def test_12_naive_utc_and_bad_anchor_input_denied(self) -> None:
        with self.assertRaisesRegex(ValueError,"UTC_NOW"):
            audit_rooted_rolling_m5(self.m5,now_utc=datetime(2026,11,11,18))
        with self.assertRaisesRegex(ValueError,"ROOT_ATTESTATION"):
            audit_rooted_rolling_m5(self.m5,now_utc=NOW,
                                    root_sha256="unapproved")

    def test_13_existing_live_root_pin_equals_observed_drive_name(self) -> None:
        self.assertEqual(ROOT_UTC,"2026-11-10T18:00:00+00:00")
        self.assertEqual(ROOT_MANIFEST_SHA256,
            "47320a77ba8a615cd043dbba55b6bc2d4e02ad0f88adf4b229143aca5dde93c0")

    def test_14_root_manifest_fork_rejected_even_if_later_valid(self) -> None:
        m=copy.deepcopy(self.m5)
        old=sorted(m.records["manifest"])[0]
        m.records["manifest"][old+"._fork"]=copy.deepcopy(m.records["manifest"][old])
        m.records["chunk"][sorted(m.records["chunk"])[0]+"._fork"]={}
        with self.assertRaises(ValueError):
            self.audit(m)

    def test_15_no_private_runtime_extra_permissions_in_workflow(self) -> None:
        from pathlib import Path
        yml=Path(".github/workflows/mfx-m5-h4-parity-readonly.yml").read_text()
        self.assertIn("group: mfx-twelvedata-private-cache",yml)
        self.assertIn("permissions:\n  contents: read",yml)
        self.assertNotIn("MFX_TWELVE_DATA_API_KEY",yml)


if __name__=="__main__":
    unittest.main()

"""P0.193 SHA-root-pinned P192 GET-only history, one-candle no-source-splice QA."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch

from mfx_cache.native_d1_epoch_20261118 import commit_fresh_epoch
from mfx_cache.td_m5_codec import digest
from mfx_research.p193_owner_nov18_active_d1_reader import (
    SOURCE_VERSION, PINNED_P192_20261118_ROOT_SHA256,
    read_p192_owner_d1_epoch,
)
from test_mfx_p171_d1_fresh_epoch import MemoryEpochStore, original_sha
from test_mfx_p192_d1_nov18_cutoff import source

OBSERVED=datetime(2026,11,18,13,43,tzinfo=timezone.utc)
ASOF=datetime(2026,11,18,14,0,tzinfo=timezone.utc)


def seeded(*, observed=OBSERVED, old_sha=None):
    s=MemoryEpochStore()
    commit_fresh_epoch(
        s,batch=source(),origin_v1_sha=old_sha or original_sha(),
        now_utc=observed)
    return s


def root_sha(s):
    return digest(s.read("manifest",s.list_names("manifest")[0]))


def read_fixture(s,*,asof=ASOF,old_sha=None):
    with patch.multiple(
        "mfx_research.p193_owner_nov18_active_d1_reader",
        PINNED_ORIGINAL_D1_V1_HEAD_SHA256=old_sha or original_sha(),
        PINNED_P192_20261118_ROOT_SHA256=root_sha(s),
    ):
        return read_p192_owner_d1_epoch(
            s,old_v1_manifest_sha256=old_sha or original_sha(),
            asof_utc=asof)


class P193OwnerNov18ReadOnlyTests(TestCase):
    def test_01_prod_real_root_anchor_matches_independent_live_audit(self):
        self.assertEqual(
            PINNED_P192_20261118_ROOT_SHA256,
            "64c00f878e2ebe1425d9895069e1405d39402e8dc73bb7eacd2ff226e51f09ad")

    def test_02_single_real_source_day_no_old_d1_splice(self):
        s=seeded()
        before=deepcopy(s.files)
        r=read_fixture(s)
        self.assertEqual(r.active_source_epoch,SOURCE_VERSION)
        self.assertEqual(r.verified_new_d1_candles,1)
        self.assertEqual(
            tuple(x.native_open_label for x in r.batch.closed_bars),
            ("2026-11-18",))
        self.assertEqual(r.original_pre_cutoff_d1_rows_in_source,0)
        self.assertEqual(r.epoch_manifest_pairs_full_sha,1)
        self.assertFalse(r.publisher_first_known_verified)
        self.assertFalse(r.provider_account_rights_verified)
        self.assertFalse(r.may_publish_buy_sell)
        self.assertEqual((r.provider_price_requests,r.drive_writes,
                          r.broker_orders),(0,0,0))
        self.assertEqual(s.files,before)
        self.assertNotIn("1.10",repr(r))

    def test_03_missing_root_fails_closed_no_legacy_fallback(self):
        with patch(
            "mfx_research.p193_owner_nov18_active_d1_reader."
            "PINNED_ORIGINAL_D1_V1_HEAD_SHA256",original_sha()):
            with self.assertRaisesRegex(ValueError,"ROOT_UNSEALED"):
                read_p192_owner_d1_epoch(
                    MemoryEpochStore(),old_v1_manifest_sha256=original_sha(),
                    asof_utc=ASOF)

    def test_04_wrong_independent_p192_root_denied(self):
        with patch(
            "mfx_research.p193_owner_nov18_active_d1_reader."
            "PINNED_ORIGINAL_D1_V1_HEAD_SHA256",original_sha()):
            with self.assertRaisesRegex(ValueError,"ROOT_SHA_MISMATCH"):
                read_p192_owner_d1_epoch(
                    seeded(),old_v1_manifest_sha256=original_sha(),
                    asof_utc=ASOF)

    def test_05_wrong_original_v1_parent_denied(self):
        with self.assertRaisesRegex(ValueError,"PINNED_ORIGINAL"):
            read_p192_owner_d1_epoch(
                seeded(),old_v1_manifest_sha256="a"*64,
                asof_utc=ASOF)

    def test_06_history_not_yet_observed_at_asof_denied(self):
        with self.assertRaisesRegex(ValueError,"NOT_CAUSALLY_OBSERVED"):
            read_fixture(seeded(),asof=OBSERVED-timedelta(seconds=1))

    def test_07_bad_sha_mutation_denied(self):
        s=seeded()
        name=next(iter(s.files["chunk"]))
        s.files["chunk"][name]["bars"][0]["high"]="9.9999"
        with self.assertRaises(ValueError):
            read_fixture(s)

    def test_08_old_p171_epoch_schema_not_p192(self):
        from test_mfx_p171_d1_fresh_epoch import prepared
        old,_=prepared()
        with self.assertRaises(ValueError):
            read_fixture(old)

    def test_09_no_future_or_naive_asof(self):
        s=seeded()
        with self.assertRaisesRegex(ValueError,"EXACT_UTC"):
            read_fixture(s,asof=datetime(2026,11,18,14))
        with self.assertRaisesRegex(ValueError,"EXACT_UTC"):
            read_fixture(s,asof=ASOF.replace(tzinfo=timezone(timedelta(hours=7))))

    def test_10_revised_p192_closed_source_cannot_enter_sha_audit(self):
        s=seeded()
        old=deepcopy(s.files)
        # Revision would be caught before append by P192 writer.
        changed=source(revised="2026-11-18")
        with self.assertRaises(ValueError):
            commit_fresh_epoch(
                s,batch=changed,origin_v1_sha=original_sha(),now_utc=ASOF)
        self.assertEqual(s.files,old)

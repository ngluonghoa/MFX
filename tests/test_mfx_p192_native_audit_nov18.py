"""P0.192 independent read-only auditor selects owner Nov18, archives P171."""
from __future__ import annotations

from contextlib import ExitStack, redirect_stdout
from datetime import timezone
from io import StringIO
import json
import os
from unittest import TestCase
from unittest.mock import patch

from mfx_cache.native_d1_fresh_epoch import FreshEpochState as P171State
from mfx_cache.native_d1_epoch_20261118 import commit_fresh_epoch
from mfx_cache.td_m5_codec import digest
from test_mfx_p171_d1_fresh_epoch import original_sha
from test_mfx_p192_d1_nov18_cutoff import AFTER, new_store, source
from tools.run_mfx_native_htf_cache_audit import main

MODULE="tools.run_mfx_native_htf_cache_audit"


class P192ReadOnlyIndependentAuditTests(TestCase):
    def run_audit(self,*,with_nov18,wrong_real_root=False):
        store,_=new_store()
        if with_nov18:
            commit_fresh_epoch(
                store,batch=source(),origin_v1_sha=original_sha(),
                now_utc=AFTER)
        source_root = (
            digest(store.read("manifest",store.list_names("manifest")[0]))
            if with_nov18 else "0"*64
        )
        def audit_tf(_store,*,interval,now_utc):
            return {
                "lag":0 if interval=="4h" else 7,
                "last_manifest_sha256":(
                    "a"*64 if interval=="4h" else original_sha()),
                "total_closed_native_bars":120 if interval=="1day" else 100,
            }
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ,{
                "MFX_REAL_CACHE_ENABLED":"true",
                "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
                "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED":"true",
                "MFX_D1_OWNER_REBASE_20261111":"true",
                "MFX_D1_OWNER_CUTOFF_20261118":"true",
            }))
            stack.enter_context(patch(MODULE+"._drive_auth_info",return_value={}))
            stack.enter_context(patch(MODULE+"._require_oauth_cache_folders"))
            stack.enter_context(patch(MODULE+"._session",return_value="test-session"))
            stack.enter_context(patch(MODULE+".PrivateNativeDriveStore",
                                      return_value="native-read-only"))
            stack.enter_context(patch(MODULE+".audit_native_cache",
                                      side_effect=audit_tf))
            stack.enter_context(patch(MODULE+".audit_d1_quarantine_readonly",
                                      return_value={"status":"SHA_OK"}))
            stack.enter_context(patch(MODULE+".PrivateD1FreshEpochStore",
                                      return_value="archived-P171"))
            stack.enter_context(patch(MODULE+".audit_fresh_epoch",
                                      return_value=P171State(None,0,0,None)))
            stack.enter_context(patch(MODULE+".PrivateD1Nov18Store",
                                      return_value=store))
            stack.enter_context(patch.multiple(
                "mfx_research.p193_owner_nov18_active_d1_reader",
                PINNED_ORIGINAL_D1_V1_HEAD_SHA256=original_sha(),
                PINNED_P192_20261118_ROOT_SHA256=(
                    "f"*64 if wrong_real_root else source_root),
            ))
            clock=stack.enter_context(patch(MODULE+".datetime"))
            clock.now.return_value=AFTER
            out=StringIO()
            with redirect_stdout(out):
                main()
        return out.getvalue(),store

    def test_01_before_new_epoch_audit_waits_no_old_d1_promoted(self):
        log,store=self.run_audit(with_nov18=False)
        r=json.loads(log.splitlines()[-1])
        nov18=r["d1_fresh_epoch_readonly"]
        self.assertEqual(nov18["status"],"P192_WAITING_FOR_FIRST_CLOSED_20261118_D1")
        self.assertEqual(nov18["owner_cutoff_local_date"],"2026-11-18")
        self.assertFalse(nov18["new_source_epoch_selected"])
        self.assertFalse(nov18["older_p171_archive_selected_for_new_d1"])
        self.assertIsNotNone(r["p171_prior_d1_epoch_archived_readonly"])
        self.assertEqual(store.puts,0)
        self.assertEqual(r["p193_real_active_d1_source_reader"]["status"],
                         "P194_WAITING_FOR_FIRST_P192_CLOSED_D1")
        self.assertEqual(r["provider_price_requests"],0)
        self.assertEqual(r["drive_writes"],0)

    def test_02_independent_full_sha_audit_promotes_only_nov18_source_cache(self):
        log,store=self.run_audit(with_nov18=True)
        self.assertIn("MFX_P192_D1_OWNER_20261118_READONLY_FULL_SHA_PASS",log)
        r=json.loads(log.splitlines()[-1])
        nov18=r["d1_fresh_epoch_readonly"]
        self.assertEqual(nov18["status"],"P192_D1_20261118_FULL_SHA_READONLY_ACCEPTED")
        self.assertTrue(nov18["new_source_epoch_selected"])
        self.assertEqual(nov18["total_closed_bars"],1)
        self.assertEqual(nov18["last_native_open_label"],"2026-11-18")
        self.assertFalse(nov18["publisher_first_known_verified"])
        self.assertFalse(nov18["may_publish_buy_sell"])
        self.assertFalse(nov18["older_p171_archive_selected_for_new_d1"])
        self.assertIn("MFX_P194_LIVE_P193_D1_READER_ROOT_ASOF_SHA_PASS",log)
        independent=r["p193_real_active_d1_source_reader"]
        self.assertEqual(independent["status"],
                         "P194_REAL_P193_GET_ONLY_SOURCE_ROOT_ASOF_ACCEPTED")
        self.assertEqual(independent["source_manifest_sha256"],
                         nov18["last_manifest_sha256"])
        self.assertEqual(independent["source_closed_d1_bars"],1)
        self.assertEqual(independent["first_permitted_source_day"],
                         "2026-11-18")
        self.assertFalse(independent["pre_cutoff_prices_in_active_source"])
        self.assertFalse(independent["entire_six_tf_manual_workflow_executed_here"])
        self.assertFalse(independent["may_publish_buy_sell"])
        self.assertEqual(r["approved_numeric_buy_sell_signals"],False)
        self.assertEqual(r["broker_orders"],0)
        self.assertEqual(r["drive_writes"],0)
        self.assertEqual(store.puts,2)  # seeded only by the test fixture

    def test_03_wrong_live_p193_root_causes_red_and_no_extra_drive_writes(self):
        with self.assertRaisesRegex(
                ValueError,"P193_REAL_GITHUB_AUDITED_P192_ROOT_SHA_MISMATCH"):
            self.run_audit(with_nov18=True,wrong_real_root=True)

    def test_04_reader_is_honest_about_manual_six_tf_not_executed(self):
        output,store=self.run_audit(with_nov18=True)
        r=json.loads(output.splitlines()[-1])
        self.assertTrue(r["p193_real_active_d1_source_reader"]["read_only"])
        self.assertFalse(
            r["p193_real_active_d1_source_reader"]
             ["entire_six_tf_manual_workflow_executed_here"])
        self.assertEqual(r["provider_price_requests"],0)
        self.assertEqual(r["drive_writes"],0)
        self.assertEqual(r["broker_orders"],0)
        self.assertEqual(store.puts,2)

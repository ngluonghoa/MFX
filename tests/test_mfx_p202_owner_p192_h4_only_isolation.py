"""P0.202 hermetic integration: H4-only native SHA write while P192 D1 RED.

No real Drive/quote HTTP, D1 mutation, provider rights or market release.
"""
from __future__ import annotations

from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from io import StringIO
import json
import os
from unittest import TestCase
from unittest.mock import patch

from mfx_cache.native_d1_epoch_20261118 import (
    audit_fresh_epoch as audit_p192, commit_fresh_epoch,
)
from mfx_cache.p200_p192_d1_sha_diff_forensics import diagnose_p192_owner_overlap
from mfx_cache.p202_p192_h4_only_isolation import (
    VERSION, eligible_p192_h4_only,
)
from tools.mfx_native_htf_drive_seal import NativeCommitReceipt
from tools.run_mfx_native_htf_incremental_commit import main
from test_mfx_p171_d1_fresh_epoch import MemoryEpochStore, original_sha
from test_mfx_p192_d1_nov18_cutoff import AFTER, source
from test_mfx_p168_independent_h4_d1_hold_cache import (
    D1_LABELS, FakeStore, FakeReadThrough, envelope, state,
)

MODULE = "tools.run_mfx_native_htf_incremental_commit"
NOW = datetime(2026, 11, 19, 14, 0, tzinfo=timezone.utc)
OLD_H4 = "2026-11-19 04:00:00"
NEW_H4 = "2026-11-19 08:00:00"


def sealed_p192():
    store = MemoryEpochStore()
    commit_fresh_epoch(
        store, batch=source(), origin_v1_sha=original_sha(),
        now_utc=AFTER,
    )
    return store


def real_numeric_report():
    store = sealed_p192()
    st = audit_p192(store, origin_v1_sha=original_sha())
    return diagnose_p192_owner_overlap(
        state=st, sealed_chunk=store.read(
            "chunk", st.last_manifest["chunk_name"]),
        refetched=source(include19=True, revised="2026-11-18"),
        origin_v1_sha=original_sha(),
    ), st


class P202P192OwnerD1H4OnlyNativeIsolationTests(TestCase):
    def test_01_exact_single_root_numeric_revision_gate(self):
        r, st = real_numeric_report()
        self.assertTrue(eligible_p192_h4_only(r, st))

    def test_02_no_missing_or_metadata_or_promotion_grant_can_pass(self):
        r, st = real_numeric_report()
        tamper = {
            "overlap_missing_count": 1,
            "numeric_ohlc_value_changed_count": 0,
            "metadata_changed_count": 1,
            "price_text_format_changed_count": 1,
            "overlap_sha_changed_count": 2,
            "conflict_classification": "METADATA_ONLY_CHANGED",
            "may_write_d1": True,
            "may_publish_buy_sell": True,
            "may_trade": True,
            "broker_orders": 1,
            "drive_writes": 1,
            "additional_vendor_requests": 1,
            "owner_source_rebase_or_revision_approved": True,
            "publisher_first_known_verified": True,
            "provider_vendor_revision_cause_independently_proven": True,
            "source_epoch": "P171_D1_OLD",
            "refetched_closed_native_bars_count": 0,
            "drive_reads_added_by_diagnostic": 2,
        }
        for key, value in tamper.items():
            with self.subTest(field=key):
                self.assertFalse(eligible_p192_h4_only({**r, key: value}, st))
        self.assertFalse(eligible_p192_h4_only({**r, "raw_price": "1.1000"}, st))

    def test_03_any_unsealed_or_other_d1_epoch_state_denied(self):
        r, st = real_numeric_report()
        for invalid in (
            replace(st, orphan_chunk="unsealed"),
            replace(st, manifests=2),
            replace(st, chunks=2),
            replace(st, last_manifest=None),
            replace(st, last_manifest={**st.last_manifest,
                "last_native_open_label": "2026-11-19"}),
            replace(st, last_manifest={**st.last_manifest,
                "owner_approved_cache_rebaseline": False}),
        ):
            with self.subTest(state=invalid):
                self.assertFalse(eligible_p192_h4_only(r, invalid))

    def run_fake(self, *, missing=False, h4_bad=False,
                 h4_not_due=False, d1_v1_changed=False,
                 quota=(100, 400), p192_reaudit_changed=False):
        p192_store = sealed_p192()
        old = (NEW_H4,) if h4_not_due else (OLD_H4,)
        originals = {
            "4h": state("4h", old),
            "1day": state("1day", D1_LABELS),
        }
        calls = []

        def audit(store, *, symbol, interval):
            calls.append(("audit", interval))
            if (d1_v1_changed and interval == "1day"
                    and calls.count(("audit", "1day")) == 2):
                return state("1day", D1_LABELS[:-1])
            return originals[interval]

        labels = D1_LABELS + ("2026-11-12", "2026-11-17")
        if not missing:
            labels += ("2026-11-18",)
        labels += ("2026-11-19",)
        results = {
            "4h": envelope("4h", (OLD_H4, NEW_H4),
                           amend=OLD_H4 if h4_bad else None),
            "1day": envelope("1day", labels, amend="2026-11-18"),
        }
        def fetched(_, params):
            calls.append(("vendor", params["interval"]))
            return results[params["interval"]]

        def committed(store, batch):
            calls.append(("commit", batch.interval))
            return NativeCommitReceipt(
                status="NATIVE_BATCH_COMMITTED", symbol="EUR/USD",
                interval=batch.interval,
                last_native_open_label=batch.closed_bars[-1].native_open_label,
                newly_closed_native_bars=1, total_closed_native_bars=2,
                manifest_sha256="a"*64, drive_objects_created_max=2,
            )

        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, {
                "GITHUB_EVENT_NAME": "schedule",
                "MFX_REAL_CACHE_ENABLED": "true",
                "MFX_V2_BATCH_CACHE_ACCEPTED": "true",
                "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED": "true",
                "MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED": "true",
                "MFX_D1_OWNER_REBASE_20261111": "false",
                "MFX_D1_OWNER_CUTOFF_20261118": "true",
            }))
            stack.enter_context(patch(MODULE + "._settings",
                                      return_value=("fake-key", {}, 400)))
            stack.enter_context(patch(MODULE + "._session",
                                      return_value="fake-session"))
            stack.enter_context(patch(MODULE + ".PrivateNativeDriveStore",
                                      FakeStore))
            stack.enter_context(patch(MODULE + ".NativeAuditReadThroughWitness",
                                      FakeReadThrough))
            stack.enter_context(patch(MODULE + ".audit_native_archive",
                                      side_effect=audit))
            stack.enter_context(patch(MODULE + ".PrivateD1Nov18Store",
                                      return_value=p192_store))
            stack.enter_context(patch(MODULE + "._usage",
                                      return_value=quota))
            stack.enter_context(patch(MODULE + "._read_payload",
                                      side_effect=fetched))
            stack.enter_context(patch(MODULE + ".commit_native_batch",
                                      side_effect=committed))
            if p192_reaudit_changed:
                original = audit_p192
                observed = [0]
                def rev_audit(store, *, origin_v1_sha):
                    observed[0] += 1
                    actual = original(store, origin_v1_sha=origin_v1_sha)
                    return (replace(actual, manifests=2) if observed[0] >= 2
                            else actual)
                stack.enter_context(patch(MODULE + ".audit_nov18_epoch",
                                          side_effect=rev_audit))
            stamp = stack.enter_context(patch(MODULE + ".datetime"))
            stamp.now.return_value = NOW
            out = StringIO()
            with redirect_stdout(out):
                try:
                    main()
                except ValueError as exc:
                    return str(exc), calls, out.getvalue(), p192_store
        return "NO_EXCEPTION", calls, out.getvalue(), p192_store

    def test_04_independent_h4_append_d1_stays_red_and_unchanged(self):
        err, calls, output, store = self.run_fake()
        self.assertEqual(err, "P192_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE")
        self.assertEqual([v for k, v in calls if k == "commit"], ["4h"])
        self.assertEqual([v for k, v in calls if k == "vendor"],
                         ["4h", "1day"])
        self.assertEqual([v for k, v in calls if k == "audit"],
                         ["4h", "1day", "4h", "1day"])
        self.assertEqual(store.puts, 2)
        self.assertIn("MFX_P200_P192_D1_SHA_DIFF_REDACTED_NO_COMMIT", output)
        self.assertIn("MFX_P202_H4_ONLY_P192_D1_NUMERIC_REVISED_STILL_HELD_RED",
                      output)
        lines = output.splitlines()
        marker = "MFX_P202_H4_ONLY_P192_D1_NUMERIC_REVISED_STILL_HELD_RED"
        response = json.loads(lines[lines.index(marker)+1])
        self.assertEqual(response["schema"], VERSION)
        self.assertEqual(response["h4_newly_closed_bars"], 1)
        self.assertTrue(response["h4_does_not_approve_d1"])
        self.assertTrue(response["d1_hold_persists"])
        self.assertFalse(response["may_publish_buy_sell"])
        self.assertEqual(response["owner_p192_d1_canonical_writes"], 0)
        self.assertEqual(response["broker_orders"], 0)

    def test_05_missing_18nov_overlap_never_allows_h4_commit(self):
        err, calls, output, store = self.run_fake(missing=True)
        self.assertEqual(err, "P192_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE")
        self.assertNotIn(("commit", "4h"), calls)
        self.assertEqual(store.puts, 2)

    def test_06_h4_invalid_source_self_quarantines_before_d1(self):
        err, calls, output, store = self.run_fake(h4_bad=True)
        self.assertEqual(err, "P059_SOURCE_NATIVE_REVISION_QUARANTINE")
        self.assertNotIn(("commit", "4h"), calls)

    def test_07_original_d1_sha_custody_change_blocks_h4(self):
        err, calls, output, store = self.run_fake(d1_v1_changed=True)
        self.assertEqual(err, "P059_NATIVE_ARCHIVE_CHANGED_DURING_FETCH")
        self.assertNotIn(("commit", "4h"), calls)

    def test_08_p192_parent_changed_between_source_checks_blocks_h4(self):
        err, calls, output, store = self.run_fake(p192_reaudit_changed=True)
        self.assertEqual(err, "P202_P192_EPOCH_CHANGED_BEFORE_H4")
        self.assertNotIn(("commit", "4h"), calls)

    def test_09_quota_denied_before_vendor_and_all_drive_writes(self):
        err, calls, output, store = self.run_fake(quota=(399, 400))
        self.assertEqual(err, "NO_EXCEPTION")
        self.assertFalse(any(k in ("vendor", "commit") for k, _ in calls))
        self.assertEqual(store.puts, 2)

    def test_10_no_new_h4_slot_d1_remains_red_without_h4_write(self):
        err, calls, output, store = self.run_fake(h4_not_due=True)
        self.assertEqual(err, "P192_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE")
        self.assertNotIn(("commit", "4h"), calls)

    def test_11_no_private_ohlc_label_or_secrets_in_public_logs(self):
        err, calls, output, store = self.run_fake()
        for secret in ("1.1000", "1.1041", "fake-key", 
                       "2026-11-18", "2026-11-19",
                       "stored_sha256", "refetched_sha256"):
            self.assertNotIn(secret, output)

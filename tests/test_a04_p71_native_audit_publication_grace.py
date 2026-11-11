"""A04/P0.71: H4/D1 READ-ONLY lag uses SAME publication clock as writer.

No Twelve Data API calls, no Drive writes, no broker, no local runtime.
Crosses Sydney DST and exact 2m15s boundaries as pure hermetic tests.
"""
from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
import os
from unittest.mock import patch
import unittest

from mfx_cache.native_htf_incremental import (
    SOURCE_PUBLICATION_BUFFER, plan_native_fetch,
)
from tools.run_mfx_native_htf_cache_audit import audit_native_cache, main
from test_a04_p58_native_htf_cache_audit import (
    ReadOnlyFakeStore, d1, h4, native,
)

UTC = timezone.utc


def h4_at_04() -> ReadOnlyFakeStore:
    store = ReadOnlyFakeStore()
    store.seed(native("4h", ("2026-11-11 04:00:00",)))
    return store


def single_d1(day: str) -> ReadOnlyFakeStore:
    store = ReadOnlyFakeStore()
    store.seed(native("1day",(day,)))
    return store


class PublicationSafeAuditTests(unittest.TestCase):
    def test_01_shared_2m15_buffer_is_not_reimplemented(self) -> None:
        self.assertEqual(SOURCE_PUBLICATION_BUFFER,
                         timedelta(minutes=2,seconds=15))

    def test_02_d1_sydney_before_publication_grace_not_lag(self) -> None:
        t=datetime(2026,11,11,13,2,14,tzinfo=UTC)
        result=audit_native_cache(d1(),interval="1day",now_utc=t)
        self.assertEqual(result["lag"],0)
        self.assertEqual(result["latest_publication_eligible_label"],"2026-11-10")
        self.assertEqual(result["status"],"LAST_EXPECTED_NATIVE_SLOT_PRESENT")
        self.assertEqual(result["publication_grace_seconds"],135)
        self.assertTrue(result["publication_grace_aligned_to_writer"])

    def test_03_d1_exact_135s_grace_shifts_due_day(self) -> None:
        t=datetime(2026,11,11,13,2,15,tzinfo=UTC)
        result=audit_native_cache(d1(),interval="1day",now_utc=t)
        self.assertEqual(result["lag"],1)
        self.assertEqual(result["latest_publication_eligible_label"],"2026-11-11")
        self.assertEqual(result["status"],
                         "LAGGING_OR_MARKET_CLOSED_REVIEW_REQUIRED")
        self.assertTrue(result["observed_only_not_market_session_sla"])

    def test_04_d1_before_local_midnight_no_false_lag(self) -> None:
        t=datetime(2026,11,11,12,59,59,tzinfo=UTC)
        self.assertEqual(audit_native_cache(
            d1(),interval="1day",now_utc=t)["lag"],0)

    def test_05_h4_before_publication_guard_does_not_cry_lag(self) -> None:
        t=datetime(2026,11,11,12,2,14,tzinfo=UTC)
        r=audit_native_cache(h4_at_04(),interval="4h",now_utc=t)
        self.assertEqual(r["lag"],0)
        self.assertEqual(r["latest_publication_eligible_label"],
                         "2026-11-11 04:00:00")

    def test_06_h4_at_135s_grace_is_one_slot_behind(self) -> None:
        t=datetime(2026,11,11,12,2,15,tzinfo=UTC)
        r=audit_native_cache(h4_at_04(),interval="4h",now_utc=t)
        self.assertEqual(r["lag"],1)
        self.assertEqual(r["latest_publication_eligible_label"],
                         "2026-11-11 08:00:00")

    def test_07_open_or_future_h4_still_rejected(self) -> None:
        store=ReadOnlyFakeStore()
        store.seed(native("4h",("2026-11-11 08:00:00",)))
        with self.assertRaisesRegex(ValueError,"FUTURE_OR_UNCLOSED"):
            audit_native_cache(
                store,interval="4h",
                now_utc=datetime(2026,11,11,12,2,14,tzinfo=UTC))

    def test_08_d1_fresh_bar_not_accepted_before_guard(self) -> None:
        store=single_d1("2026-11-11")
        with self.assertRaisesRegex(ValueError,"FUTURE_OR_UNCLOSED"):
            audit_native_cache(
                store,interval="1day",
                now_utc=datetime(2026,11,11,13,2,14,tzinfo=UTC))

    def test_09_sydney_dst_ends_utc_local_boundary_april(self) -> None:
        store=single_d1("2026-04-04")
        early=datetime(2026,4,5,14,2,14,tzinfo=UTC)
        late=early+timedelta(seconds=1)
        self.assertEqual(audit_native_cache(
            store,interval="1day",now_utc=early)["lag"],0)
        r=audit_native_cache(store,interval="1day",now_utc=late)
        self.assertEqual((r["lag"],r["latest_publication_eligible_label"]),
                         (1,"2026-04-05"))

    def test_10_sydney_dst_starts_utc_local_boundary_october(self) -> None:
        store=single_d1("2026-10-03")
        early=datetime(2026,10,4,13,2,14,tzinfo=UTC)
        late=early+timedelta(seconds=1)
        self.assertEqual(audit_native_cache(
            store,interval="1day",now_utc=early)["lag"],0)
        self.assertEqual(audit_native_cache(
            store,interval="1day",now_utc=late)["lag"],1)

    def test_11_reader_due_matches_existing_writer_due_both_frames(self) -> None:
        for interval,store,t_before,t_after in (
            ("4h",h4_at_04(),
             datetime(2026,11,11,12,2,14,tzinfo=UTC),
             datetime(2026,11,11,12,2,15,tzinfo=UTC)),
            ("1day",d1(),
             datetime(2026,11,11,13,2,14,tzinfo=UTC),
             datetime(2026,11,11,13,2,15,tzinfo=UTC)),
        ):
            with self.subTest(interval=interval):
                previous=store.read(
                    "manifest",store.list_names("manifest")[0])
                before=plan_native_fetch(
                    interval=interval,previous=previous,now_utc=t_before)
                after=plan_native_fetch(
                    interval=interval,previous=previous,now_utc=t_after)
                self.assertEqual(before.provider_requests_planned,0)
                self.assertEqual(after.provider_requests_planned,1)
                self.assertEqual(audit_native_cache(
                    store,interval=interval,now_utc=t_before)["lag"],0)
                self.assertEqual(audit_native_cache(
                    store,interval=interval,now_utc=t_after)["lag"],1)

    def test_12_readonly_summary_does_not_claim_no_auto_native_writer(self) -> None:
        stores=(h4(),d1())
        with patch.dict(os.environ,{
            "MFX_REAL_CACHE_ENABLED":"true",
            "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
            "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED":"true",
        }),patch(
            "tools.run_mfx_native_htf_cache_audit._drive_auth_info",
            return_value={"type":"fake"},
        ),patch(
            "tools.run_mfx_native_htf_cache_audit._require_oauth_cache_folders",
        ),patch(
            "tools.run_mfx_native_htf_cache_audit._session",
            return_value="fake",
        ),patch(
            "tools.run_mfx_native_htf_cache_audit.PrivateNativeDriveStore",
            side_effect=stores,
        ):
            buf=StringIO()
            with redirect_stdout(buf):
                main()
        output=buf.getvalue()
        receipt=json.loads(output.splitlines()[-1])
        self.assertFalse(receipt["no_automated_native_writer"])
        self.assertFalse(receipt["this_job_writes_native_archive"])
        self.assertFalse(receipt["native_writer_schedule_evaluated_here"])
        self.assertEqual(receipt["provider_price_requests"],0)
        self.assertEqual(receipt["drive_writes"],0)
        self.assertEqual(receipt["broker_orders"],0)
        self.assertNotIn("1.1030",output)

    def test_13_readonly_workflow_unchanged_frequency_and_no_vendor(self) -> None:
        from pathlib import Path
        yml=Path(".github/workflows/mfx-native-htf-cache-audit.yml").read_text()
        writer=Path(".github/workflows/mfx-native-htf-incremental-commit.yml").read_text()
        self.assertIn('cron: "45 * * * *"',yml)
        self.assertIn('cron: "25 * * * *"',writer)
        self.assertIn("MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED",writer)
        self.assertNotIn("MFX_TWELVE_DATA_API_KEY",yml)
        self.assertIn("group: mfx-twelvedata-private-cache",yml)

    def test_14_future_D1_cannot_be_promoted_at_sydney_midnight(self) -> None:
        store=single_d1("2026-11-12")
        with self.assertRaisesRegex(ValueError,"FUTURE_OR_UNCLOSED_NATIVE_D1"):
            audit_native_cache(
                store,interval="1day",
                now_utc=datetime(2026,11,11,13,30,tzinfo=UTC))


if __name__=="__main__":
    unittest.main()

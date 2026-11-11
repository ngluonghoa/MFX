"""A04/P0.67 delayed GitHub cron :00..:04 cannot starve older CLOSED M5.

Hermetic tests only. No provider, Google Drive, broker, local cache output.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import unittest

from mfx_cache.td_m5_codec import ClosedM5Bar
from mfx_cache.v2_batch_commit import _last_manifest, commit_hour
from tools.mfx_hourly_catchup import (
    latest_eligible_closed_hour, plan_bounded_catchup,
    commit_bounded_catchup,
)
from tools.run_a04_p46_cloud_batch_cache import needs_hourly_fetch

UTC=timezone.utc
BASE=datetime(2026,11,10,18,tzinfo=UTC)


class Store:
    def __init__(self) -> None:
        self.objects: dict[str,dict[str,dict[str,Any]]]={
            "manifest":{},"chunk":{}}
        self.writes=0

    def list_names(self,bucket:str) -> tuple[str,...]:
        return tuple(sorted(self.objects[bucket]))

    def read(self,bucket:str,name:str) -> dict[str,Any]:
        return copy.deepcopy(self.objects[bucket][name])

    def put_if_absent(
        self,bucket:str,name:str,body:dict[str,Any],
    ) -> None:
        if name in self.objects[bucket]:
            if self.objects[bucket][name] != body:
                raise ValueError("P067_FAKE_REWRITE_DENIED")
            return
        self.objects[bucket][name]=copy.deepcopy(body)
        self.writes+=1


def bars(hours:int) -> tuple[ClosedM5Bar,...]:
    hour=BASE+timedelta(hours=hours)
    return tuple(ClosedM5Bar(
        start_utc=(hour+timedelta(minutes=5*i)).isoformat(),
        open="1.1",high="1.11",low="1.09",close="1.105",
    ) for i in range(12))


def observed(*hours:int) -> tuple[ClosedM5Bar,...]:
    return tuple(bar for index in hours for bar in bars(index))


def seeded(*hours:int) -> Store:
    s=Store()
    for h in hours:
        r=commit_hour(s,now_utc=BASE+timedelta(hours=h+1,minutes=10),
                      observed=bars(h))
        if r.status != "BATCH_COMMITTED":
            raise AssertionError("fake seed failed")
    return s


class DelayedCronCatchupTests(unittest.TestCase):
    def test_01_utc_004_before_five_grace_uses_second_previous_hour(self) -> None:
        at=BASE+timedelta(hours=3,minutes=4)
        self.assertEqual(latest_eligible_closed_hour(at),
                         BASE+timedelta(hours=1))

    def test_02_exact_005_uses_immediately_prior_closed_hour(self) -> None:
        at=BASE+timedelta(hours=3,minutes=5)
        self.assertEqual(latest_eligible_closed_hour(at),
                         BASE+timedelta(hours=2))

    def test_03_000_and_059_clock_edges_are_safe(self) -> None:
        for minute,eligible in ((0,1),(4,1),(5,2),(59,2)):
            at=BASE+timedelta(hours=3,minutes=minute)
            self.assertEqual(latest_eligible_closed_hour(at),
                             BASE+timedelta(hours=eligible))

    def test_04_non_utc_and_naive_rejected(self) -> None:
        bad=(datetime(2026,11,10,21,4),
             datetime(2026,11,11,4,4,
                      tzinfo=timezone(timedelta(hours=7))))
        for now in bad:
            with self.assertRaisesRegex(ValueError,"EXACT_UTC"):
                latest_eligible_closed_hour(now)

    def test_05_original_blank_bootstrap_no_poll_before_005(self) -> None:
        self.assertFalse(needs_hourly_fetch(
            Store(),BASE+timedelta(hours=3,minutes=4)))

    def test_06_delayed_next_hour_004_with_old_m5_does_poll(self) -> None:
        d=seeded(0)
        self.assertTrue(needs_hourly_fetch(
            d,BASE+timedelta(hours=3,minutes=4)))

    def test_07_fresh_eligible_hour_never_polls_unready_new_hour(self) -> None:
        d=seeded(0,1)
        self.assertFalse(needs_hourly_fetch(
            d,BASE+timedelta(hours=3,minutes=4)))
        self.assertTrue(needs_hourly_fetch(
            d,BASE+timedelta(hours=3,minutes=5)))

    def test_08_catchup_pre005_only_older_safe_hour(self) -> None:
        now=BASE+timedelta(hours=3,minutes=4)
        p=plan_bounded_catchup(
            observed(0,1,2),previous_hour_utc=BASE.isoformat(),now_utc=now)
        self.assertEqual(tuple(x[0] for x in p),(BASE+timedelta(hours=1),))

    def test_09_catchup_at_005_includes_newly_eligible_prior_hour(self) -> None:
        now=BASE+timedelta(hours=3,minutes=5)
        p=plan_bounded_catchup(
            observed(0,1,2),previous_hour_utc=BASE.isoformat(),now_utc=now)
        self.assertEqual(tuple(x[0] for x in p),(
            BASE+timedelta(hours=1),BASE+timedelta(hours=2)))

    def test_10_delayed_at_004_recover_real_hour_parent_sha(self) -> None:
        d=seeded(0)
        prior=d.writes
        now=BASE+timedelta(hours=3,minutes=4)
        p=plan_bounded_catchup(
            observed(0,1,2),previous_hour_utc=BASE.isoformat(),now_utc=now)
        receipts=commit_bounded_catchup(d,p,real_now_utc=now)
        self.assertEqual(len(receipts),1)
        self.assertEqual(receipts[0].committed_hour_utc,
                         (BASE+timedelta(hours=1)).isoformat())
        self.assertEqual(d.writes,prior+2)
        _,last=_last_manifest(d)
        assert last is not None
        self.assertEqual(last["total_batches"],2)
        self.assertEqual(last["gap_prior_hours_unverified"],0)
        self.assertEqual(last["continuity_status"],"CONTIGUOUS_WITH_PRIOR_BATCH")

    def test_11_004_never_writes_last_hour_closed_only_four_minutes(self) -> None:
        d=seeded(0)
        now=BASE+timedelta(hours=3,minutes=4)
        future=((BASE+timedelta(hours=2),bars(2)),)
        prior=d.writes
        with self.assertRaisesRegex(ValueError,"FUTURE_TARGET"):
            commit_bounded_catchup(d,future,real_now_utc=now)
        self.assertEqual(d.writes,prior)

    def test_12_at_004_when_no_older_uncommitted_m5_zero_fetch(self) -> None:
        d=seeded(0,1)
        self.assertFalse(needs_hourly_fetch(
            d,BASE+timedelta(hours=3,minutes=4)))
        p=plan_bounded_catchup(
            observed(0,1,2),previous_hour_utc=
            (BASE+timedelta(hours=1)).isoformat(),
            now_utc=BASE+timedelta(hours=3,minutes=4))
        self.assertEqual(p,())

    def test_13_midnight_rollover_does_not_shift_utc_grid(self) -> None:
        now=datetime(2026,11,11,0,4,tzinfo=UTC)
        self.assertEqual(latest_eligible_closed_hour(now),
                         datetime(2026,11,10,22,tzinfo=UTC))
        self.assertEqual(latest_eligible_closed_hour(
            now+timedelta(minutes=1)),
            datetime(2026,11,10,23,tzinfo=UTC))

    def test_14_wrong_clock_does_not_grant_broker_or_source(self) -> None:
        with self.assertRaisesRegex(ValueError,"EXACT_UTC"):
            needs_hourly_fetch(Store(),datetime(2026,11,10,21,4))

    def test_15_existing_hourly_workflow_and_one_vendor_fetch_unchanged(self) -> None:
        yml=Path(".github/workflows/twelve-data-cache.yml").read_text()
        writer=Path("tools/run_a04_p46_cloud_batch_cache.py").read_text()
        self.assertIn('cron: "10 * * * *"',yml)
        self.assertIn("mfx-twelvedata-private-cache",yml)
        self.assertIn("MFX_V2_BATCH_CACHE_ACCEPTED",yml)
        self.assertEqual(writer.count("vendor_payload = _vendor_m5("),1)
        self.assertIn("latest_eligible_closed_hour",writer)
        self.assertNotIn("broker.submit",writer)


if __name__=="__main__":
    unittest.main()

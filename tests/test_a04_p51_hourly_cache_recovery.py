"""P0.51: immutable B1 hourly catchup (one vendor fetch), offline tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import copy
import unittest

from mfx_cache.td_m5_codec import ClosedM5Bar
from mfx_cache.v2_batch_commit import _last_manifest, commit_hour
from tools.mfx_hourly_catchup import (
    MAX_RECOVERY_BATCHES, plan_bounded_catchup, commit_bounded_catchup,
)

UTC = timezone.utc
BASE = datetime(2026, 11, 10, 18, tzinfo=UTC)


class FakeStore:
    def __init__(self) -> None:
        self.objects: dict[str, dict[str, dict[str, Any]]] = {
            "chunk": {}, "manifest": {},
        }
        self.writes = 0

    def list_names(self, bucket: str) -> tuple[str, ...]:
        return tuple(sorted(self.objects[bucket]))

    def read(self, bucket: str, name: str) -> dict[str, Any]:
        return copy.deepcopy(self.objects[bucket][name])

    def put_if_absent(
        self, bucket: str, name: str, body: dict[str, Any],
    ) -> None:
        if name in self.objects[bucket]:
            if self.objects[bucket][name] != body:
                raise ValueError("P051_FAKE_IMMUTABLE_OBJECT_REWRITE_DENIED")
            return
        self.objects[bucket][name] = copy.deepcopy(body)
        self.writes += 1


def rows(hour: datetime) -> tuple[ClosedM5Bar, ...]:
    return tuple(ClosedM5Bar(
        start_utc=(hour+timedelta(minutes=5*i)).isoformat(),
        open="1.10000", high="1.12000", low="1.09000",
        close="1.11000",
    ) for i in range(12))


def bulk(*hours: int) -> tuple[ClosedM5Bar, ...]:
    return tuple(b for i in hours for b in rows(BASE+timedelta(hours=i)))


class P051CatchupTests(unittest.TestCase):
    def test_01_bootstrap_only_immediately_prior_full_hour(self) -> None:
        r = plan_bounded_catchup(
            bulk(0,1,2,3), previous_hour_utc=None,
            now_utc=BASE+timedelta(hours=4,minutes=10))
        self.assertEqual([h for h,_ in r],[BASE+timedelta(hours=3)])

    def test_02_recovers_three_missing_hours_in_order(self) -> None:
        r = plan_bounded_catchup(
            bulk(0,1,2,3), previous_hour_utc=BASE.isoformat(),
            now_utc=BASE+timedelta(hours=4,minutes=10))
        self.assertEqual([h for h,_ in r], [
            BASE+timedelta(hours=1),BASE+timedelta(hours=2),
            BASE+timedelta(hours=3)])
        self.assertEqual([len(x) for _,x in r],[12,12,12])

    def test_03_4_hour_limit_is_fail_closed_for_writes(self) -> None:
        r = plan_bounded_catchup(
            bulk(0,1,2,3,4,5,6),previous_hour_utc=BASE.isoformat(),
            now_utc=BASE+timedelta(hours=7,minutes=10))
        self.assertEqual(len(r),MAX_RECOVERY_BATCHES)
        self.assertEqual(r[-1][0],BASE+timedelta(hours=4))

    def test_04_missing_partial_hour_not_synthesized(self) -> None:
        observed = bulk(1)+rows(BASE+timedelta(hours=2))[:-1]+bulk(3)
        r = plan_bounded_catchup(
            observed,previous_hour_utc=BASE.isoformat(),
            now_utc=BASE+timedelta(hours=4,minutes=10))
        self.assertEqual([h for h,_ in r],[
            BASE+timedelta(hours=1),BASE+timedelta(hours=3)])

    def test_05_stale_fetch_with_no_complete_hour_is_noop(self) -> None:
        r = plan_bounded_catchup(
            rows(BASE)[:6],previous_hour_utc=BASE.isoformat(),
            now_utc=BASE+timedelta(hours=2,minutes=10))
        self.assertEqual(r,())

    def test_06_all_prior_hours_already_sealed_noop(self) -> None:
        r=plan_bounded_catchup(
            bulk(0,1),previous_hour_utc=(BASE+timedelta(hours=1)).isoformat(),
            now_utc=BASE+timedelta(hours=2,minutes=10))
        self.assertEqual(r,())

    def test_07_pre_close_grace_is_noop(self) -> None:
        r=plan_bounded_catchup(
            bulk(0,1),previous_hour_utc=BASE.isoformat(),
            now_utc=BASE+timedelta(hours=2,minutes=4))
        self.assertEqual(r,())

    def test_08_invalid_previous_hour_is_denied(self) -> None:
        with self.assertRaisesRegex(ValueError,"PREVIOUS_HOUR_INVALID"):
            plan_bounded_catchup(
                bulk(0,1),previous_hour_utc="2026-11-10T18:12:00+00:00",
                now_utc=BASE+timedelta(hours=2,minutes=10))

    def test_09_non_utc_clock_denied(self) -> None:
        with self.assertRaisesRegex(ValueError,"EXACT_UTC"):
            plan_bounded_catchup(
                bulk(0,1),previous_hour_utc=None,
                now_utc=datetime(2026,11,10,20,10))

    def test_10_more_than_120_rows_denied(self) -> None:
        r=bulk(*range(11))
        self.assertGreater(len(r),120)
        with self.assertRaisesRegex(ValueError,"VENDOR_M5_BOUNDED"):
            plan_bounded_catchup(
                r,previous_hour_utc=BASE.isoformat(),
                now_utc=BASE+timedelta(hours=12,minutes=10))

    def test_11_duplicate_m5_timestamps_denied(self) -> None:
        r=rows(BASE+timedelta(hours=1))
        with self.assertRaises(ValueError):
            plan_bounded_catchup(
                r[:1]+r[:1]+r[1:],
                previous_hour_utc=BASE.isoformat(),
                now_utc=BASE+timedelta(hours=2,minutes=10))

    def test_12_real_b1_engine_appends_three_sha_linked_hours(self) -> None:
        d=FakeStore()
        result=commit_hour(
            d,now_utc=BASE+timedelta(hours=1,minutes=10),
            observed=rows(BASE))
        self.assertEqual(result.status,"BATCH_COMMITTED")
        plan=plan_bounded_catchup(
            bulk(0,1,2,3),previous_hour_utc=BASE.isoformat(),
            now_utc=BASE+timedelta(hours=4,minutes=10))
        receipts=commit_bounded_catchup(
            d,plan,real_now_utc=BASE+timedelta(hours=4,minutes=10))
        self.assertEqual(len(receipts),3)
        self.assertEqual((len(d.objects["chunk"]),len(d.objects["manifest"])),
                         (4,4))
        _,last=_last_manifest(d)
        assert last is not None
        self.assertEqual(last["total_batches"],4)
        self.assertEqual(last["total_closed_m5"],48)
        self.assertEqual(last["continuity_status"],
                         "CONTIGUOUS_WITH_PRIOR_BATCH")
        self.assertEqual(last["gap_prior_hours_unverified"],0)
        self.assertEqual(d.writes,8)

    def test_13_missing_middle_hour_explicitly_marked_gap(self) -> None:
        d=FakeStore()
        commit_hour(d,now_utc=BASE+timedelta(hours=1,minutes=10),
                    observed=rows(BASE))
        plan=plan_bounded_catchup(
            bulk(1,3),previous_hour_utc=BASE.isoformat(),
            now_utc=BASE+timedelta(hours=4,minutes=10))
        commit_bounded_catchup(
            d,plan,real_now_utc=BASE+timedelta(hours=4,minutes=10))
        _,last=_last_manifest(d)
        assert last is not None
        self.assertEqual(last["gap_prior_hours_unverified"],1)
        self.assertEqual(last["continuity_status"],
                         "MISSING_PRIOR_HOURS_UNVERIFIED")

    def test_14_rerun_with_current_manifest_performs_zero_writes(self) -> None:
        d=FakeStore()
        commit_hour(d,now_utc=BASE+timedelta(hours=1,minutes=10),
                    observed=rows(BASE))
        plan=plan_bounded_catchup(
            bulk(1,2),previous_hour_utc=BASE.isoformat(),
            now_utc=BASE+timedelta(hours=3,minutes=10))
        commit_bounded_catchup(
            d,plan,real_now_utc=BASE+timedelta(hours=3,minutes=10))
        before=d.writes
        _,last=_last_manifest(d)
        assert last is not None
        again=plan_bounded_catchup(
            bulk(0,1,2),previous_hour_utc=last["hour_utc"],
            now_utc=BASE+timedelta(hours=3,minutes=10))
        self.assertEqual(again,())
        self.assertEqual(commit_bounded_catchup(
            d,again,real_now_utc=BASE+timedelta(hours=3,minutes=10)),())
        self.assertEqual(d.writes,before)

    def test_15_future_recovery_target_denied(self) -> None:
        d=FakeStore()
        plan=((BASE+timedelta(hours=2),rows(BASE+timedelta(hours=2))),)
        with self.assertRaisesRegex(ValueError,"FUTURE_TARGET"):
            commit_bounded_catchup(
                d,plan,real_now_utc=BASE+timedelta(hours=2,minutes=30))
        self.assertEqual(d.writes,0)

    def test_16_unordered_recovery_targets_denied(self) -> None:
        d=FakeStore()
        plan=((BASE+timedelta(hours=1),rows(BASE+timedelta(hours=1))),
              (BASE,rows(BASE)))
        with self.assertRaisesRegex(ValueError,"UNORDERED"):
            commit_bounded_catchup(
                d,plan,real_now_utc=BASE+timedelta(hours=3,minutes=10))

    def test_17_bounded_batch_count_enforced(self) -> None:
        d=FakeStore()
        plan=tuple(
            (BASE+timedelta(hours=i),rows(BASE+timedelta(hours=i)))
            for i in range(5))
        with self.assertRaisesRegex(ValueError,"BATCH_BOUND"):
            commit_bounded_catchup(
                d,plan,real_now_utc=BASE+timedelta(hours=6,minutes=10))
        self.assertEqual(d.writes,0)

    def test_18_writer_still_single_hourly_fetch_one_concurrency_group(self) -> None:
        y=Path(".github/workflows/twelve-data-cache.yml").read_text(
            encoding="utf-8")
        t=Path("tools/run_a04_p46_cloud_batch_cache.py").read_text(
            encoding="utf-8")
        self.assertIn('cron: "10 * * * *"',y)
        self.assertIn("mfx-twelvedata-private-cache",y)
        self.assertIn("MFX_REAL_CACHE_ENABLED",y)
        self.assertIn("plan_bounded_catchup",t)
        self.assertIn("commit_bounded_catchup",t)
        self.assertEqual(t.count("vendor_payload = _vendor_m5("),1)
        self.assertNotIn("broker.submit",t)

    def test_19_empty_vendor_bars_do_not_create_files(self) -> None:
        d=FakeStore()
        p=plan_bounded_catchup(
            (),previous_hour_utc=None,
            now_utc=BASE+timedelta(hours=2,minutes=10))
        self.assertEqual(p,())
        self.assertEqual(commit_bounded_catchup(
            d,p,real_now_utc=BASE+timedelta(hours=2,minutes=10)),())
        self.assertEqual(d.writes,0)


if __name__=="__main__":
    unittest.main()

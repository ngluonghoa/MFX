"""P046-B1: offline fake Google Drive hourly batch commit/recovery regression."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any
import copy
import unittest

from mfx_cache.td_m5_codec import ClosedM5Bar, digest
from mfx_cache.v2_batch_commit import (
    BatchPlan, PrivateObjectStore, _last_manifest,
    commit_hour, plan_closed_hour,
)
from tools.run_a04_p46_cloud_batch_cache import needs_hourly_fetch

UTC = timezone.utc
HOUR = datetime(2026, 11, 10, 13, tzinfo=UTC)
NOW = HOUR + timedelta(minutes=10)
BASE = HOUR - timedelta(hours=1)


def hour_rows(hour: datetime = BASE) -> tuple[ClosedM5Bar, ...]:
    return tuple(ClosedM5Bar(
        start_utc=(hour + timedelta(minutes=5*i)).isoformat(),
        open="1.10000", high="1.11000", low="1.09000",
        close=str(1.1 + i/100000),
    ) for i in range(12))


class FakeDrive(PrivateObjectStore):
    def __init__(self) -> None:
        self.objects: dict[str, dict[str, dict[str, Any]]] = {
            "chunk": {}, "manifest": {},
        }
        self.fail_once_after_chunk = False
        self.fail_once_after_manifest = False
        self.read_corrupt_for: tuple[str, str] | None = None
        self.list_hide_for: tuple[str, str] | None = None
        self.writes: list[tuple[str, str]] = []

    def list_names(self, bucket: str) -> tuple[str, ...]:
        return tuple(sorted(
            n for n in self.objects[bucket]
            if self.list_hide_for != (bucket, n)
        ))

    def read(self, bucket: str, name: str) -> dict[str, Any]:
        record = copy.deepcopy(self.objects[bucket][name])
        if self.read_corrupt_for == (bucket, name):
            record["broker_orders"] = 1
        return record

    def put_if_absent(
        self, bucket: str, name: str, body: dict[str, Any],
    ) -> None:
        existing = self.objects[bucket].get(name)
        if existing is not None:
            if existing != body:
                raise ValueError("P046_B1_FAKE_OVERWRITE_DENIED")
            return
        self.objects[bucket][name] = copy.deepcopy(body)
        self.writes.append((bucket, name))
        if bucket == "chunk" and self.fail_once_after_chunk:
            self.fail_once_after_chunk = False
            raise OSError("P046_B1_FAKE_CRASH_AFTER_CHUNK")
        if bucket == "manifest" and self.fail_once_after_manifest:
            self.fail_once_after_manifest = False
            raise OSError("P046_B1_FAKE_CRASH_AFTER_MANIFEST")


class P046B1HourlyCommitTests(unittest.TestCase):
    def test_01_first_hour_commits_two_files(self) -> None:
        d = FakeDrive()
        r = commit_hour(d, now_utc=NOW, observed=hour_rows())
        self.assertEqual(r.status, "BATCH_COMMITTED")
        self.assertEqual((len(d.objects["chunk"]),len(d.objects["manifest"])),
                         (1,1))
        self.assertEqual(r.new_closed_m5, 12)

    def test_02_exact_four_m15_two_m30_one_h1(self) -> None:
        d = FakeDrive()
        commit_hour(d, now_utc=NOW, observed=hour_rows())
        chunk = next(iter(d.objects["chunk"].values()))
        self.assertEqual({f:len(v) for f,v in chunk["derived"].items()},
                         {"M15":4,"M30":2,"H1":1})
        self.assertTrue(all(not row["is_source_native"]
                            for v in chunk["derived"].values() for row in v))

    def test_03_no_numeric_signals_source_side_and_utc(self) -> None:
        d = FakeDrive()
        commit_hour(d, now_utc=NOW, observed=hour_rows())
        for b in ("chunk","manifest"):
            obj = next(iter(d.objects[b].values()))
            self.assertIs(obj["approved_original_numeric_signals"],False)
            self.assertEqual(obj["broker_orders"],0)
            self.assertEqual(obj["source_side"],"MID")
            self.assertEqual(obj["timezone"],"UTC")

    def test_04_second_same_hour_is_noop_no_files(self) -> None:
        d = FakeDrive()
        commit_hour(d, now_utc=NOW, observed=hour_rows())
        r = commit_hour(d, now_utc=NOW, observed=hour_rows())
        self.assertEqual(r.status, "NOT_DUE_OR_INCOMPLETE_HOUR")
        self.assertEqual(len(d.writes),2)

    def test_05_hour_before_five_minute_grace_skips(self) -> None:
        d = FakeDrive()
        r = commit_hour(d, now_utc=HOUR+timedelta(minutes=4),
                        observed=hour_rows())
        self.assertEqual(r.new_closed_m5,0)
        self.assertEqual(d.writes,[])

    def test_06_incomplete_hour_skips_with_no_manifest(self) -> None:
        d = FakeDrive()
        r = commit_hour(d,now_utc=NOW,observed=hour_rows()[:-1])
        self.assertEqual(r.status,"NOT_DUE_OR_INCOMPLETE_HOUR")
        self.assertEqual(d.writes,[])

    def test_07_missing_middle_bar_skips_not_synthesizes(self) -> None:
        d = FakeDrive()
        sample = hour_rows()
        r = commit_hour(d,now_utc=NOW,
                        observed=sample[:5]+sample[6:])
        self.assertEqual(r.new_closed_m5,0)
        self.assertEqual(d.writes,[])

    def test_08_fake_crash_after_chunk_then_recover_without_prices(self) -> None:
        d = FakeDrive()
        d.fail_once_after_chunk = True
        with self.assertRaisesRegex(OSError,"P046_B1_FAKE_CRASH_AFTER_CHUNK"):
            commit_hour(d,now_utc=NOW,observed=hour_rows())
        self.assertEqual((len(d.objects["chunk"]),len(d.objects["manifest"])),
                         (1,0))
        replay = commit_hour(d,now_utc=NOW)
        self.assertEqual(replay.status,"RECOVERED_UNCOMMITTED_CHUNK")
        self.assertTrue(replay.recovered_orphan)
        self.assertEqual(len(d.objects["manifest"]),1)
        self.assertEqual(len(d.writes),2)

    def test_09_recover_after_hour_changed_before_api(self) -> None:
        d = FakeDrive()
        d.fail_once_after_chunk = True
        with self.assertRaises(OSError):
            commit_hour(d,now_utc=NOW,observed=hour_rows())
        recovered=commit_hour(d,now_utc=NOW+timedelta(hours=3))
        self.assertEqual(recovered.status,"RECOVERED_UNCOMMITTED_CHUNK")
        self.assertEqual(recovered.actual_twelve_data_calls,0)

    def test_10_manifest_uploaded_then_crash_is_idempotent(self) -> None:
        d=FakeDrive()
        d.fail_once_after_manifest=True
        with self.assertRaisesRegex(OSError,"FAKE_CRASH_AFTER_MANIFEST"):
            commit_hour(d,now_utc=NOW,observed=hour_rows())
        self.assertEqual(len(d.objects["manifest"]),1)
        r=commit_hour(d,now_utc=NOW,observed=hour_rows())
        self.assertEqual(r.status,"NOT_DUE_OR_INCOMPLETE_HOUR")
        self.assertEqual(len(d.writes),2)

    def test_11_next_hour_chain_increments(self) -> None:
        d=FakeDrive()
        commit_hour(d,now_utc=NOW,observed=hour_rows())
        later=NOW+timedelta(hours=1)
        commit_hour(d,now_utc=later,observed=hour_rows(BASE+timedelta(hours=1)))
        _,m=_last_manifest(d)
        self.assertEqual(m["total_batches"],2)
        self.assertEqual(m["total_closed_m5"],24)
        self.assertEqual(m["continuity_status"],"CONTIGUOUS_WITH_PRIOR_BATCH")
        self.assertEqual(m["gap_prior_hours_unverified"],0)

    def test_12_skipped_hour_is_not_marked_contiguous(self) -> None:
        d=FakeDrive()
        commit_hour(d,now_utc=NOW,observed=hour_rows())
        later=NOW+timedelta(hours=3)
        commit_hour(d,now_utc=later,observed=hour_rows(BASE+timedelta(hours=3)))
        _,m=_last_manifest(d)
        self.assertEqual(m["continuity_status"],"MISSING_PRIOR_HOURS_UNVERIFIED")
        self.assertEqual(m["gap_prior_hours_unverified"],2)

    def test_13_first_hour_does_not_claim_verified_history(self) -> None:
        d=FakeDrive()
        commit_hour(d,now_utc=NOW,observed=hour_rows())
        _,m=_last_manifest(d)
        self.assertEqual(m["continuity_status"],"BOOTSTRAP_HISTORY_UNVERIFIED")

    def test_14_conflicting_manifest_same_hour_fails_closed(self) -> None:
        d=FakeDrive()
        commit_hour(d,now_utc=NOW,observed=hour_rows())
        key=next(iter(d.objects["manifest"]))
        d.objects["manifest"][key+"_fork"]=d.objects["manifest"][key]
        with self.assertRaisesRegex(ValueError,"FORKED_MANIFEST_HOUR"):
            commit_hour(d,now_utc=NOW,observed=hour_rows())

    def test_15_manifest_parent_link_tamper_fails_closed(self) -> None:
        d=FakeDrive()
        commit_hour(d,now_utc=NOW,observed=hour_rows())
        commit_hour(d,now_utc=NOW+timedelta(hours=1),
                    observed=hour_rows(BASE+timedelta(hours=1)))
        latest=max(d.objects["manifest"])
        d.objects["manifest"][latest]["parent_manifest_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"OBJECT_NAME_CONTENT_SHA_MISMATCH"):
            commit_hour(d,now_utc=NOW+timedelta(hours=2))

    def test_16_corrupted_chunk_hash_name_blocks_recovery(self) -> None:
        d=FakeDrive()
        d.fail_once_after_chunk=True
        with self.assertRaises(OSError):
            commit_hour(d,now_utc=NOW,observed=hour_rows())
        key=next(iter(d.objects["chunk"]))
        d.objects["chunk"][key]["source_side"]="ASK"
        with self.assertRaisesRegex(ValueError,"OBJECT_NAME_CONTENT_SHA_MISMATCH"):
            commit_hour(d,now_utc=NOW)

    def test_17_multiple_orphans_same_parent_are_quarantined(self) -> None:
        d=FakeDrive()
        d.fail_once_after_chunk=True
        with self.assertRaises(OSError):
            commit_hour(d,now_utc=NOW,observed=hour_rows())
        c=next(iter(d.objects["chunk"].values()))
        from mfx_cache.v2_batch_commit import _make_plan
        extra=_make_plan(None,hour_utc=(BASE+timedelta(hours=1)).isoformat(),
                         bars=hour_rows(BASE+timedelta(hours=1)),
                         now_utc=NOW+timedelta(hours=2))
        d.objects["chunk"][extra.chunk_name]=extra.chunk
        with self.assertRaisesRegex(ValueError,"MULTIPLE_UNCOMMITTED_SIBLING"):
            commit_hour(d,now_utc=NOW+timedelta(hours=2))

    def test_18_readback_corruption_blocks_publish(self) -> None:
        d=FakeDrive()
        original=d.put_if_absent
        def tampering(bucket:str,name:str,body:dict[str,Any])->None:
            original(bucket,name,body)
            if bucket=="chunk":
                d.read_corrupt_for=(bucket,name)
        d.put_if_absent=tampering # type: ignore[method-assign]
        with self.assertRaisesRegex(ValueError,"CHUNK_READBACK_MISMATCH"):
            commit_hour(d,now_utc=NOW,observed=hour_rows())
        self.assertEqual(d.objects["manifest"],{})

    def test_19_stale_writes_cannot_replace_committed_chunk(self) -> None:
        d=FakeDrive()
        commit_hour(d,now_utc=NOW,observed=hour_rows())
        key=next(iter(d.objects["chunk"]))
        fake=copy.deepcopy(d.objects["chunk"][key])
        fake["source_side"]="BID"
        with self.assertRaisesRegex(ValueError,"FAKE_OVERWRITE_DENIED"):
            d.put_if_absent("chunk",key,fake)

    def test_20_missing_chunk_parent_not_silently_accepted(self) -> None:
        d=FakeDrive()
        commit_hour(d,now_utc=NOW,observed=hour_rows())
        manifest=next(iter(d.objects["manifest"].values()))
        self.assertIn(manifest["chunk_name"],d.objects["chunk"])

    def test_21_complete_hour_plan_names_are_sha_pinned(self) -> None:
        p=plan_closed_hour(None,hour_rows(),now_utc=NOW)
        self.assertIsInstance(p,BatchPlan)
        assert p is not None
        self.assertIn(digest(p.chunk),p.chunk_name)
        self.assertIn(digest(p.manifest),p.manifest_name)

    def test_22_original_M5_input_change_changes_chunk_hash(self) -> None:
        x=hour_rows()
        a=plan_closed_hour(None,x,now_utc=NOW)
        y=x[:3]+(replace(x[3],close="1.10777"),)+x[4:]
        b=plan_closed_hour(None,y,now_utc=NOW)
        assert a is not None and b is not None
        self.assertNotEqual(a.chunk_sha256,b.chunk_sha256)

    def test_23_bars_must_be_exact_utc_alignment(self) -> None:
        x=hour_rows()
        y=(replace(x[0],start_utc="2026-11-10T12:01:00+00:00"),)+x[1:]
        with self.assertRaises(ValueError):
            plan_closed_hour(None,y,now_utc=NOW)

    def test_24_no_future_close_allowed(self) -> None:
        from mfx_cache.v2_engine import validate_m5
        x=hour_rows()
        with self.assertRaisesRegex(ValueError,"P046_FUTURE_OPEN"):
            validate_m5(x,asof_utc=BASE+timedelta(minutes=30))

    def test_25_smart_hour_due_without_provider_call(self) -> None:
        d=FakeDrive()
        self.assertTrue(needs_hourly_fetch(d,NOW))
        commit_hour(d,now_utc=NOW,observed=hour_rows())
        self.assertFalse(needs_hourly_fetch(d,NOW))
        self.assertTrue(needs_hourly_fetch(d,NOW+timedelta(hours=1)))

    def test_26_no_fetch_before_five_minute_grace(self) -> None:
        self.assertFalse(needs_hourly_fetch(FakeDrive(),HOUR+timedelta(minutes=4)))

    def test_27_uncommitted_orphan_priority_over_new_vendor_data(self) -> None:
        d=FakeDrive()
        d.fail_once_after_chunk=True
        with self.assertRaises(OSError):
            commit_hour(d,now_utc=NOW,observed=hour_rows())
        r=commit_hour(d,now_utc=NOW+timedelta(hours=1),
                      observed=hour_rows(BASE+timedelta(hours=1)))
        self.assertTrue(r.recovered_orphan)
        self.assertEqual(len(d.objects["manifest"]),1)

    def test_28_unknown_manifest_schema_fails_closed(self) -> None:
        d=FakeDrive()
        commit_hour(d,now_utc=NOW,observed=hour_rows())
        name=next(iter(d.objects["manifest"]))
        d.objects["manifest"][name]["schema"]="FX2"
        with self.assertRaisesRegex(ValueError,"P046_B1_STRICT_OBJECT_SCHEMA"):
            commit_hour(d,now_utc=NOW)

    def test_29_unsupported_storage_bucket_denied(self) -> None:
        from tools.run_a04_p46_cloud_batch_cache import PrivateDriveBatchStore
        with self.assertRaisesRegex(ValueError,"UNAUTHORIZED_DRIVE_BUCKET"):
            PrivateDriveBatchStore._folder("secrets")

    def test_30_no_network_if_dual_activation_missing(self) -> None:
        import os
        from unittest.mock import patch
        from tools.run_a04_p46_cloud_batch_cache import main
        with patch.dict(os.environ,{
            "MFX_REAL_CACHE_ENABLED":"false",
            "MFX_V2_BATCH_CACHE_ACCEPTED":"false",
        }):
            main()

    def test_31_manifest_total_and_sha_are_deterministic(self) -> None:
        x=plan_closed_hour(None,hour_rows(),now_utc=NOW)
        y=plan_closed_hour(None,hour_rows(),now_utc=NOW)
        self.assertEqual(x,y)
        assert x is not None
        self.assertEqual(x.manifest["total_closed_m5"],12)

    def test_32_unchanged_provider_data_do_not_write_again(self) -> None:
        d=FakeDrive()
        commit_hour(d,now_utc=NOW,observed=hour_rows())
        r=commit_hour(d,now_utc=NOW,observed=hour_rows())
        self.assertEqual(r.drive_object_writes_expected,0)
        self.assertEqual(len(d.writes),2)

    def test_33_bad_time_zone_now_denied(self) -> None:
        with self.assertRaisesRegex(ValueError,"P046_B1_UTC_NOW_REQUIRED"):
            plan_closed_hour(None,hour_rows(),now_utc=NOW.replace(tzinfo=None))

    def test_34_unknown_chain_manifest_is_not_auto_repaired(self) -> None:
        d=FakeDrive()
        commit_hour(d,now_utc=NOW,observed=hour_rows())
        commit_hour(d,now_utc=NOW+timedelta(hours=1),
                    observed=hour_rows(BASE+timedelta(hours=1)))
        first=sorted(d.objects["manifest"])[0]
        del d.objects["manifest"][first]
        with self.assertRaisesRegex(ValueError,"INVALID_ROOT_MANIFEST"):
            commit_hour(d,now_utc=NOW+timedelta(hours=2))

    def test_35_referenced_chunk_missing_blocks_cache_state(self) -> None:
        d=FakeDrive()
        commit_hour(d,now_utc=NOW,observed=hour_rows())
        del d.objects["chunk"][next(iter(d.objects["chunk"]))]
        with self.assertRaises(ValueError):
            commit_hour(d,now_utc=NOW)

    def test_36_second_chunk_same_committed_hour_is_fork(self) -> None:
        d=FakeDrive()
        commit_hour(d,now_utc=NOW,observed=hour_rows())
        from mfx_cache.v2_batch_commit import _make_plan
        other=hour_rows()
        changed=other[:1]+(replace(other[1],close="1.10990"),)+other[2:]
        plan=_make_plan(None,hour_utc=BASE.isoformat(),
                        bars=changed,now_utc=NOW)
        d.objects["chunk"][plan.chunk_name]=plan.chunk
        with self.assertRaisesRegex(ValueError,"CONFLICTING_COMMITTED_HOUR"):
            commit_hour(d,now_utc=NOW)

    def test_37_workflow_uses_new_writer_and_dual_activation(self) -> None:
        from pathlib import Path
        y=Path(".github/workflows/twelve-data-cache.yml").read_text(
            encoding="utf-8")
        self.assertIn("MFX_REAL_CACHE_ENABLED",y)
        self.assertIn("MFX_V2_BATCH_CACHE_ACCEPTED",y)
        self.assertIn("python -m tools.run_a04_p46_cloud_batch_cache",y)
        self.assertNotIn(
            "python -m tools.run_a04_p45_cloud_twelve_data_cache",y)
        self.assertIn('cron: "10 * * * *"',y)

    def test_35_manifest_has_gap_and_no_trade_outcomes(self) -> None:
        d=FakeDrive()
        commit_hour(d,now_utc=NOW,observed=hour_rows())
        r=commit_hour(d,now_utc=NOW+timedelta(hours=3),
                      observed=hour_rows(BASE+timedelta(hours=3)))
        self.assertEqual(r.real_user_signals,0)
        self.assertEqual(r.broker_orders,0)


if __name__ == "__main__":
    unittest.main()

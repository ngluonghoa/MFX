"""A04/P0.50 read-only live cache audit — hermetic negative/positive tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import copy
import unittest

from mfx_cache.td_m5_codec import ClosedM5Bar
from mfx_cache.v2_batch_commit import commit_hour
from tools.run_mfx_hourly_cache_audit import audit_recent_cache

UTC = timezone.utc
START = datetime(2026, 11, 10, 20, tzinfo=UTC)


class FakeReadOnlyAuditStore:
    def __init__(self) -> None:
        self.objects: dict[str, dict[str, dict[str, Any]]] = {
            "chunk": {}, "manifest": {},
        }
        self.write_count = 0

    def list_names(self, bucket: str) -> tuple[str, ...]:
        return tuple(sorted(self.objects[bucket]))

    def read(self, bucket: str, name: str) -> dict[str, Any]:
        return copy.deepcopy(self.objects[bucket][name])

    def put_if_absent(
        self, bucket: str, name: str, body: dict[str, Any],
    ) -> None:
        assert name not in self.objects[bucket]
        self.objects[bucket][name] = copy.deepcopy(body)
        self.write_count += 1


def bars(hour: datetime) -> tuple[ClosedM5Bar, ...]:
    return tuple(ClosedM5Bar(
        start_utc=(hour+timedelta(minutes=5*i)).isoformat(),
        open="1.10100", high="1.10200", low="1.10000",
        close="1.10150",
    ) for i in range(12))


def commit(d: FakeReadOnlyAuditStore, hour: datetime) -> None:
    r = commit_hour(
        d, now_utc=hour+timedelta(hours=1, minutes=10),
        observed=bars(hour),
    )
    assert r.status == "BATCH_COMMITTED"


class P050AuditTests(unittest.TestCase):
    def test_01_first_real_shape_audit_is_fresh(self) -> None:
        d = FakeReadOnlyAuditStore()
        commit(d, START)
        count = d.write_count
        r = audit_recent_cache(
            d, now_utc=START+timedelta(hours=1, minutes=35))
        self.assertEqual(r["status"], "FRESH_LAST_CLOSED_HOUR")
        self.assertEqual(r["manifest_count"], 1)
        self.assertEqual(r["chunk_count"], 1)
        self.assertEqual(r["total_closed_m5"], 12)
        self.assertTrue(r["full_history_audited"])
        self.assertEqual(d.write_count, count)
        self.assertEqual((r["twelve_data_api_calls"],r["broker_orders"]), (0,0))

    def test_02_two_consecutive_hours_are_sha_linked(self) -> None:
        d = FakeReadOnlyAuditStore()
        commit(d, START)
        commit(d, START+timedelta(hours=1))
        r = audit_recent_cache(
            d, now_utc=START+timedelta(hours=2, minutes=35))
        self.assertEqual(r["latest_continuity_status"],
                         "CONTIGUOUS_WITH_PRIOR_BATCH")
        self.assertEqual(r["audited_manifest_chunk_pairs"],2)
        self.assertEqual(r["total_closed_m5"],24)
        self.assertEqual(r["last_hour_lag"],0)

    def test_03_explicit_gap_kept_visible_without_fabrication(self) -> None:
        d = FakeReadOnlyAuditStore()
        commit(d, START)
        commit(d, START+timedelta(hours=3))
        r = audit_recent_cache(
            d, now_utc=START+timedelta(hours=4, minutes=35))
        self.assertEqual(r["latest_continuity_status"],
                         "MISSING_PRIOR_HOURS_UNVERIFIED")

    def test_04_corrupt_chunk_fails_closed(self) -> None:
        d = FakeReadOnlyAuditStore()
        commit(d, START)
        name = next(iter(d.objects["chunk"]))
        d.objects["chunk"][name]["bars"][0]["close"] = "1.99999"
        with self.assertRaisesRegex(ValueError,"SHA"):
            audit_recent_cache(
                d, now_utc=START+timedelta(hours=1, minutes=35))

    def test_05_corrupt_manifest_fails_closed(self) -> None:
        d = FakeReadOnlyAuditStore()
        commit(d, START)
        name = next(iter(d.objects["manifest"]))
        d.objects["manifest"][name]["chunk_sha256"] = "0"*64
        with self.assertRaises(ValueError):
            audit_recent_cache(
                d, now_utc=START+timedelta(hours=1, minutes=35))

    def test_06_missing_chunk_fails_closed(self) -> None:
        d = FakeReadOnlyAuditStore()
        commit(d, START)
        d.objects["chunk"].clear()
        with self.assertRaisesRegex(ValueError,"CHUNK_NOT_LISTED"):
            audit_recent_cache(
                d, now_utc=START+timedelta(hours=1, minutes=35))

    def test_07_duplicate_manifest_hour_fails_closed(self) -> None:
        d = FakeReadOnlyAuditStore()
        commit(d, START)
        n=next(iter(d.objects["manifest"]))
        d.objects["manifest"][n[:-5]+"a.json"] = copy.deepcopy(
            d.objects["manifest"][n])
        with self.assertRaisesRegex(ValueError,"DUPLICATE_OR_UNKNOWN"):
            audit_recent_cache(
                d, now_utc=START+timedelta(hours=1, minutes=35))

    def test_08_future_hour_fails_closed(self) -> None:
        d = FakeReadOnlyAuditStore()
        commit(d, START)
        with self.assertRaisesRegex(ValueError,"FUTURE_OR_UNALIGNED"):
            audit_recent_cache(d, now_utc=START+timedelta(minutes=35))

    def test_09_stale_snapshot_is_reported_not_mislabeled_fresh(self) -> None:
        d = FakeReadOnlyAuditStore()
        commit(d, START)
        r = audit_recent_cache(
            d, now_utc=START+timedelta(hours=3, minutes=35))
        self.assertEqual(r["status"],"LAGGING_OR_MARKET_CLOSED_NEEDS_REVIEW")
        self.assertEqual(r["last_hour_lag"],2)

    def test_10_utc_required(self) -> None:
        d = FakeReadOnlyAuditStore()
        with self.assertRaisesRegex(ValueError,"REQUIRES_UTC"):
            audit_recent_cache(d,now_utc=datetime(2026,11,10,20))

    def test_11_missing_manifest_denied(self) -> None:
        d = FakeReadOnlyAuditStore()
        with self.assertRaisesRegex(ValueError,"NO_SEALED_MANIFEST"):
            audit_recent_cache(d,now_utc=START)

    def test_12_long_history_uses_bounded_recent_window(self) -> None:
        d = FakeReadOnlyAuditStore()
        for offset in range(5):
            commit(d, START+timedelta(hours=offset))
        r = audit_recent_cache(
            d,now_utc=START+timedelta(hours=5,minutes=35))
        self.assertEqual(r["audited_manifest_chunk_pairs"],3)
        self.assertFalse(r["full_history_audited"])
        self.assertEqual(r["total_closed_m5"],60)

    def test_13_workflow_is_readonly_and_no_vendor_credentials(self) -> None:
        y=Path(".github/workflows/mfx-hourly-cache-audit.yml").read_text(
            encoding="utf-8")
        self.assertIn('cron: "35 * * * *"',y)
        self.assertIn("MFX_V2_BATCH_CACHE_ACCEPTED",y)
        self.assertIn("python -m tools.run_mfx_hourly_cache_audit",y)
        self.assertNotIn("MFX_TWELVE_DATA_API_KEY",y)
        self.assertNotIn("tools.run_a04_p46_cloud_batch_cache",y)


if __name__=="__main__":
    unittest.main()

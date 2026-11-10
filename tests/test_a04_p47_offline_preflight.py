"""P0.47 offline-only no-provider HOT/B1 read preflight acceptance tests."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any
import unittest

from mfx_cache.td_m5_codec import ClosedM5Bar, digest
from mfx_cache.v2_batch_commit import _make_plan
from mfx_cache.v3_hot_overlay import plan_hot
from mfx_cache.v3_offline_preflight import inspect_offline_hot_b1
from mfx_cache.v3_sealed_index import reconcile_sealed_index

UTC = timezone.utc
START = datetime(2026, 11, 10, 14, tzinfo=UTC)
NOW = START + timedelta(hours=2, minutes=10, seconds=30)


def candles(start: datetime, n: int) -> tuple[ClosedM5Bar, ...]:
    return tuple(
        ClosedM5Bar(
            start_utc=(start + timedelta(minutes=5 * k)).isoformat(),
            open="1.10000", high="1.20000",
            low="1.00000", close="1.15000",
        ) for k in range(n)
    )


class OfflineB1Store:
    def __init__(self) -> None:
        self.obj: dict[str, dict[str, dict[str, Any]]] = {
            "manifest": {}, "chunk": {},
        }
        self.reads = 0
        self.lists = 0
        self.writes = 0

    def list_names(self, bucket: str) -> tuple[str, ...]:
        self.lists += 1
        return tuple(sorted(self.obj[bucket]))

    def read(self, bucket: str, name: str) -> dict[str, Any]:
        self.reads += 1
        return deepcopy(self.obj[bucket][name])

    def put_if_absent(
        self, bucket: str, name: str, body: dict[str, Any],
    ) -> None:
        if name in self.obj[bucket]:
            raise ValueError("FIXTURE_IMMUTABLE_SOURCE_ALREADY_EXISTS")
        self.obj[bucket][name] = deepcopy(body)
        self.writes += 1

    def append_hour(self, hour: int) -> None:
        names = sorted(self.obj["manifest"])
        previous = self.obj["manifest"][names[-1]] if names else None
        start = START + timedelta(hours=hour)
        plan = _make_plan(
            previous, hour_utc=start.isoformat(),
            bars=candles(start, 12), now_utc=NOW,
        )
        self.put_if_absent("chunk", plan.chunk_name, plan.chunk)
        self.put_if_absent("manifest", plan.manifest_name, plan.manifest)


class OfflinePointer:
    def __init__(self) -> None:
        self.state: dict[str, Any] | None = None

    def load(self) -> dict[str, Any] | None:
        return deepcopy(self.state)

    def write(
        self, *, expected: dict[str, Any] | None,
        replacement: dict[str, Any],
    ) -> None:
        if self.state != expected:
            raise ValueError("FIXTURE_POINTER_CHANGED")
        self.state = deepcopy(replacement)


class P047OfflinePreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = OfflineB1Store()
        self.source.append_hour(0)
        self.source.append_hour(1)
        pointer = OfflinePointer()
        reconcile_sealed_index(self.source, pointer, now_utc=NOW)
        assert pointer.state is not None
        self.index = pointer.state
        recent = candles(START + timedelta(minutes=45), 16)
        result = plan_hot(None, recent, now_utc=NOW)
        assert result.new_state is not None
        self.hot = result.new_state

    def audit(self, *, at: datetime = NOW) -> Any:
        return inspect_offline_hot_b1(
            self.source, self.index, self.hot, now_utc=at,
        )

    def test_01_no_index_never_calls_source(self) -> None:
        before = (self.source.reads, self.source.lists, self.source.writes)
        result = inspect_offline_hot_b1(
            self.source, None, self.hot, now_utc=NOW,
        )
        self.assertEqual(result.status, "NO_SEALED_B1_INDEX")
        self.assertFalse(result.offline_research_usable)
        self.assertEqual(
            (self.source.reads, self.source.lists, self.source.writes), before,
        )

    def test_02_no_hot_never_calls_source(self) -> None:
        result = inspect_offline_hot_b1(
            self.source, self.index, None, now_utc=NOW,
        )
        self.assertEqual(result.status, "NO_HOT_OVERLAY")
        self.assertFalse(result.offline_research_usable)

    def test_03_fresh_closed_m5_b1_research_overlap(self) -> None:
        result = self.audit()
        self.assertEqual(
            result.status, "OFFLINE_ANCHORED_RESEARCH_ONLY_NO_LATESTNESS_PROOF",
        )
        self.assertEqual(result.verified_overlap_m5, 12)
        self.assertTrue(result.offline_research_usable)
        self.assertFalse(result.globally_latest_source_proven)

    def test_04_only_two_immutable_reads_no_list_or_write(self) -> None:
        before = (self.source.reads, self.source.lists, self.source.writes)
        self.audit()
        after = (self.source.reads, self.source.lists, self.source.writes)
        self.assertEqual(after, (before[0] + 2, before[1], before[2]))

    def test_05_stale_hourly_hot_is_fail_closed_without_io(self) -> None:
        before = self.source.reads
        result = self.audit(at=NOW + timedelta(minutes=12))
        self.assertEqual(result.status, "HOT_STALE_GAPPED_OR_INSUFFICIENT")
        self.assertFalse(result.offline_research_usable)
        self.assertEqual(self.source.reads, before)

    def test_06_fresh_but_unanchored_hot_never_promoted(self) -> None:
        later = NOW + timedelta(hours=7)
        observed = candles(START + timedelta(hours=7, minutes=45), 16)
        result = plan_hot(None, observed, now_utc=later)
        assert result.new_state is not None
        preflight = inspect_offline_hot_b1(
            self.source, self.index, result.new_state, now_utc=later,
        )
        self.assertEqual(preflight.status, "HOT_UNANCHORED_SEALED_B1")
        self.assertFalse(preflight.offline_research_usable)

    def test_07_hot_behind_indexed_b1_blocks_before_source_io(self) -> None:
        older = candles(START + timedelta(minutes=45), 9)
        result = plan_hot(None, older, now_utc=NOW)
        assert result.new_state is not None
        before = self.source.reads
        check = inspect_offline_hot_b1(
            self.source, self.index, result.new_state, now_utc=NOW,
        )
        self.assertEqual(check.status, "HOT_BEHIND_INDEXED_B1")
        self.assertFalse(check.offline_research_usable)
        self.assertEqual(self.source.reads, before)

    def test_08_gap_cannot_be_classed_as_usable_research(self) -> None:
        original = candles(START + timedelta(minutes=45), 16)
        candidate = original[:6] + original[7:]
        result = plan_hot(None, candidate, now_utc=NOW)
        assert result.new_state is not None
        preflight = inspect_offline_hot_b1(
            self.source, self.index, result.new_state, now_utc=NOW,
        )
        self.assertEqual(
            preflight.status, "HOT_STALE_GAPPED_OR_INSUFFICIENT",
        )
        self.assertFalse(preflight.offline_research_usable)

    def test_09_unknown_b1_continuity_not_self_approved(self) -> None:
        forged_index = deepcopy(self.index)
        forged_index["source_continuity_status"] = (
            "MISSING_PRIOR_HOURS_UNVERIFIED"
        )
        before = self.source.reads
        preflight = inspect_offline_hot_b1(
            self.source, forged_index, self.hot, now_utc=NOW,
        )
        self.assertEqual(
            preflight.status, "B1_SOURCE_CONTINUITY_UNVERIFIED",
        )
        self.assertEqual(self.source.reads, before)

    def test_10_missing_immutable_b1_chunk_raises(self) -> None:
        del self.source.obj["chunk"][self.index["chunk_name"]]
        with self.assertRaisesRegex(ValueError, "MISSING_SEALED_SOURCE"):
            self.audit()

    def test_11_sha_rewritten_hot_bar_still_conflicts_with_b1(self) -> None:
        forged_hot = deepcopy(self.hot)
        record = next(
            x for x in forged_hot["recent_bars"]
            if x["start_utc"] == (
                START + timedelta(hours=1, minutes=10)
            ).isoformat()
        )
        record["close"] = "1.16000"
        record["bar_sha256"] = digest({
            k: record[k] for k in ("start_utc", "open", "high", "low", "close")
        })
        forged_hot["recent_index_sha256"] = digest(
            forged_hot["recent_bars"]
        )
        with self.assertRaisesRegex(
            ValueError, "HOT_B1_IMMUTABLE_SOURCE_MISMATCH",
        ):
            inspect_offline_hot_b1(
                self.source, self.index, forged_hot, now_utc=NOW,
            )

    def test_12_invalid_utc_and_no_live_promotions(self) -> None:
        with self.assertRaisesRegex(ValueError, "EXACT_UTC_REQUIRED"):
            self.audit(at=NOW.replace(tzinfo=None))
        preflight = self.audit()
        self.assertFalse(preflight.source_numeric_buy_sell_authorized)
        self.assertFalse(preflight.broker_orders_authorized)
        self.assertEqual((preflight.vendor_requests, preflight.drive_writes),
                         (0, 0))

    def test_13_forged_market_approval_rejected(self) -> None:
        forged = deepcopy(self.hot)
        forged["approved_original_numeric_signals"] = True
        with self.assertRaisesRegex(
            ValueError, "PROVENANCE_OR_TRADE_PROMOTION",
        ):
            inspect_offline_hot_b1(
                self.source, self.index, forged, now_utc=NOW,
            )

    def test_14_receipt_is_deterministic_without_provider_calls(self) -> None:
        a = self.audit()
        b = self.audit()
        self.assertEqual(a, b)
        self.assertEqual(a.hot_age_seconds, 330)
        self.assertEqual(a.vendor_requests, 0)
        self.assertEqual(a.drive_writes, 0)

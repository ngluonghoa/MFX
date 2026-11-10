"""A04/P0.46-B3: synthetic HOT overlay and fake-Drive race/adverse tests."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import os
import unittest
from unittest.mock import patch
from typing import Any

from mfx_cache.td_m5_codec import ClosedM5Bar, digest
from mfx_cache.v3_hot_overlay import (
    MAX_HOT_CANDLES, HotFreshness, commit_hot, freshness, plan_hot,
    validate_hot,
)
from tools.run_a04_p46_b3_hot_cloud import main as cloud_main

UTC = timezone.utc
BASE = datetime(2026, 11, 10, 12, 10, tzinfo=UTC)
NOW = datetime(2026, 11, 10, 13, 30, 30, tzinfo=UTC)


def rows(n: int = 16, *, start: datetime = BASE) -> tuple[ClosedM5Bar,...]:
    return tuple(ClosedM5Bar(
        start_utc=(start+timedelta(minutes=i*5)).isoformat(),
        open="1.10000",high="1.20000",low="1.00000",
        close="1.15000",
    ) for i in range(n))


class FakeDriveHot:
    def __init__(self) -> None:
        self.state: dict[str,Any]|None=None
        self.creates=0
        self.updates=0
        self.reads=0
        self.fail_after_persist=False
        self.corrupt_read_after_write=False
        self.race_on_second_load=False

    def load(self)->dict[str,Any]|None:
        self.reads+=1
        if self.race_on_second_load and self.reads==2 and self.state:
            self.state["last_updated_utc"]="2026-11-10T13:30:31+00:00"
        obj=deepcopy(self.state)
        if self.corrupt_read_after_write and self.creates+self.updates:
            assert obj is not None
            obj["symbol"]="GBP/USD"
        return obj

    def write(self,*,expected:dict[str,Any]|None,
              replacement:dict[str,Any])->None:
        if self.state!=expected:
            raise ValueError("FAKE_NOT_ATOMIC_PREVIOUS_CHANGED")
        if self.state is None:
            self.creates+=1
        else:
            self.updates+=1
        self.state=deepcopy(replacement)
        if self.fail_after_persist:
            self.fail_after_persist=False
            raise OSError("FAKE_CRASH_AFTER_HOT_OBJECT_WRITE")


class P046B3HotTests(unittest.TestCase):
    def _initial(self)->dict[str,Any]:
        r=plan_hot(None,rows(),now_utc=NOW)
        assert r.new_state is not None
        return r.new_state

    def test_01_bootstrap_one_hot_state_and_bounded_16_rows(self)->None:
        r=plan_hot(None,rows(),now_utc=NOW)
        self.assertEqual(r.status,"NEW_CLOSED_M5_HOT_OVERLAY")
        self.assertEqual(r.new_closed_m5,16)
        self.assertEqual(r.expected_drive_object_creates,1)
        self.assertEqual(r.expected_drive_object_updates,0)
        assert r.new_state is not None
        self.assertEqual(len(r.new_state["recent_bars"]),16)

    def test_02_initial_state_has_explicit_mid_provenance(self)->None:
        m=self._initial()
        self.assertEqual(m["symbol"],"EUR/USD")
        self.assertEqual(m["provider"],"TWELVE_DATA_COMPOSITE_MID")
        self.assertEqual(m["side"],"MID")
        self.assertEqual(m["timezone"],"UTC")
        self.assertFalse(m["approved_original_numeric_signals"])
        self.assertFalse(m["source_revision_history_verified"])

    def test_03_fresh_read_is_research_only_not_trade(self)->None:
        q=freshness(self._initial(),now_utc=NOW)
        self.assertIsInstance(q,HotFreshness)
        self.assertEqual(q.status,"FRESH_RECENT_M5_RESEARCH_ONLY")
        self.assertTrue(q.research_data_usable)
        self.assertFalse(q.live_buy_sell_authorized)
        self.assertFalse(q.broker_orders_authorized)

    def test_04_stale_read_not_research_usable(self)->None:
        q=freshness(self._initial(),
                    now_utc=NOW+timedelta(seconds=400))
        self.assertEqual(q.status,"STALE_CLOSED_M5_NOT_FRESH")
        self.assertFalse(q.research_data_usable)

    def test_05_one_more_m5_appends_with_one_update(self)->None:
        prior=self._initial()
        nxt=rows(start=BASE+timedelta(minutes=5))
        r=plan_hot(prior,nxt,now_utc=NOW+timedelta(minutes=5))
        self.assertEqual(r.new_closed_m5,1)
        self.assertEqual(r.expected_drive_object_creates,0)
        self.assertEqual(r.expected_drive_object_updates,1)
        assert r.new_state is not None
        self.assertEqual(r.new_state["generation"],2)

    def test_06_unchanged_returns_no_drive_io(self)->None:
        r=plan_hot(self._initial(),rows(),now_utc=NOW+timedelta(seconds=20))
        self.assertEqual(r.status,"UNCHANGED_NO_DRIVE_WRITE")
        self.assertIsNone(r.new_state)
        self.assertEqual(r.expected_drive_object_updates,0)

    def test_07_historical_revision_quarantined(self)->None:
        previous=self._initial()
        changed=rows()
        changed=changed[:4]+(replace(changed[4],close="1.16000"),)+changed[5:]
        with self.assertRaisesRegex(ValueError,"REVISED_CLOSED_M5_QUARANTINE"):
            plan_hot(previous,changed,now_utc=NOW+timedelta(minutes=5))

    def test_08_historical_revision_even_without_new_bar_denied(self)->None:
        previous=self._initial()
        modified=(replace(rows()[0],low="0.95000"),)+rows()[1:]
        with self.assertRaisesRegex(ValueError,"REVISED_CLOSED_M5_QUARANTINE"):
            plan_hot(previous,modified,now_utc=NOW)

    def test_09_out_of_order_vendor_bars_denied(self)->None:
        b=rows()
        with self.assertRaisesRegex(ValueError,"DUPLICATE_OR_UNORDERED"):
            plan_hot(None,tuple(reversed(b)),now_utc=NOW)

    def test_10_duplicate_vendor_timestamp_denied(self)->None:
        b=rows()
        with self.assertRaisesRegex(ValueError,"DUPLICATE_OR_UNORDERED"):
            plan_hot(None,b+(b[-1],),now_utc=NOW)

    def test_11_future_and_open_candle_denied(self)->None:
        b=rows()
        late=replace(b[-1],start_utc=NOW.replace(second=0).isoformat())
        with self.assertRaisesRegex(ValueError,"P046_FUTURE_OPEN"):
            plan_hot(None,b[:-1]+(late,),now_utc=NOW)

    def test_12_naive_timestamp_denied(self)->None:
        b=rows()
        naive=replace(b[-1],start_utc="2026-11-10T13:25:00")
        with self.assertRaises(ValueError):
            plan_hot(None,b[:-1]+(naive,),now_utc=NOW)

    def test_13_wrong_utc_offset_denied(self)->None:
        b=rows()
        last=replace(b[-1],start_utc="2026-11-10T20:25:00+07:00")
        with self.assertRaises(ValueError):
            plan_hot(None,b[:-1]+(last,),now_utc=NOW)

    def test_14_invalid_ohlc_denied(self)->None:
        b=rows()
        altered=(replace(b[0],low="1.30"),)+b[1:]
        with self.assertRaisesRegex(ValueError,"INVALID_M5_OHLC"):
            plan_hot(None,altered,now_utc=NOW)

    def test_15_source_gap_marks_unverified_no_signal(self)->None:
        prev=self._initial()
        shifted=rows(start=BASE+timedelta(minutes=10))
        shifted=shifted[:14]+shifted[15:]  # omit 13:30, retain 13:35
        r=plan_hot(prev,shifted,now_utc=NOW+timedelta(minutes=10))
        assert r.new_state is not None
        self.assertTrue(r.new_state["source_gap_unverified"])
        self.assertEqual(freshness(
            r.new_state,now_utc=NOW+timedelta(minutes=10),
        ).status,"UNKNOWN_SOURCE_SESSION_OR_MISSING_M5")

    def test_16_ever_seen_gap_cannot_be_silently_cleared(self)->None:
        prior=self._initial()
        shifted=rows(start=BASE+timedelta(minutes=10))
        first=plan_hot(prior,shifted[:14]+shifted[15:],
                       now_utc=NOW+timedelta(minutes=10))
        assert first.new_state is not None
        s=first.new_state
        later=NOW+timedelta(minutes=10)
        for i in range(1,30):
            latest=datetime.fromisoformat(s["latest_closed_start_utc"])
            next_bar=ClosedM5Bar(
                start_utc=(latest+timedelta(minutes=5)).isoformat(),
                open="1.10000",high="1.20000",low="1.00000",
                close="1.15000",
            )
            known=tuple(ClosedM5Bar(
                start_utc=x["start_utc"],open=x["open"],high=x["high"],
                low=x["low"],close=x["close"],
            ) for x in s["recent_bars"][-14:])
            later=NOW+timedelta(minutes=10+5*i)
            r=plan_hot(s,known+(next_bar,),now_utc=later)
            assert r.new_state is not None
            s=r.new_state
        self.assertTrue(s["source_gap_unverified"])
        self.assertFalse(freshness(s,now_utc=later).research_data_usable)

    def test_17_window_is_capped_to_24_not_unbounded(self)->None:
        s=self._initial()
        for i in range(1,16):
            x=rows(start=BASE+timedelta(minutes=5*i))
            r=plan_hot(s,x,now_utc=NOW+timedelta(minutes=5*i))
            assert r.new_state is not None
            s=r.new_state
        self.assertEqual(len(s["recent_bars"]),MAX_HOT_CANDLES)

    def test_18_first_seen_timestamp_of_old_bars_kept(self)->None:
        s=self._initial()
        r=plan_hot(s,rows(start=BASE+timedelta(minutes=5)),
                   now_utc=NOW+timedelta(minutes=5))
        assert r.new_state is not None
        self.assertEqual(s["recent_bars"][1]["first_seen_utc"],
                         r.new_state["recent_bars"][1]["first_seen_utc"])

    def test_19_first_seen_of_new_close_is_actual_poll_time(self)->None:
        s=self._initial()
        later=NOW+timedelta(minutes=5)
        r=plan_hot(s,rows(start=BASE+timedelta(minutes=5)),
                   now_utc=later)
        assert r.new_state is not None
        self.assertEqual(r.new_state["recent_bars"][-1]["first_seen_utc"],
                         later.isoformat())

    def test_20_parent_hot_digest_and_generation(self)->None:
        prior=self._initial()
        r=plan_hot(prior,rows(start=BASE+timedelta(minutes=5)),
                   now_utc=NOW+timedelta(minutes=5))
        assert r.new_state is not None
        self.assertEqual(r.new_state["previous_hot_sha256"],digest(prior))
        self.assertEqual(r.new_state["generation"],2)

    def test_21_source_historical_input_without_overlap_denied(self)->None:
        prior=self._initial()
        newer=rows(start=BASE+timedelta(hours=10))
        with self.assertRaisesRegex(ValueError,"LOST_SOURCE_OVERLAP"):
            plan_hot(prior,newer,now_utc=NOW+timedelta(hours=10))

    def test_22_invalid_hot_schema_rejected(self)->None:
        prior=self._initial()
        prior["side"]="BID"
        with self.assertRaisesRegex(ValueError,"HOT_PROVENANCE"):
            validate_hot(prior,now_utc=NOW)

    def test_23_hot_sha_index_tamper_rejected(self)->None:
        prior=self._initial()
        prior["recent_index_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"HOT_WINDOW_INDEX_MISMATCH"):
            validate_hot(prior,now_utc=NOW)

    def test_24_hot_source_bar_digest_tamper_rejected(self)->None:
        prior=self._initial()
        prior["recent_bars"][0]["close"]="1.19000"
        with self.assertRaisesRegex(ValueError,"HOT_BAR_FINGERPRINT_CHANGED"):
            validate_hot(prior,now_utc=NOW)

    def test_25_hot_first_seen_cannot_predate_close(self)->None:
        prior=self._initial()
        prior["recent_bars"][0]["first_seen_utc"]=BASE.isoformat()
        with self.assertRaisesRegex(ValueError,"IMPOSSIBLE_FIRST_SEEN"):
            validate_hot(prior,now_utc=NOW)

    def test_26_future_hot_update_denied(self)->None:
        prior=self._initial()
        with self.assertRaisesRegex(ValueError,"FUTURE_OR_REVERSED"):
            validate_hot(prior,now_utc=NOW-timedelta(seconds=5))

    def test_27_malformed_generation_denied(self)->None:
        prior=self._initial()
        prior["generation"]=0
        with self.assertRaisesRegex(ValueError,"INVALID_HOT_GENERATION"):
            validate_hot(prior,now_utc=NOW)

    def test_28_root_hot_requires_no_previous_sha(self)->None:
        prior=self._initial()
        prior["previous_hot_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"GENERATION_PREDECESSOR_MISMATCH"):
            validate_hot(prior,now_utc=NOW)

    def test_29_24_plus_bars_does_not_authorize_real_signals(self)->None:
        s=self._initial()
        for i in range(1,12):
            r=plan_hot(s,rows(start=BASE+timedelta(minutes=5*i)),
                       now_utc=NOW+timedelta(minutes=5*i))
            assert r.new_state is not None
            s=r.new_state
        self.assertFalse(s["approved_original_numeric_signals"])
        self.assertFalse(freshness(
            s,now_utc=NOW+timedelta(minutes=55)).live_buy_sell_authorized)

    def test_30_fake_drive_boot_one_create_and_no_fragments(self)->None:
        store=FakeDriveHot()
        r=commit_hot(store,rows(),now_utc=NOW)
        self.assertEqual(r.new_closed_m5,16)
        self.assertEqual((store.creates,store.updates),(1,0))
        self.assertEqual(len(store.state["recent_bars"]),16)  # type: ignore[index]

    def test_31_fake_drive_next_m5_updates_same_file(self)->None:
        store=FakeDriveHot()
        commit_hot(store,rows(),now_utc=NOW)
        later=NOW+timedelta(minutes=5)
        commit_hot(store,rows(start=BASE+timedelta(minutes=5)),now_utc=later)
        self.assertEqual((store.creates,store.updates),(1,1))

    def test_32_fake_drive_unchanged_has_zero_writes(self)->None:
        store=FakeDriveHot()
        commit_hot(store,rows(),now_utc=NOW)
        commit_hot(store,rows(),now_utc=NOW+timedelta(seconds=20))
        self.assertEqual((store.creates,store.updates),(1,0))

    def test_33_fake_crash_after_write_retry_is_idempotent(self)->None:
        store=FakeDriveHot()
        store.fail_after_persist=True
        with self.assertRaisesRegex(OSError,"FAKE_CRASH_AFTER_HOT_OBJECT_WRITE"):
            commit_hot(store,rows(),now_utc=NOW)
        r=commit_hot(store,rows(),now_utc=NOW+timedelta(seconds=20))
        self.assertEqual(r.status,"UNCHANGED_NO_DRIVE_WRITE")
        self.assertEqual((store.creates,store.updates),(1,0))

    def test_34_race_between_plan_and_write_detected(self)->None:
        store=FakeDriveHot()
        commit_hot(store,rows(),now_utc=NOW)
        store.reads=0
        store.race_on_second_load=True
        with self.assertRaisesRegex(ValueError,"HOT_STATE_CHANGED_AFTER_PLAN"):
            commit_hot(store,rows(start=BASE+timedelta(minutes=5)),
                       now_utc=NOW+timedelta(minutes=5))

    def test_35_readback_tamper_detected(self)->None:
        store=FakeDriveHot()
        store.corrupt_read_after_write=True
        with self.assertRaisesRegex(ValueError,"HOT_FINAL_READBACK_MISMATCH"):
            commit_hot(store,rows(),now_utc=NOW)

    def test_36_non_utc_asof_denied(self)->None:
        with self.assertRaisesRegex(ValueError,"EXPLICIT_UTC_REQUIRED"):
            plan_hot(None,rows(),now_utc=NOW.astimezone(
                timezone(timedelta(hours=7))))

    def test_37_more_than_120_vendor_rows_denied(self)->None:
        many=rows(121,start=BASE-timedelta(hours=11))
        with self.assertRaisesRegex(ValueError,"BOUNDED_VENDOR_WINDOW"):
            plan_hot(None,many,now_utc=NOW)

    def test_38_untrusted_arbitrary_approval_field_denied(self)->None:
        state=self._initial()
        state["licensed_quote_retention_verified"]=True
        with self.assertRaisesRegex(ValueError,"HOT_PROVENANCE"):
            validate_hot(state,now_utc=NOW)

    def test_39_no_credentials_no_network_if_not_enabled(self)->None:
        with patch.dict(os.environ,{
            "MFX_REAL_CACHE_ENABLED":"false",
            "MFX_V3_HOT_CACHE_ACCEPTED":"false",
            "MFX_TD_ACCOUNT_CACHE_RIGHTS_CONFIRMED":"false",
        }):
            cloud_main()

    def test_40_no_elevation_on_one_or_two_bars(self)->None:
        r=plan_hot(None,rows(2),now_utc=BASE+timedelta(minutes=10,seconds=30))
        assert r.new_state is not None
        self.assertEqual(freshness(r.new_state,now_utc=BASE+timedelta(
            minutes=10,seconds=30)).status,"INSUFFICIENT_RECENT_M5")

    def test_41_same_slot_new_price_requires_review(self)->None:
        prior=self._initial()
        prior["last_updated_utc"]="2026-11-10T13:35:00+00:00"
        prior["last_poll_slot_utc"]="2026-11-10T13:35:00+00:00"
        with self.assertRaisesRegex(ValueError,"NEW_CLOSE_IN_ALREADY_PERSISTED_SLOT"):
            plan_hot(prior,rows(start=BASE+timedelta(minutes=5)),
                     now_utc=NOW+timedelta(minutes=5))

    def test_42_no_cross_project_or_forex_source_modification(self)->None:
        from pathlib import Path
        content=Path(".github/workflows/mfx-hot-cache.yml").read_text()
        self.assertIn("MFX_V3_HOT_CACHE_ACCEPTED",content)
        self.assertIn("MFX_TD_ACCOUNT_CACHE_RIGHTS_CONFIRMED",content)
        self.assertIn('cron: "*/5 * * * *"',content)
        self.assertIn("run_a04_p46_b3_hot_cloud",content)
        self.assertNotIn("MOCHI",content)


if __name__=="__main__":
    unittest.main()

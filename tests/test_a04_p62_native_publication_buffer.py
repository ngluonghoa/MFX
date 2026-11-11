"""A04/P0.62: source-native H4/D1 API publication readiness, DST and credits.

Conservative no-network schedule guards for Twelve Data REST candlestick
availability. These tests NEVER invoke provider API, Google Drive or broker.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from mfx_cache.native_fx_htf import (
    H4_CLOSE_GRACE, NativeFXBar, NativeFXBatch,
)
from mfx_cache.native_htf_archive import plan_native_sealed
from mfx_cache.native_htf_incremental import (
    SOURCE_PUBLICATION_BUFFER, plan_native_fetch,
)

UTC=timezone.utc


def stored(tf: str, labels: tuple[str,...]) -> dict[str,object]:
    axis="UTC_INTRADAY_OPEN" if tf=="4h" else "EXCHANGE_LOCAL_SESSION_DATE"
    batch=NativeFXBatch(
        symbol="EUR/USD",interval=tf,
        exchange_timezone="Australia/Sydney",time_reference=axis,
        incomplete_excluded=0,
        closed_bars=tuple(
            NativeFXBar(
                symbol="EUR/USD",interval=tf,
                native_open_label=label,time_reference=axis,
                exchange_timezone="Australia/Sydney",
                exchange_timezone_origin="DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT",
                open="1.1000",high="1.1040",low="1.0990",close="1.1030",
            )
            for label in labels),
    )
    sealed=plan_native_sealed(batch,previous=None)
    assert sealed is not None
    return sealed.manifest


def plan(tf: str, labels: tuple[str,...], t: datetime):
    return plan_native_fetch(interval=tf,previous=stored(tf,labels),now_utc=t)


class P062NativePublicationTests(unittest.TestCase):
    def test_01_buffer_is_greater_than_parser_minimum(self) -> None:
        self.assertEqual(SOURCE_PUBLICATION_BUFFER,timedelta(seconds=135))
        self.assertGreater(SOURCE_PUBLICATION_BUFFER,H4_CLOSE_GRACE)

    def test_02_h4_15_seconds_after_close_no_provider(self) -> None:
        p=plan("4h",("2026-11-11 00:00:00",),
               datetime(2026,11,11,8,0,16,tzinfo=UTC))
        self.assertIsNone(p.request)
        self.assertEqual(p.provider_requests_planned,0)

    def test_03_h4_2m14_before_buffer_no_provider(self) -> None:
        p=plan("4h",("2026-11-11 00:00:00",),
               datetime(2026,11,11,8,2,14,tzinfo=UTC))
        self.assertEqual(p.status,"NO_NEW_CLOSED_SLOT_NO_VENDOR_CALL")
        self.assertEqual(p.calendar_slots_behind,0)

    def test_04_h4_exact_buffer_boundary_one_provider(self) -> None:
        p=plan("4h",("2026-11-11 00:00:00",),
               datetime(2026,11,11,8,2,15,tzinfo=UTC))
        self.assertEqual(p.provider_requests_planned,1)
        self.assertEqual(p.calendar_slots_behind,1)
        self.assertEqual(p.latest_expected_closed_label,
                         "2026-11-11 04:00:00")
        self.assertEqual(p.request["outputsize"],"24")

    def test_05_h4_2m16_after_boundary_stays_due(self) -> None:
        p=plan("4h",("2026-11-11 00:00:00",),
               datetime(2026,11,11,8,2,16,tzinfo=UTC))
        self.assertEqual(p.provider_requests_planned,1)

    def test_06_h4_existing_newest_04_skips_after_buffer(self) -> None:
        p=plan("4h",("2026-11-11 04:00:00",),
               datetime(2026,11,11,8,2,16,tzinfo=UTC))
        self.assertEqual(p.provider_requests_planned,0)

    def test_07_d1_sydney_nov12_midnight_below_buffer_skips(self) -> None:
        # Nov 11 13:00:00 UTC = Nov 12 00:00:00 Sydney (AEDT UTC+11).
        p=plan("1day",("2026-11-10",),
               datetime(2026,11,11,13,2,14,tzinfo=UTC))
        self.assertEqual(p.latest_expected_closed_label,"2026-11-10")
        self.assertEqual(p.provider_requests_planned,0)

    def test_08_d1_sydney_nov12_midnight_at_buffer_due(self) -> None:
        p=plan("1day",("2026-11-10",),
               datetime(2026,11,11,13,2,15,tzinfo=UTC))
        self.assertEqual(p.latest_expected_closed_label,"2026-11-11")
        self.assertEqual(p.calendar_slots_behind,1)
        self.assertEqual(p.provider_requests_planned,1)
        self.assertNotIn("timezone",p.request)

    def test_09_d1_sydney_dst_spring_forward_midnight_local(self) -> None:
        # On Oct 4 Sydney transitions at 02:00, but at local midnight
        # it is still AEST (UTC+10). Never assume AEDT for the whole day.
        before=plan("1day",("2026-10-02",),
            datetime(2026,10,3,14,2,14,tzinfo=UTC))
        after=plan("1day",("2026-10-02",),
            datetime(2026,10,3,14,2,15,tzinfo=UTC))
        self.assertEqual(before.latest_expected_closed_label,"2026-10-02")
        self.assertEqual(after.latest_expected_closed_label,"2026-10-03")
        self.assertEqual(before.provider_requests_planned,0)
        self.assertEqual(after.provider_requests_planned,1)

    def test_10_d1_sydney_dst_fall_back_midnight_local(self) -> None:
        # On Apr 5 Sydney will fall back at 03:00, but at midnight
        # it is still AEDT (UTC+11).
        before=plan("1day",("2026-04-03",),
            datetime(2026,4,4,13,2,14,tzinfo=UTC))
        after=plan("1day",("2026-04-03",),
            datetime(2026,4,4,13,2,15,tzinfo=UTC))
        self.assertEqual(before.latest_expected_closed_label,"2026-04-03")
        self.assertEqual(after.latest_expected_closed_label,"2026-04-04")
        self.assertEqual(before.provider_requests_planned,0)
        self.assertEqual(after.provider_requests_planned,1)

    def test_11_both_timeframes_due_with_same_utc_clock(self) -> None:
        t=datetime(2026,11,11,13,2,15,tzinfo=UTC)
        h=plan("4h",("2026-11-11 00:00:00",),t)
        d=plan("1day",("2026-11-10",),t)
        self.assertEqual(h.provider_requests_planned,1)
        self.assertEqual(d.provider_requests_planned,1)
        self.assertEqual(h.latest_expected_closed_label,
                         "2026-11-11 08:00:00")
        self.assertEqual(d.latest_expected_closed_label,"2026-11-11")

    def test_12_no_h4_source_call_if_4h_candle_not_ready(self) -> None:
        t=datetime(2026,11,11,12,2,14,tzinfo=UTC)
        p=plan("4h",("2026-11-11 04:00:00",),t)
        self.assertEqual(p.provider_requests_planned,0)

    def test_13_no_synthetic_weekend_holiday_assumptions(self) -> None:
        # Vendor Forex API v2 documents 24/7 data. P062 only uses dates.
        # It must not silently skip a Saturday due to broker calendars.
        p=plan("4h",("2026-11-13 20:00:00",),
               datetime(2026,11,14,4,2,15,tzinfo=UTC))
        self.assertEqual(p.provider_requests_planned,1)
        self.assertEqual(p.latest_expected_closed_label,
                         "2026-11-14 00:00:00")

    def test_14_source_window_remains_bounded_120(self) -> None:
        p=plan("4h",("2026-11-10 00:00:00",),
               datetime(2026,11,11,12,2,15,tzinfo=UTC))
        self.assertLessEqual(int(p.request["outputsize"]),120)

    def test_15_unready_d1_still_exposes_no_vendor_request(self) -> None:
        p=plan("1day",("2026-11-10",),
               datetime(2026,11,11,13,1,tzinfo=UTC))
        self.assertIsNone(p.request)
        self.assertEqual(p.overlap_bar_count,1)

    def test_16_older_existing_d1_can_be_due_while_new_day_waits(self) -> None:
        # On Nov 12 00:02 local, Nov 11 is not assumed ready until 2:15,
        # but a lagged Nov 9 root must still fetch Nov 10.
        p=plan("1day",("2026-11-09",),
               datetime(2026,11,11,13,2,14,tzinfo=UTC))
        self.assertEqual(p.latest_expected_closed_label,"2026-11-10")
        self.assertEqual(p.calendar_slots_behind,1)
        self.assertEqual(p.provider_requests_planned,1)

    def test_17_hourly_plus_manual_incremental_workflow(self) -> None:
        y=Path(".github/workflows/mfx-native-htf-incremental-commit.yml").read_text()
        self.assertIn("workflow_dispatch:",y)
        self.assertIn('cron: "25 * * * *"',y)
        self.assertIn("MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED",y)

    def test_18_original_native_h4_parser_minimum_remains_15_seconds(self) -> None:
        self.assertEqual(H4_CLOSE_GRACE,timedelta(seconds=15))

    def test_19_parser_at_time_2m15_safety_not_fake_closed(self) -> None:
        # A H4 08:00 source candle itself is UNclosed at 08:02:15
        # and is never stored by the P052 parser.
        from mfx_cache.native_fx_htf import parse_native_forex
        data={"meta":{"symbol":"EUR/USD","interval":"4h","type":"Forex"},
              "values":[{"datetime":"2026-11-11 08:00:00",
                         "open":"1.1","high":"1.2","low":"1.0","close":"1.1"}]}
        got=parse_native_forex(
            data,symbol="EUR/USD",interval="4h",
            now_utc=datetime(2026,11,11,8,2,15,tzinfo=UTC),
            requested_timezone="UTC")
        self.assertEqual(len(got.closed_bars),0)
        self.assertEqual(got.incomplete_excluded,1)

    def test_20_timezone_naive_continues_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError,"REQUIRES_UTC"):
            plan_native_fetch(interval="1day",previous=None,
                              now_utc=datetime(2026,11,11,8,2,15))


if __name__ == "__main__":
    unittest.main()

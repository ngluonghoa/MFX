"""Signal-first 6TF read-only composition: M5/M15/M30/H1/native H4/D1."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from mfx_cache.native_fx_htf import parse_native_forex
from mfx_cache.td_m5_codec import ClosedM5Bar
from mfx_research.six_tf_readonly_context import (
    FRAMES, SixTimeframeResearchReceipt,
    build_six_timeframe_readonly_context,
)

UTC = timezone.utc
ASOF = datetime(2026, 11, 12, 12, 1, tzinfo=UTC)
START = datetime(2026, 11, 12, 11, tzinfo=UTC)


def m5(count=12, *, start=START):
    return tuple(ClosedM5Bar(
        start_utc=(start + timedelta(minutes=5*i)).isoformat(),
        open="1.1000", high="1.1010", low="1.0990",
        close="1.1005",
    ) for i in range(count))


def vendor(interval, labels):
    return {
        "status": "ok",
        "meta": {
            "symbol": "EUR/USD", "interval": interval,
            "type": "Physical Currency",
            "exchange_timezone": "Australia/Sydney",
        },
        "values": [{
            "datetime": stamp,
            "open": "1.1000", "high": "1.1020",
            "low": "1.0990", "close": "1.1010",
        } for stamp in labels],
    }


def h4(now=ASOF, labels=("2026-11-12 08:00:00",)):
    return parse_native_forex(
        vendor("4h", labels), symbol="EUR/USD", interval="4h",
        requested_timezone="UTC", now_utc=now,
    )


def d1(now=ASOF, labels=("2026-11-11",)):
    return parse_native_forex(
        vendor("1day", labels), symbol="EUR/USD", interval="1day",
        requested_timezone=None, now_utc=now,
    )


def build(bars=None, *, four=None, daily=None, now=ASOF):
    return build_six_timeframe_readonly_context(
        m5() if bars is None else bars,
        h4() if four is None else four,
        d1() if daily is None else daily, asof_utc=now,
    )


class SixTFSourceSliceTests(TestCase):
    def test_01_six_real_computed_timeframes(self):
        r=build()
        self.assertEqual(tuple(f.frame for f in r.frames),FRAMES)
        self.assertEqual(r.total_frames,6)
        self.assertTrue(r.research_technical_context_complete)

    def test_02_asof_latest_closed_m5(self):
        r=build()
        self.assertEqual(r.frames[0].source_label,
                         "2026-11-12T11:55:00+00:00")
        self.assertEqual(r.frames[0].end_utc,
                         "2026-11-12T12:00:00+00:00")

    def test_03_m15_3_m5_closed(self):
        r=build()
        self.assertEqual(r.frames[1].source_bar_count,3)
        self.assertEqual(r.frames[1].source_label,
                         "2026-11-12T11:45:00+00:00")

    def test_04_m30_6_m5_closed(self):
        self.assertEqual(build().frames[2].source_bar_count,6)

    def test_05_h1_12_m5_closed(self):
        self.assertEqual(build().frames[3].source_bar_count,12)

    def test_06_h4_remains_native(self):
        r=build()
        self.assertTrue(r.frames[4].native)
        self.assertEqual(r.frames[4].time_basis,"UTC_INTRADAY_OPEN")
        self.assertEqual(r.frames[4].end_utc,
                         "2026-11-12T12:00:00+00:00")

    def test_07_d1_exchange_local_not_midnight_utc(self):
        r=build()
        self.assertTrue(r.frames[5].native)
        self.assertEqual(r.frames[5].time_basis,
                         "EXCHANGE_LOCAL_SESSION_DATE")
        self.assertEqual(r.frames[5].source_label,"2026-11-11")
        self.assertIsNone(r.frames[5].end_utc)

    def test_08_public_action_never_buy_sell(self):
        r=build()
        self.assertEqual((r.action,r.stage),("NO_SIGNAL","UNVERIFIED"))
        self.assertFalse(r.may_publish_verified_buy_sell)

    def test_09_research_ready_not_release_ready(self):
        r=build()
        self.assertEqual(r.status,"SIX_TF_TECHNICAL_RESEARCH_READY_NO_SIGNAL")
        self.assertFalse(r.forex_1to1_numerical_parity_verified)
        self.assertFalse(r.entry_sl_tp_net_rr_approved)

    def test_10_no_vendor_broker_drive_side_effects(self):
        r=build()
        self.assertEqual((r.provider_requests,r.drive_market_cache_writes,
                          r.broker_orders),(0,0,0))
        self.assertFalse(r.may_trade)

    def test_11_no_actual_market_archive_authentication_claim(self):
        r=build()
        self.assertFalse(r.source_feed_subscription_verified)
        self.assertFalse(r.archive_sha_independently_verified)
        self.assertFalse(r.historical_asof_replay_proven)

    def test_12_native_not_derived_for_h4_d1(self):
        r=build()
        self.assertEqual(tuple(x.native for x in r.frames),
                         (True,False,False,False,True,True))

    def test_13_closed_m15_derived_ohlc(self):
        r=build()
        self.assertEqual((r.frames[1].open,r.frames[1].close),
                         ("1.1000","1.1005"))
        self.assertEqual((r.frames[1].high,r.frames[1].low),
                         ("1.1010","1.0990"))

    def test_14_stable_sha_for_identical_inputs(self):
        self.assertEqual(build().input_m5_sha256,
                         build().input_m5_sha256)

    def test_15_changed_m5_price_updates_fingerprint(self):
        b=list(m5())
        b[3]=replace(b[3],close="1.1008")
        self.assertNotEqual(build(tuple(b)).input_m5_sha256,
                            build().input_m5_sha256)

    def test_16_incomplete_last_m5_denies_latest_all_derived(self):
        r=build(m5()[:-1])
        self.assertFalse(r.research_technical_context_complete)
        self.assertEqual(r.missing_or_stale_frames,
                         ("M5","M15","M30","H1"))

    def test_17_interior_gap_denies_h1_but_can_keep_m15(self):
        b=m5()
        r=build(b[:1]+b[2:])
        self.assertIn("H1",r.missing_or_stale_frames)
        self.assertNotIn("M15",r.missing_or_stale_frames)
        self.assertEqual(r.action,"NO_SIGNAL")

    def test_18_insufficient_full_m5_history_blocks_h1(self):
        r=build(m5()[6:])
        self.assertIn("H1",r.missing_or_stale_frames)
        self.assertNotIn("M30",r.missing_or_stale_frames)

    def test_19_missing_native_h4_blocks_six_frame_ready(self):
        r=build(four=h4(labels=()))
        self.assertEqual(r.missing_or_stale_frames,("H4",))
        self.assertFalse(r.research_technical_context_complete)

    def test_20_missing_native_d1_blocks_six_frame_ready(self):
        r=build(daily=d1(labels=()))
        self.assertEqual(r.missing_or_stale_frames,("D1",))

    def test_21_old_native_h4_not_silent_rollforward(self):
        r=build(four=h4(labels=("2026-11-11 20:00:00",)))
        self.assertIn("H4",r.missing_or_stale_frames)

    def test_22_old_native_d1_not_silent_rollforward(self):
        r=build(daily=d1(labels=("2026-11-06",)))
        self.assertIn("D1",r.missing_or_stale_frames)

    def test_23_wrong_native_symbol_rejected(self):
        x=h4()
        with self.assertRaisesRegex(ValueError,"NATIVE_BATCH_SCOPE"):
            build(four=replace(x,symbol="GBP/USD"))

    def test_24_wrong_native_time_reference_rejected(self):
        with self.assertRaisesRegex(ValueError,"NATIVE_BATCH_SCOPE"):
            build(four=replace(h4(),time_reference="EXCHANGE_LOCAL_SESSION_DATE"))

    def test_25_sydney_timezone_missing_rejected(self):
        with self.assertRaisesRegex(ValueError,"NATIVE_BATCH_SCOPE"):
            build(daily=replace(d1(),exchange_timezone="UTC"))

    def test_26_h4_not_fabricated_by_m5(self):
        with self.assertRaisesRegex(ValueError,"NATIVE_BATCH_SCOPE"):
            build(four=replace(h4(),is_provider_native=False))

    def test_27_native_wrong_price_side_rejected(self):
        x=h4()
        b=replace(x.closed_bars[0],price_side="BID")
        with self.assertRaisesRegex(ValueError,"NATIVE_BAR_SCOPE"):
            build(four=replace(x,closed_bars=(b,)))

    def test_28_native_source_numeric_false_required(self):
        x=h4()
        b=replace(x.closed_bars[0],source_numeric_strategy_approved=True)
        with self.assertRaisesRegex(ValueError,"NATIVE_BAR_SCOPE"):
            build(four=replace(x,closed_bars=(b,)))

    def test_29_native_duplicate_h4_rejected(self):
        x=h4()
        with self.assertRaisesRegex(ValueError,"DUPLICATE_OR_UNSORTED"):
            build(four=replace(x,closed_bars=x.closed_bars*2))

    def test_30_native_future_h4_rejected(self):
        x=h4()
        b=replace(x.closed_bars[0],native_open_label="2026-11-12 12:00:00")
        with self.assertRaisesRegex(ValueError,"NATIVE_H4_OPEN_OR_FUTURE"):
            build(four=replace(x,closed_bars=(b,)))

    def test_31_native_misaligned_h4_rejected(self):
        x=h4()
        b=replace(x.closed_bars[0],native_open_label="2026-11-12 09:00:00")
        with self.assertRaisesRegex(ValueError,"NATIVE_H4_UTC_4H_GRID"):
            build(four=replace(x,closed_bars=(b,)))

    def test_32_native_current_local_d1_date_rejected(self):
        x=d1()
        b=replace(x.closed_bars[0],native_open_label="2026-11-12")
        with self.assertRaisesRegex(ValueError,"NATIVE_D1_LOCAL_DATE_NOT_CLOSED"):
            build(daily=replace(x,closed_bars=(b,)))

    def test_33_invalid_native_ohlc_rejected(self):
        x=h4()
        b=replace(x.closed_bars[0],low="1.9000")
        with self.assertRaisesRegex(ValueError,"NATIVE_OHLC_INVALID"):
            build(four=replace(x,closed_bars=(b,)))

    def test_34_naive_utc_asof_denied(self):
        with self.assertRaisesRegex(ValueError,"EXACT_UTC_ASOF"):
            build(now=datetime(2026,11,12,12,1))

    def test_35_non_utc_asof_denied(self):
        with self.assertRaisesRegex(ValueError,"EXACT_UTC_ASOF"):
            build(now=ASOF.astimezone(timezone(timedelta(hours=7))))

    def test_36_unsorted_m5_rejected(self):
        x=m5()
        with self.assertRaisesRegex(ValueError,"DUPLICATE_OR_UNORDERED"):
            build((x[1],x[0])+x[2:])

    def test_37_invalid_m5_price_rejected(self):
        x=list(m5())
        x[0]=replace(x[0],high="0.5")
        with self.assertRaisesRegex(ValueError,"INVALID_M5_OHLC"):
            build(tuple(x))

    def test_38_missing_native_batch_cannot_fake_empty_object(self):
        with self.assertRaisesRegex(ValueError,"NATIVE_BATCH_SCOPE"):
            build(four={})

    def test_39_no_invented_d1_utc_anchor(self):
        r=build()
        self.assertFalse(any("D1" in x.frame and x.end_utc is not None
                             for x in r.frames))

    def test_40_immutable_receipt_and_output(self):
        r=build()
        self.assertIsInstance(r,SixTimeframeResearchReceipt)
        with self.assertRaises(Exception):
            r.action="BUY"

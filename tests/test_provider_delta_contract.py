import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from forex_trading.cache_core import (
    CachePartition, CandleSnapshot, IncrementalPolicy, plan_incremental_refresh,
)
from forex_trading.market_data import BarSide, Timeframe
from forex_trading.provider_delta_contract import (
    SyntheticOandaRequest, parse_oanda_utc, plan_synthetic_oanda_delta,
    parse_synthetic_oanda_candles, diff_synthetic_delta,
)

UTC = timezone.utc
T = datetime(2026, 11, 7, 10, tzinfo=UTC)
M = timedelta(minutes=1)


def part(**kw):
    d = dict(provider_id="OANDA_SCHEMATIC_FIXTURE", broker_product_ref="SYNTH",
             instrument_version="EURUSD-synthetic-v1", side=BarSide.BID,
             timeframe=Timeframe.M5, calendar_version="TEST_CAL",
             aggregation_version="TEST_AGG", source_timezone_policy="UTC_TEST",
             rights_policy_ref="NOT_GRANTED", schema_version="CACHE_TEST")
    d.update(kw)
    return CachePartition(**d)


def req(**kw):
    d = dict(partition=part(), wire_instrument="EUR_USD",
             from_utc=T, to_utc=T + 15*M)
    d.update(kw)
    return SyntheticOandaRequest(**d)


def row(i=0, *, bid="1.10000", ask="1.10020", complete=True, volume=3):
    t = T + 5*i*M
    stamp = t.strftime("%Y-%m-%dT%H:%M:%S.000000000Z")
    return {
        "time": stamp, "complete": complete, "volume": volume,
        "bid": {"o": bid, "h": "1.11000", "l": "1.09000", "c": bid},
        "ask": {"o": ask, "h": "1.11020", "l": "1.09020", "c": ask},
    }


def payload(*rows):
    return {"instrument": "EUR_USD", "granularity": "M5",
            "candles": list(rows)}


def parse(*rows, request=None):
    return parse_synthetic_oanda_candles(payload(*rows),
                                        req() if request is None else request,
                                        T + 16*M)


class ProviderDeltaFixtureTests(unittest.TestCase):
    def test_oanda_timestamp_nanos_zero_are_exact(self):
        t=parse_oanda_utc("2026-11-07T10:00:00.000000000Z")
        self.assertEqual(t.utc,T)
        self.assertTrue(t.exact)

    def test_nanos_nonzero_not_rounded(self):
        t=parse_oanda_utc("2026-11-07T10:00:00.123456789Z")
        self.assertEqual(t.utc.microsecond,123456)
        self.assertEqual(t.nanosecond_remainder,789)
        self.assertFalse(t.exact)

    def test_non_utc_wall_time_and_invalid_dates_fail(self):
        for bad in ("2026-11-07T10:00:00+07:00",
                    "2026-11-07 10:00:00Z",
                    "2026-02-30T10:00:00Z",
                    "2026-11-07T10:00:00.1234567890Z",
                    "2026-11-07T10:00:00"):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                parse_oanda_utc(bad)

    def test_both_bid_ask_closed_candles_staged(self):
        x=parse(row(0),row(1))
        self.assertEqual(len(x.pairs),2)
        self.assertEqual(x.pairs[0].bid.side,BarSide.BID)
        self.assertEqual(x.pairs[0].ask.side,BarSide.ASK)
        self.assertEqual(x.pairs[0].bid.close,Decimal("1.10000"))
        self.assertEqual(x.pairs[0].ask.close,Decimal("1.10020"))
        self.assertNotEqual(x.pairs[0].bid.synthetic_record_digest,
                            x.pairs[0].ask.synthetic_record_digest)
        self.assertFalse(x.may_commit_real_cache)
        self.assertFalse(x.vendor_response_verified)
        self.assertFalse(x.provider_rights_verified)

    def test_oanda_fixture_not_broker_fill_even_with_bid_ask(self):
        x=parse(row())
        self.assertEqual(len(x.response_sha256_claim),64)
        self.assertFalse(x.may_commit_real_cache)

    def test_complete_false_is_provisional_not_cacheable(self):
        x=parse(row(0),row(1,complete=False))
        self.assertEqual(len(x.pairs),1)
        self.assertEqual(x.open_candle_count_skipped,1)

    def test_incomplete_row_without_quote_cannot_become_closed(self):
        incomplete={"time":row(1)["time"],"complete":False}
        x=parse(row(0),incomplete)
        self.assertEqual(len(x.pairs),1)
        self.assertEqual(x.open_candle_count_skipped,1)

    def test_ask_required_for_closed_bar(self):
        r=row()
        r.pop("ask")
        with self.assertRaisesRegex(ValueError,"BID_ASK_BOTH"):
            parse(r)

    def test_mid_only_rejected(self):
        r=row()
        r["mid"]=r.pop("bid")
        r.pop("ask")
        with self.assertRaisesRegex(ValueError,"BID_ASK_BOTH"):
            parse(r)

    def test_response_instrument_mismatch(self):
        with self.assertRaisesRegex(ValueError,"INSTRUMENT"):
            parse_synthetic_oanda_candles(
                {"instrument":"GBP_USD","granularity":"M5","candles":[row()]},
                req(),T+16*M)

    def test_response_timeframe_mismatch(self):
        with self.assertRaisesRegex(ValueError,"TIMEFRAME"):
            parse_synthetic_oanda_candles(
                {"instrument":"EUR_USD","granularity":"H4","candles":[row()]},
                req(),T+16*M)

    def test_no_unverified_D1_rollover_request(self):
        with self.assertRaisesRegex(ValueError,"DAILY_WEEKLY"):
            req(partition=part(timeframe=Timeframe.D1))

    def test_pair_request_requires_bid_base_partition(self):
        with self.assertRaisesRegex(ValueError,"BID_BASE"):
            req(partition=part(side=BarSide.ASK))

    def test_request_requires_both_components_no_smoothing(self):
        with self.assertRaisesRegex(ValueError,"LOSSY_OR_UNPAIRED"):
            req(wire_price="M")
        with self.assertRaisesRegex(ValueError,"LOSSY_OR_UNPAIRED"):
            req(smooth=True)
        with self.assertRaisesRegex(ValueError,"LOSSY_OR_UNPAIRED"):
            req(include_first=False)

    def test_no_unbounded_or_invalid_query_time(self):
        with self.assertRaisesRegex(ValueError,"EMPTY_OR_REVERSED"):
            req(to_utc=T)
        with self.assertRaises(ValueError):
            req(from_utc=datetime(2026,11,7,10))

    def test_bounded_delta_plan_refuses_network_even_valid(self):
        # Synthetic placeholder RefreshPlan: no real cache or network call.
        from forex_trading.cache_core import RefreshPlan, RefreshMode
        f=RefreshPlan(RefreshMode.DELTA_WINDOW,T,"snapshot-hash",False,False,"delta")
        result=plan_synthetic_oanda_delta(f,part(),"EUR_USD",T+15*M)
        self.assertIsNotNone(result.request)
        self.assertEqual(result.request.wire_price,"BA")
        self.assertEqual(result.request.from_utc,T)
        self.assertFalse(result.may_issue_network_call)
        self.assertFalse(result.may_store_real_data)

    def test_missing_delta_window_does_not_fallback_to_history(self):
        from forex_trading.cache_core import RefreshPlan, RefreshMode
        f=RefreshPlan(RefreshMode.RANGE_ENDPOINT_REQUIRED,None,"sha",False,False,"blocked")
        result=plan_synthetic_oanda_delta(f,part(),"EUR_USD",T+15*M)
        self.assertIsNone(result.request)
        self.assertFalse(result.may_issue_network_call)

    def test_no_more_closed_candles_refuses_query(self):
        from forex_trading.cache_core import RefreshPlan, RefreshMode
        f=RefreshPlan(RefreshMode.DELTA_WINDOW,T+15*M,"sha",False,False,"stale")
        result=plan_synthetic_oanda_delta(f,part(),"EUR_USD",T+15*M)
        self.assertIsNone(result.request)

    def test_future_completed_candle_rejected(self):
        with self.assertRaisesRegex(ValueError,"COMPLETE_BEFORE"):
            parse(row(2),request=req(to_utc=T+11*M))

    def test_outside_requested_from_to_rejected(self):
        with self.assertRaisesRegex(ValueError,"OUTSIDE_BOUNDED"):
            parse(row(0),request=req(from_utc=T+1*M))

    def test_unordered_and_duplicate_candle_time_rejected(self):
        with self.assertRaisesRegex(ValueError,"UNSORTED"):
            parse(row(1),row(0))
        with self.assertRaisesRegex(ValueError,"UNSORTED"):
            parse(row(0),row(0))

    def test_precision_loss_rejected(self):
        r=row()
        r["time"]="2026-11-07T10:00:00.000000001Z"
        with self.assertRaisesRegex(ValueError,"SUBMICROSECOND"):
            parse(r)

    def test_invalid_complete_and_volume(self):
        for invalid in (None,1,"true"):
            r=row()
            r["complete"]=invalid
            with self.subTest(invalid=invalid),self.assertRaisesRegex(ValueError,"COMPLETE_FLAG"):
                parse(r)
        for invalid in (True,-1,1.5,"3"):
            r=row()
            r["volume"]=invalid
            with self.subTest(volume=invalid),self.assertRaisesRegex(ValueError,"PRICE_COUNT"):
                parse(r)

    def test_bad_price_and_nan_rejected(self):
        for invalid in ("NaN", "-1", 1.5, "0", ""):
            r=row()
            r["bid"]["o"]=invalid
            with self.subTest(value=invalid),self.assertRaises(ValueError):
                parse(r)

    def test_price_ohlc_inconsistency_rejected(self):
        r=row()
        r["bid"]["h"]="1.0000"
        with self.assertRaisesRegex(ValueError,"INCONSISTENT"):
            parse(r)

    def test_max_page_guard(self):
        with self.assertRaisesRegex(ValueError,"PAGE_SIZE"):
            parse_synthetic_oanda_candles(payload(row(0),row(1)),req(),T+16*M,max_rows=1)

    def test_empty_response_not_proof_market_closed(self):
        x=parse()
        self.assertEqual(x.pairs,())
        self.assertFalse(x.vendor_response_verified)

    def test_repeated_overlap_yields_no_dirty_or_new_bars(self):
        old=parse(row(0),row(1))
        new=parse(row(0),row(1))
        d=diff_synthetic_delta(old.pairs,new)
        self.assertEqual((d.appended,d.corrected,d.unchanged),(0,0,2))
        self.assertIsNone(d.first_dirty_utc)
        self.assertFalse(d.may_persist_real_prices)

    def test_changed_bid_old_candle_detected(self):
        old=parse(row(0),row(1))
        now=parse(row(0,bid="1.10050"),row(1))
        d=diff_synthetic_delta(old.pairs,now)
        self.assertEqual((d.appended,d.corrected,d.unchanged),(0,1,1))
        self.assertEqual(d.first_dirty_utc,T)

    def test_changed_ask_old_candle_detected(self):
        old=parse(row(0),row(1))
        now=parse(row(0),row(1,ask="1.10050"))
        d=diff_synthetic_delta(old.pairs,now)
        self.assertEqual(d.corrected,1)
        self.assertEqual(d.first_dirty_utc,T+5*M)

    def test_append_only_detected(self):
        old=parse(row(0))
        now=parse(row(0),row(1))
        d=diff_synthetic_delta(old.pairs,now)
        self.assertEqual((d.appended,d.corrected,d.unchanged),(1,0,1))
        self.assertEqual(d.first_dirty_utc,T+5*M)

    def test_missing_old_not_automatically_deleted(self):
        old=parse(row(0),row(1))
        now=parse(row(1))
        d=diff_synthetic_delta(old.pairs,now)
        self.assertEqual(d.corrected,0)
        self.assertEqual(d.appended,0)
        self.assertTrue(d.missing_previous_rows_not_deleted)

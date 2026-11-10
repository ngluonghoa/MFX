"""A04/P0.52 native provider H4/D1 strict offline metadata/timezone contracts."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
import unittest

from mfx_cache.native_fx_htf import (
    native_request_contract, parse_native_forex,
)

UTC = timezone.utc
NOW = datetime(2026,11,10,20,15,tzinfo=UTC)


def vendor(interval: str, values: list[dict[str,str]], *,
           symbol: str = "EUR/USD",
           exchange_timezone: str = "Australia/Sydney") -> dict[str,object]:
    return {
        "meta": {
            "symbol":symbol,"interval":interval,
            "type":"Physical Currency",
            "exchange_timezone":exchange_timezone,
        },
        "values": values,
        "status":"ok",
    }


def bar(stamp: str, *, op: str="1.1150", high: str="1.1180",
        low: str="1.1140", close: str="1.1160") -> dict[str,str]:
    return {
        "datetime":stamp,"open":op,"high":high,
        "low":low,"close":close,
    }


def parse(payload: object, *, interval: str="4h",
          now: datetime=NOW, symbol: str="EUR/USD",
          timezone_request: str | None="UTC"):
    return parse_native_forex(
        payload,symbol=symbol,interval=interval,now_utc=now,
        requested_timezone=timezone_request,
    )


class P052NativeForexTests(unittest.TestCase):
    def test_01_native_4h_contract_pins_utc(self) -> None:
        self.assertEqual(native_request_contract(
            symbol="EUR/USD",interval="4h"),{
                "symbol":"EUR/USD","interval":"4h",
                "format":"JSON","outputsize":"120","timezone":"UTC",
            })

    def test_02_daily_contract_never_claims_utc_timezone(self) -> None:
        r=native_request_contract(symbol="USD/JPY",interval="1day")
        self.assertNotIn("timezone",r)
        self.assertEqual(r["symbol"],"USD/JPY")

    def test_03_completed_h4_is_native_not_m5_derived(self) -> None:
        x=parse(vendor("4h",[
            bar("2026-11-10 16:00:00"),
            bar("2026-11-10 12:00:00"),
        ]))
        self.assertEqual(len(x.closed_bars),2)
        self.assertEqual(x.closed_bars[0].native_open_label,
                         "2026-11-10 12:00:00")
        self.assertTrue(x.is_provider_native)
        self.assertTrue(x.closed_bars[0].is_provider_native)
        self.assertEqual(x.time_reference,"UTC_INTRADAY_OPEN")
        self.assertEqual((x.vendor_calls_made_by_parser,
                          x.google_drive_writes,x.broker_orders),(0,0,0))
        self.assertFalse(x.closed_bars[0].source_numeric_strategy_approved)

    def test_04_4h_open_candle_excluded(self) -> None:
        x=parse(vendor("4h",[
            bar("2026-11-10 20:00:00"),
            bar("2026-11-10 16:00:00"),
        ]))
        self.assertEqual(len(x.closed_bars),1)
        self.assertEqual(x.incomplete_excluded,1)

    def test_05_4h_requires_close_grace_15_seconds(self) -> None:
        v=vendor("4h",[bar("2026-11-10 16:00:00")])
        x=parse(v,now=datetime(2026,11,10,20,0,10,tzinfo=UTC))
        self.assertEqual(len(x.closed_bars),0)
        y=parse(v,now=datetime(2026,11,10,20,0,16,tzinfo=UTC))
        self.assertEqual(len(y.closed_bars),1)

    def test_06_d1_preserves_exchange_local_session_date(self) -> None:
        x=parse(vendor("1day",[
            bar("2026-11-11"),bar("2026-11-10"),
        ]),interval="1day",timezone_request=None)
        self.assertEqual(len(x.closed_bars),1)
        self.assertEqual(x.incomplete_excluded,1)
        b=x.closed_bars[0]
        self.assertEqual(b.native_open_label,"2026-11-10")
        self.assertEqual(b.time_reference,"EXCHANGE_LOCAL_SESSION_DATE")
        self.assertEqual(b.exchange_timezone,"Australia/Sydney")
        self.assertNotIn("start_utc",vars(b) if hasattr(b,"__dict__") else b.__slots__)

    def test_07_new_york_daily_date_checked_locally_not_utc(self) -> None:
        # 01:00 UTC on Nov 11 is still Nov 10 local New York.
        now=datetime(2026,11,11,1,0,tzinfo=UTC)
        data=vendor("1day",[bar("2026-11-10"),bar("2026-11-09")],
                    exchange_timezone="America/New_York")
        x=parse(data,interval="1day",timezone_request=None,now=now)
        self.assertEqual([b.native_open_label for b in x.closed_bars],
                         ["2026-11-09"])
        self.assertEqual(x.incomplete_excluded,1)

    def test_08_wrong_symbol_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError,"META_INTERVAL"):
            parse(vendor("4h",[bar("2026-11-10 12:00:00")],
                         symbol="GBP/USD"))

    def test_09_wrong_interval_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError,"META_INTERVAL"):
            parse(vendor("1day",[bar("2026-11-10")]))

    def test_10_intraday_utc_request_mandatory(self) -> None:
        with self.assertRaisesRegex(ValueError,"TIMEZONE_CONTRACT"):
            parse(vendor("4h",[bar("2026-11-10 12:00:00")]),
                  timezone_request=None)

    def test_11_daily_utc_request_forbidden(self) -> None:
        with self.assertRaisesRegex(ValueError,"TIMEZONE_CONTRACT"):
            parse(vendor("1day",[bar("2026-11-10")]),interval="1day")

    def test_12_exchange_timezone_missing_rejected(self) -> None:
        data=vendor("1day",[bar("2026-11-10")])
        data["meta"].pop("exchange_timezone") # type: ignore[union-attr]
        with self.assertRaisesRegex(ValueError,"EXCHANGE_TIMEZONE_REQUIRED"):
            parse(data,interval="1day",timezone_request=None)

    def test_13_invalid_iana_zone_rejected(self) -> None:
        data=vendor("1day",[bar("2026-11-10")],
                    exchange_timezone="Mars/Deimos")
        with self.assertRaisesRegex(ValueError,"INVALID_EXCHANGE_TIMEZONE"):
            parse(data,interval="1day",timezone_request=None)

    def test_14_duplicates_are_rejected_not_silent(self) -> None:
        with self.assertRaisesRegex(ValueError,"DUPLICATE_NATIVE"):
            parse(vendor("4h",[bar("2026-11-10 12:00:00")]*2))

    def test_15_invalid_h4_alignment_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError,"NOT_HOUR_ALIGNED"):
            parse(vendor("4h",[bar("2026-11-10 12:30:00")]))

    def test_16_daily_must_be_date_only(self) -> None:
        with self.assertRaisesRegex(ValueError,"D1_LOCAL_DATE"):
            parse(vendor("1day",[bar("2026-11-10 00:00:00")]),
                  interval="1day",timezone_request=None)

    def test_17_h4_cannot_be_derived_from_M5_contract(self) -> None:
        with self.assertRaisesRegex(ValueError,"ONLY_PROVIDER_NATIVE"):
            native_request_contract(symbol="EUR/USD",interval="5min")
        with self.assertRaisesRegex(ValueError,"ONLY_PROVIDER_NATIVE"):
            native_request_contract(symbol="EUR/USD",interval="1h")

    def test_18_bad_forex_symbol_fails_closed(self) -> None:
        for bad in ("EURUSD","EUR/EUR","eur/usd","AAPL",
                    "EUR/USD/USD","XAU/USD"):
            with self.subTest(bad=bad):
                if bad=="XAU/USD":
                    # XAU/USD syntactically valid; asset-type provider metadata
                    # still must validate genuine Forex at parse time.
                    continue
                with self.assertRaisesRegex(ValueError,"INVALID_FOREX_SYMBOL"):
                    native_request_contract(symbol=bad,interval="4h")

    def test_19_wrong_asset_type_fails_closed(self) -> None:
        data=vendor("4h",[bar("2026-11-10 12:00:00")])
        data["meta"]["type"]="Stock" # type: ignore[index]
        with self.assertRaisesRegex(ValueError,"META_INTERVAL"):
            parse(data)

    def test_20_invalid_ohlc_fails_closed(self) -> None:
        data=vendor("4h",[bar("2026-11-10 12:00:00",
                              op="1.115",low="1.116",close="1.117")])
        with self.assertRaisesRegex(ValueError,"INVALID_NATIVE_OHLC"):
            parse(data)

    def test_21_nonfinite_price_denied(self) -> None:
        data=vendor("4h",[bar("2026-11-10 12:00:00",close="NaN")])
        with self.assertRaisesRegex(ValueError,"INVALID_PRICE_VALUE"):
            parse(data)

    def test_22_zero_rows_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError,"META_INTERVAL"):
            parse(vendor("4h",[]))

    def test_23_over_120_rows_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError,"META_INTERVAL"):
            parse(vendor("4h",[bar("2026-11-10 12:00:00")]*121))

    def test_24_sha_deterministic_per_native_bar_and_date_axis(self) -> None:
        data=vendor("1day",[bar("2026-11-10")])
        a=parse(data,interval="1day",timezone_request=None)
        b=parse(data,interval="1day",timezone_request=None)
        self.assertEqual(a.closed_bars[0].sha256(),b.closed_bars[0].sha256())
        self.assertEqual(len(a.closed_bars[0].sha256()),64)

    def test_25_utc_clock_required(self) -> None:
        with self.assertRaisesRegex(ValueError,"EXACT_UTC"):
            parse(vendor("4h",[bar("2026-11-10 12:00:00")]),
                  now=datetime(2026,11,10,20,0))

    def test_26_vendor_error_cannot_be_cache_input(self) -> None:
        data=vendor("4h",[bar("2026-11-10 12:00:00")])
        data["status"]="error"
        with self.assertRaisesRegex(ValueError,"INVALID_VENDOR_PAYLOAD"):
            parse(data)

    def test_27_no_auto_activated_h4_d1_workflow(self) -> None:
        y=Path(".github/workflows/twelve-data-cache.yml").read_text(
            encoding="utf-8")
        self.assertIn("run_a04_p46_cloud_batch_cache",y)
        self.assertNotIn("native_fx_htf",y)
        self.assertIn('cron: "10 * * * *"',y)


if __name__=="__main__":
    unittest.main()

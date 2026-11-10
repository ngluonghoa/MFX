"""A04/P0.53 offline security/quota + native proof manual-only regression."""
from __future__ import annotations

from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import patch, Mock
from contextlib import redirect_stdout
import os
import unittest

from mfx_cache.native_fx_htf import parse_native_forex
from tools.run_mfx_native_htf_probe import (
    SYMBOL, INTERVALS, _probe_one, _read_payload, main,
    plan_probe_quota,
)

NOW = datetime(2026,11,10,20,15,tzinfo=timezone.utc)
OHLC = {
    "open":"1.115","high":"1.118",
    "low":"1.114","close":"1.117",
}


def response(interval: str) -> dict:
    return {
        "meta": {
            "symbol":"EUR/USD","interval":interval,
            "type":"Physical Currency",
            "exchange_timezone":"Australia/Sydney",
        },
        "values":[{
            "datetime": "2026-11-10 12:00:00"
                        if interval=="4h" else "2026-11-09",
            **OHLC,
        }],
        "status":"ok",
    }


class P053NativeManualProofTests(unittest.TestCase):
    def test_01_quota_two_price_requests_fit_8_limit(self) -> None:
        self.assertTrue(plan_probe_quota(1,8,400))

    def test_02_quota_two_price_requests_rejected_near_limit(self) -> None:
        self.assertFalse(plan_probe_quota(6,8,400))
        self.assertFalse(plan_probe_quota(7,8,400))

    def test_03_local_credit_cap_does_not_get_exceeded(self) -> None:
        self.assertFalse(plan_probe_quota(399,800,400))
        self.assertTrue(plan_probe_quota(395,800,400))

    def test_04_wrong_quota_types_fail_closed(self) -> None:
        for bad in ((True,8,400),(1,0,400),(-1,8,400)):
            with self.subTest(value=bad):
                with self.assertRaisesRegex(ValueError,"USAGE_INVALID"):
                    plan_probe_quota(*bad)

    def test_05_h4_http_request_has_explicit_utc(self) -> None:
        with patch("tools.run_mfx_native_htf_probe._read_payload",
                   return_value=response("4h")) as getter:
            r = _probe_one("not-secret","4h",now_utc=NOW)
        p=getter.call_args.args[1]
        self.assertEqual(p["interval"],"4h")
        self.assertEqual(p["timezone"],"UTC")
        self.assertEqual(p["apikey"],"not-secret")
        self.assertEqual(r.time_reference,"UTC_INTRADAY_OPEN")
        self.assertEqual(len(r.closed_bars),1)

    def test_06_daily_http_request_omits_ignored_timezone(self) -> None:
        with patch("tools.run_mfx_native_htf_probe._read_payload",
                   return_value=response("1day")) as getter:
            r = _probe_one("not-secret","1day",now_utc=NOW)
        p=getter.call_args.args[1]
        self.assertNotIn("timezone",p)
        self.assertEqual(p["interval"],"1day")
        self.assertEqual(r.time_reference,"EXCHANGE_LOCAL_SESSION_DATE")
        self.assertEqual(r.closed_bars[0].native_open_label,"2026-11-09")

    def test_07_no_closed_candles_fails_closed(self) -> None:
        empty=response("4h")
        empty["values"][0]["datetime"]="2026-11-10 20:00:00"
        with patch("tools.run_mfx_native_htf_probe._read_payload",
                   return_value=empty):
            with self.assertRaisesRegex(ValueError,"NO_CLOSED_NATIVE_ROWS"):
                _probe_one("fake","4h",now_utc=NOW)

    def test_08_vendor_error_never_exposes_api_key(self) -> None:
        # Host CI has no requests package; emulate its import fully offline.
        from types import SimpleNamespace
        import sys

        class FakeRequestException(Exception):
            pass

        mocked_requests = SimpleNamespace(
            RequestException=FakeRequestException,
            get=Mock(side_effect=FakeRequestException(
                "https://api.twelvedata.com/time_series?apikey=SECRET")),
        )
        with patch.dict(sys.modules, {"requests": mocked_requests}):
            with self.assertRaises(ValueError) as ctx:
                _read_payload(
                    "https://api.twelvedata.com/time_series",
                    {"apikey":"SECRET"},
                )
        self.assertNotIn("SECRET",str(ctx.exception))
        self.assertEqual(str(ctx.exception),
                         "P053_VENDOR_RESPONSE_UNAVAILABLE")

    def test_09_vendor_error_payload_rejected_silently(self) -> None:
        from types import SimpleNamespace
        import sys

        http=Mock()
        http.status_code=200
        http.json.return_value={"status":"error",
                                "message":"private-key-could-leak"}
        mocked_requests=SimpleNamespace(
            RequestException=OSError, get=Mock(return_value=http),
        )
        with patch.dict(sys.modules, {"requests": mocked_requests}):
            with self.assertRaisesRegex(ValueError,"VENDOR_ERROR_OR_INVALID"):
                _read_payload("https://example.invalid",{"apikey":"SECRET"})

    def test_10_main_gate_missing_never_calls_vendor(self) -> None:
        with patch.dict(os.environ,{
            "MFX_REAL_CACHE_ENABLED":"false",
            "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
        }),patch("tools.run_mfx_native_htf_probe._usage") as usage:
            out=StringIO()
            with redirect_stdout(out):
                main()
        usage.assert_not_called()
        self.assertIn("DISABLED_EXISTING_CACHE_GATES",out.getvalue())

    def test_11_main_insufficient_quota_never_calls_price(self) -> None:
        with patch.dict(os.environ,{
            "MFX_REAL_CACHE_ENABLED":"true",
            "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
            "MFX_TWELVE_DATA_API_KEY":"fake",
        }),patch("tools.run_mfx_native_htf_probe._usage",
                 return_value=(6,8)),patch(
                 "tools.run_mfx_native_htf_probe._probe_one") as probe:
            out=StringIO()
            with redirect_stdout(out):
                main()
        probe.assert_not_called()
        self.assertIn("NO_PRICE_REQUESTS",out.getvalue())
        self.assertIn('"price_requests": 0',out.getvalue())

    def test_12_success_prints_only_masked_source_receipt(self) -> None:
        a=parse_native_forex(response("4h"),symbol=SYMBOL,
                            interval="4h",now_utc=NOW,
                            requested_timezone="UTC")
        b=parse_native_forex(response("1day"),symbol=SYMBOL,
                            interval="1day",now_utc=NOW,
                            requested_timezone=None)
        with patch.dict(os.environ,{
            "MFX_REAL_CACHE_ENABLED":"true",
            "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
            "MFX_TWELVE_DATA_API_KEY":"TOPSECRET",
        }),patch("tools.run_mfx_native_htf_probe._usage",
                 side_effect=[(1,8),(2,8)]),patch(
                 "tools.run_mfx_native_htf_probe._probe_one",
                 side_effect=[a,b]) as probe:
            out=StringIO()
            with redirect_stdout(out):
                main()
        s=out.getvalue()
        self.assertIn("METADATA_ONLY_TWO_REQUESTS_PASS",s)
        self.assertIn("EXCHANGE_LOCAL_SESSION_DATE",s)
        self.assertIn('"private_drive_writes": 0',s)
        self.assertNotIn("TOPSECRET",s)
        self.assertNotIn("1.115",s)
        self.assertEqual(probe.call_count,2)

    def test_13_second_provider_quota_check_fails_closed(self) -> None:
        a=parse_native_forex(response("4h"),symbol=SYMBOL,
                            interval="4h",now_utc=NOW,
                            requested_timezone="UTC")
        with patch.dict(os.environ,{
            "MFX_REAL_CACHE_ENABLED":"true",
            "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
            "MFX_TWELVE_DATA_API_KEY":"fake",
        }),patch("tools.run_mfx_native_htf_probe._usage",
                 side_effect=[(1,8),(7,8)]),patch(
                 "tools.run_mfx_native_htf_probe._probe_one",
                 return_value=a) as probe:
            with self.assertRaisesRegex(ValueError,"SECOND_NATIVE_REQUEST"):
                main()
        self.assertEqual(probe.call_count,1)

    def test_14_workflow_is_dispatch_only_and_has_no_drive_access(self) -> None:
        y=Path(".github/workflows/mfx-native-htf-manual-probe.yml").read_text(
            encoding="utf-8")
        self.assertIn("workflow_dispatch:",y)
        self.assertNotIn("schedule:",y)
        self.assertNotIn("MFX_GDRIVE",y)
        self.assertNotIn("MFX_CACHE_CHUNK_FOLDER_ID",y)
        self.assertIn("mfx-twelvedata-private-cache",y)
        self.assertIn("python -m tools.run_mfx_native_htf_probe",y)
        self.assertIn("MFX_TWELVE_DATA_API_KEY",y)

    def test_15_pair_scope_only_eurusd_until_separate_activation(self) -> None:
        self.assertEqual(SYMBOL,"EUR/USD")
        self.assertEqual(INTERVALS,("4h","1day"))


if __name__ == "__main__":
    unittest.main()

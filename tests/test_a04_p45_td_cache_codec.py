"""A04/P0.45: fake Twelve Data UTC M5 payloads; no API/Drive calls."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from mfx_cache.td_m5_codec import (
    VERSION, ClosedM5Bar, canonical, check_manifest, compute_delta,
    content_chunk, digest, initial_manifest, next_manifest,
    parse_closed_utc_m5,
)

NOW = datetime(2026, 11, 10, 10, 31, tzinfo=timezone.utc)
RAW = {
    "meta": {
        "symbol": "EUR/USD", "interval": "5min",
        "exchange_timezone": "Australia/Sydney",
        "type": "Physical Currency",
    },
    "status": "ok",
    "values": [
        {"datetime": "2026-11-10 10:30:00", "open": "1.3", "high": "1.4",
         "low": "1.2", "close": "1.25"},  # OPEN: must exclude
        {"datetime": "2026-11-10 10:25:00", "open": "1.2", "high": "1.3",
         "low": "1.1", "close": "1.25"},
        {"datetime": "2026-11-10 10:20:00", "open": "1.1", "high": "1.3",
         "low": "1.0", "close": "1.2"},
    ],
}


def parsed():
    return parse_closed_utc_m5(deepcopy(RAW), now_utc=NOW)


def filled():
    m = initial_manifest(NOW)
    rows = parsed()
    d = compute_delta(m, rows)
    chunk = content_chunk(d, NOW)
    return next_manifest(m, d, now_utc=NOW,
                         new_chunk_sha256=digest(chunk))


class P045CloudCachePureTests(unittest.TestCase):
    def test_01_utc_request_closed_only_and_sorted(self) -> None:
        v = parsed()
        self.assertEqual(len(v), 2)
        self.assertEqual([b.start_utc for b in v], [
            "2026-11-10T10:20:00+00:00", "2026-11-10T10:25:00+00:00",
        ])

    def test_02_default_exchange_timezone_not_wrongly_used(self) -> None:
        self.assertEqual(len(parsed()), 2)
        self.assertEqual(parsed()[0].start_utc,
                         "2026-11-10T10:20:00+00:00")

    def test_03_first_chunk_and_manifest_increment(self) -> None:
        m = filled()
        self.assertEqual((m["total_closed_bars_archived"], m["total_chunks"]),
                         (2, 1))
        self.assertEqual(m["credits_reserved_today"], 1)
        self.assertEqual(m["schema"], VERSION)
        self.assertEqual(m["source"], "TWELVE_DATA_COMPOSITE_MID")
        self.assertEqual(m["side"], "MID")

    def test_04_closed_identical_second_fetch_no_chunk(self) -> None:
        m = filled()
        d = compute_delta(m, parsed())
        self.assertTrue(d.no_change)
        self.assertEqual(d.new_bars, ())
        after = next_manifest(m, d, now_utc=NOW + timedelta(minutes=5),
                              new_chunk_sha256=None)
        self.assertEqual(after["total_chunks"], 1)
        self.assertEqual(after["credits_reserved_today"], 2)

    def test_05_revision_overlap_is_quarantined(self) -> None:
        m = filled()
        edited = list(parsed())
        old = edited[1]
        edited[1] = ClosedM5Bar(old.start_utc, old.open, old.high,
                                old.low, "1.29")
        with self.assertRaisesRegex(ValueError, "P045_HISTORICAL_CLOSED_BAR_REVISION"):
            compute_delta(m, tuple(edited))

    def test_06_gap_is_not_filled_or_assumed_contiguous(self) -> None:
        m = filled()
        new = ClosedM5Bar("2026-11-10T10:35:00+00:00",
                          "1.2", "1.3", "1.1", "1.25")
        d = compute_delta(m, (new,))
        self.assertEqual(d.gaps_detected, 1)
        self.assertEqual(len(d.new_bars), 1)

    def test_07_exact_five_minute_delta(self) -> None:
        m = filled()
        new = ClosedM5Bar("2026-11-10T10:30:00+00:00",
                          "1.2", "1.3", "1.1", "1.25")
        d = compute_delta(m, (new,))
        self.assertEqual(d.gaps_detected, 0)

    def test_08_no_real_signals_or_orders_possible(self) -> None:
        m = filled()
        self.assertFalse(m["may_confirm_user_buy_sell"])
        self.assertEqual(m["broker_orders"], 0)
        d = compute_delta(initial_manifest(NOW), parsed())
        c = content_chunk(d, NOW)
        self.assertEqual(c["confirmed_user_signals"], 0)
        self.assertIs(c["may_trade"], False)

    def test_09_wrong_vendor_symbol_denied(self) -> None:
        data = deepcopy(RAW)
        data["meta"]["symbol"] = "GBP/USD"
        with self.assertRaisesRegex(ValueError, "P045_VENDOR_SYMBOL"):
            parse_closed_utc_m5(data, now_utc=NOW)

    def test_10_wrong_interval_denied(self) -> None:
        data = deepcopy(RAW)
        data["meta"]["interval"] = "1day"
        with self.assertRaisesRegex(ValueError, "P045_VENDOR_SYMBOL"):
            parse_closed_utc_m5(data, now_utc=NOW)

    def test_11_non_forex_type_denied(self) -> None:
        data = deepcopy(RAW)
        data["meta"]["type"] = "Common Stock"
        with self.assertRaisesRegex(ValueError, "P045_NON_FOREX"):
            parse_closed_utc_m5(data, now_utc=NOW)

    def test_12_duplicate_vendor_timestamp_denied(self) -> None:
        data = deepcopy(RAW)
        data["values"].append(data["values"][-1].copy())
        with self.assertRaisesRegex(ValueError, "P045_DUPLICATE_VENDOR_BAR"):
            parse_closed_utc_m5(data, now_utc=NOW)

    def test_13_invalid_ohlc_denied(self) -> None:
        data = deepcopy(RAW)
        data["values"][1]["low"] = "1.4"
        with self.assertRaisesRegex(ValueError, "P045_INVALID_OHLC"):
            parse_closed_utc_m5(data, now_utc=NOW)

    def test_14_zero_nan_non_decimal_prices_denied(self) -> None:
        for invalid in ("NaN", "0", "-1", 1.2):
            data = deepcopy(RAW)
            data["values"][1]["open"] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_closed_utc_m5(data, now_utc=NOW)

    def test_15_malformed_or_unaligned_utc_timestamp_denied(self) -> None:
        for bad in ("2026-11-10 10:21:00", "2026-11-10T10:20:00",
                    "2026-11-10 10:20:59"):
            data = deepcopy(RAW)
            data["values"][1]["datetime"] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_closed_utc_m5(data, now_utc=NOW)

    def test_16_naive_or_non_utc_clock_denied(self) -> None:
        for bad in (NOW.replace(tzinfo=None),
                    NOW.replace(tzinfo=timezone(timedelta(hours=7)))):
            with self.assertRaisesRegex(ValueError, "P045_EXACT_UTC"):
                parse_closed_utc_m5(deepcopy(RAW), now_utc=bad)

    def test_17_manifest_source_forgery_denied(self) -> None:
        m = filled()
        for k, v in (("source", "UNKNOWN"), ("side", "BID"),
                     ("may_confirm_user_buy_sell", True),
                     ("broker_orders", 1)):
            forged = {**m, k: v}
            with self.subTest(k=k), self.assertRaises(ValueError):
                check_manifest(forged)

    def test_18_duplicate_index_denied(self) -> None:
        m = filled()
        m["recent_bars"].append(m["recent_bars"][0])
        with self.assertRaisesRegex(ValueError, "P045_DUPLICATE_OR_REORDERED"):
            check_manifest(m)

    def test_19_digest_and_chunk_deterministic(self) -> None:
        d = compute_delta(initial_manifest(NOW), parsed())
        a = content_chunk(d, NOW)
        self.assertEqual(digest(a), digest(a))
        self.assertEqual(canonical(a), canonical(deepcopy(a)))
        self.assertEqual(len(digest(a)), 64)

    def test_20_empty_chunk_denied(self) -> None:
        m = filled()
        d = compute_delta(m, parsed())
        with self.assertRaisesRegex(ValueError, "P045_NO_EMPTY"):
            content_chunk(d, NOW)

    def test_21_new_data_cannot_omit_chunk_link(self) -> None:
        d = compute_delta(initial_manifest(NOW), parsed())
        with self.assertRaisesRegex(ValueError, "P045_CHUNK_REQUIRED"):
            next_manifest(initial_manifest(NOW), d, now_utc=NOW,
                          new_chunk_sha256=None)

    def test_22_old_history_outside_recent_index_fail_closed(self) -> None:
        m = filled()
        m["recent_bars"] = m["recent_bars"][-1:]
        older = parsed()[0]
        with self.assertRaisesRegex(ValueError, "P045_OLDER_THAN_RECENT"):
            compute_delta(m, (older,))

    def test_23_manifest_can_reject_boolean_fake_credit_count(self) -> None:
        m = filled()
        m["credits_reserved_today"] = True
        with self.assertRaisesRegex(ValueError, "P045_INVALID_QUOTA"):
            check_manifest(m)

    def test_24_explicit_stale_bootstrap_quote_does_not_override_latest(self) -> None:
        m = filled()
        d = compute_delta(m, parsed()[:1])
        self.assertTrue(d.no_change)
        self.assertEqual(d.newest, m["last_start_utc"])

    def test_25_daily_budget_resets_only_with_utc_date(self) -> None:
        m = filled()
        d = compute_delta(m, ())
        after = next_manifest(
            m, d, now_utc=datetime(2026, 11, 11, tzinfo=timezone.utc),
            new_chunk_sha256=None,
        )
        self.assertEqual(after["credits_reserved_today"], 1)
        self.assertEqual(after["credit_day_utc"], "2026-11-11")


if __name__ == "__main__":
    unittest.main()

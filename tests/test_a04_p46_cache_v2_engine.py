"""P046 Cache V2: strict offline accuracy/efficiency and adverse cases."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from mfx_cache.td_m5_codec import ClosedM5Bar
from mfx_cache.v2_engine import (
    CALENDAR, PROVIDER, VERSION,
    FetchCandidate, RawChunk, compact_utc_days, derive_intraday,
    detect_missing, indicator_cache, make_chunk,
    modeled_write_pressure, plan_fetch, source_fingerprint, validate_m5,
)

UTC = timezone.utc
BASE = datetime(2026, 11, 10, 12, tzinfo=UTC)
ASOF = datetime(2026, 11, 10, 15, tzinfo=UTC)


def bars(n: int = 12, *, start: datetime = BASE) -> tuple[ClosedM5Bar, ...]:
    out: list[ClosedM5Bar] = []
    for i in range(n):
        close = Decimal("1.10000") + Decimal(i) / Decimal("100000")
        out.append(ClosedM5Bar(
            start_utc=(start + timedelta(minutes=5*i)).isoformat(),
            open="1.10000", high="1.20000", low="1.00000",
            close=str(close),
        ))
    return tuple(out)


def candidate(
    symbol: str, frame: str, *,
    last: str | None = None,
    polled: str | None = None,
    priority: int = 5,
    cost: int = 1,
) -> FetchCandidate:
    return FetchCandidate(
        symbol=symbol, frame=frame, last_closed_start_utc=last,
        last_polled_utc=polled, priority=priority, request_credits=cost,
    )


class P046CacheV2Test(unittest.TestCase):
    def test_01_m15_exact_3_closed_m5_bars(self) -> None:
        r = derive_intraday(bars(3), "M15", asof_utc=ASOF)
        self.assertEqual(len(r.candles), 1)
        self.assertEqual(r.candles[0].source_count, 3)
        self.assertEqual(r.candles[0].frame, "M15")
        self.assertEqual((r.candles[0].open, r.candles[0].close),
                         (bars(3)[0].open, bars(3)[-1].close))

    def test_02_m30_exact_6_m5(self) -> None:
        r = derive_intraday(bars(6), "M30", asof_utc=ASOF)
        self.assertEqual((len(r.candles), r.candles[0].source_count), (1, 6))

    def test_03_h1_exact_12_m5(self) -> None:
        r = derive_intraday(bars(12), "H1", asof_utc=ASOF)
        self.assertEqual((len(r.candles), r.candles[0].source_count), (1, 12))
        self.assertEqual(r.candles[0].end_utc,
                         "2026-11-10T13:00:00+00:00")

    def test_04_incomplete_m15_is_skipped_not_fabricated(self) -> None:
        subset = (bars(3)[0], bars(3)[2])
        r = derive_intraday(subset, "M15", asof_utc=ASOF)
        self.assertEqual(r.candles, ())
        self.assertEqual(r.skipped_incomplete_windows,
                         ("2026-11-10T12:00:00+00:00",))

    def test_05_24_m5_yield_two_h1(self) -> None:
        r = derive_intraday(bars(24), "H1", asof_utc=ASOF)
        self.assertEqual(len(r.candles), 2)
        self.assertEqual(r.skipped_incomplete_windows, ())

    def test_06_h4_d1_never_created_from_m5(self) -> None:
        for frame in ("H4", "D1", "W1", "M5"):
            with self.subTest(frame=frame), self.assertRaisesRegex(
                ValueError, "P046_H4_D1_MUST_BE_PROVIDER_NATIVE"
            ):
                derive_intraday(bars(12), frame, asof_utc=ASOF)

    def test_07_origin_and_quality_not_fake_provider_native(self) -> None:
        c = derive_intraday(bars(3), "M15", asof_utc=ASOF).candles[0]
        self.assertEqual(c.source_provider, PROVIDER)
        self.assertEqual(c.calendar_version, CALENDAR)
        self.assertFalse(c.is_source_native)
        self.assertFalse(c.source_numeric_strategy_approved)
        self.assertEqual(c.price_side, "MID")
        self.assertEqual(len(c.source_sha256), 64)

    def test_08_change_in_m5_invalidates_only_that_window(self) -> None:
        baseline = derive_intraday(bars(6), "M15", asof_utc=ASOF)
        original = bars(6)
        revised = replace(original[1], close="1.10100")
        changed = derive_intraday(
            original[:1] + (revised,) + original[2:], "M15", asof_utc=ASOF,
        )
        self.assertNotEqual(baseline.candles[0].source_sha256,
                            changed.candles[0].source_sha256)
        self.assertEqual(baseline.candles[1].source_sha256,
                         changed.candles[1].source_sha256)

    def test_09_m5_duplicate_rejected(self) -> None:
        a = bars(1)[0]
        with self.assertRaisesRegex(ValueError, "P046_DUPLICATE_OR_UNORDERED"):
            validate_m5((a, a), asof_utc=ASOF)

    def test_10_future_bar_rejected(self) -> None:
        future = bars(1, start=ASOF-timedelta(minutes=5))[0]
        with self.assertRaisesRegex(ValueError, "P046_FUTURE_OPEN"):
            validate_m5((future,), asof_utc=ASOF)

    def test_11_naive_timestamp_rejected(self) -> None:
        a = replace(bars(1)[0], start_utc="2026-11-10T12:00:00")
        with self.assertRaisesRegex(ValueError, "P046_EXACT_M5_UTC"):
            validate_m5((a,), asof_utc=ASOF)

    def test_12_offset_aware_non_utc_rejected(self) -> None:
        a = replace(bars(1)[0], start_utc="2026-11-10T19:00:00+07:00")
        with self.assertRaisesRegex(ValueError, "P046_EXACT_M5_UTC"):
            validate_m5((a,), asof_utc=ASOF)

    def test_13_invalid_low_high_rejected(self) -> None:
        a = replace(bars(1)[0], low="1.300")
        with self.assertRaisesRegex(ValueError, "P046_INVALID_M5_OHLC"):
            validate_m5((a,), asof_utc=ASOF)

    def test_14_nonfinite_price_rejected(self) -> None:
        for bad in ("NaN", "Infinity", "-1"):
            a = replace(bars(1)[0], close=bad)
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_m5((a,), asof_utc=ASOF)

    def test_15_missing_slot_marked_not_created(self) -> None:
        three = bars(3)
        missing = (three[0], three[2])
        gaps = detect_missing(missing, asof_utc=ASOF)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].missing_m5_slots, 1)
        self.assertEqual(gaps[0].classification, "POSSIBLE_SOURCE_HOLE")
        self.assertFalse(gaps[0].auto_backfill_allowed)

    def test_16_weekend_like_gap_classified_unknown_session(self) -> None:
        a = bars(1)[0]
        b = bars(1, start=BASE+timedelta(days=3))[0]
        gaps = detect_missing((a, b), asof_utc=BASE+timedelta(days=4))
        self.assertEqual(gaps[0].classification, "SESSION_UNKNOWN")
        self.assertFalse(gaps[0].auto_backfill_allowed)

    def test_17_gap_list_limit_fails_closed(self) -> None:
        seq = (bars(1)[0], bars(1, start=BASE+timedelta(minutes=15))[0],
               bars(1, start=BASE+timedelta(minutes=30))[0])
        with self.assertRaisesRegex(ValueError, "P046_GAP_REPORT_TOO_LARGE"):
            detect_missing(seq, asof_utc=ASOF, max_holes=1)

    def test_18_identical_chunks_compact_without_duplicates(self) -> None:
        source = bars(4)
        chunks = tuple(make_chunk((b,), asof_utc=ASOF) for b in source)
        p = compact_utc_days(chunks + (chunks[0],), asof_utc=ASOF)
        self.assertEqual(len(p), 1)
        self.assertEqual(len(p[0].canonical_bars), 4)
        self.assertEqual(len(p[0].parent_chunk_sha256), 4)
        self.assertFalse(p[0].parent_deletion_authorized)
        self.assertFalse(p[0].drive_verified_readback)

    def test_19_below_compaction_threshold_not_flushed(self) -> None:
        chunks = tuple(make_chunk((b,), asof_utc=ASOF) for b in bars(3))
        self.assertEqual(compact_utc_days(chunks, asof_utc=ASOF), ())

    def test_20_compacted_digest_deterministic_under_parent_order(self) -> None:
        chunks = tuple(make_chunk((b,), asof_utc=ASOF) for b in bars(5))
        fwd = compact_utc_days(chunks, asof_utc=ASOF)
        back = compact_utc_days(tuple(reversed(chunks)), asof_utc=ASOF)
        self.assertEqual(fwd, back)
        self.assertEqual(len(fwd[0].compacted_sha256), 64)

    def test_21_compaction_tampered_parent_sha_rejected(self) -> None:
        c = make_chunk(bars(1), asof_utc=ASOF)
        bad = replace(c, sha256="0"*64)
        with self.assertRaisesRegex(ValueError, "P046_CHUNK_CONTENT_SHA"):
            compact_utc_days((bad,), asof_utc=ASOF)

    def test_22_conflicting_overlap_quarantined(self) -> None:
        first = bars(1)[0]
        changed = replace(first, close="1.10099")
        a = make_chunk((first,), asof_utc=ASOF)
        b = make_chunk((changed,), asof_utc=ASOF)
        with self.assertRaisesRegex(ValueError, "P046_OVERLAPPING_REVISED"):
            compact_utc_days((a,b), asof_utc=ASOF, min_parent_chunks=2)

    def test_23_parent_chunk_source_provenance_rejected(self) -> None:
        c = make_chunk(bars(1), asof_utc=ASOF)
        bad = replace(c, side="BID")
        with self.assertRaisesRegex(ValueError, "P046_COMPACTION_PROVENANCE"):
            compact_utc_days((bad,), asof_utc=ASOF)

    def test_24_cross_utc_day_partitions_are_separate(self) -> None:
        near = datetime(2026, 11, 10, 23, 50, tzinfo=UTC)
        later = near + timedelta(minutes=10)
        chunks = tuple(make_chunk((b,), asof_utc=ASOF+timedelta(days=1))
                       for b in (*bars(2, start=near), *bars(2, start=later)))
        p = compact_utc_days(chunks, asof_utc=ASOF+timedelta(days=1),
                             min_parent_chunks=2)
        self.assertEqual(len(p), 2)
        self.assertEqual({part.utc_day for part in p},
                         {"2026-11-10", "2026-11-11"})

    def test_25_indicator_ema_atr_research_computed(self) -> None:
        r = indicator_cache(bars(8), period=3, asof_utc=ASOF)
        self.assertFalse(r.reused)
        self.assertTrue(Decimal(r.snapshot.ema_close).is_finite())
        self.assertTrue(Decimal(r.snapshot.atr_wilder) > 0)
        self.assertFalse(r.snapshot.numerical_strategy_approved)
        self.assertFalse(r.snapshot.publishable_signal)

    def test_26_indicator_reuse_identical_hash(self) -> None:
        first = indicator_cache(bars(8), period=3, asof_utc=ASOF)
        second = indicator_cache(bars(8), period=3, asof_utc=ASOF,
                                 cached=first.snapshot)
        self.assertTrue(second.reused)
        self.assertEqual(first.snapshot, second.snapshot)

    def test_27_indicator_recomputes_only_changed_window(self) -> None:
        original = bars(8)
        first = indicator_cache(original, period=3, asof_utc=ASOF)
        altered = original[:3] + (replace(original[3], close="1.10099"),) + original[4:]
        second = indicator_cache(altered, period=3, asof_utc=ASOF,
                                 cached=first.snapshot)
        self.assertFalse(second.reused)
        self.assertNotEqual(first.snapshot.source_sha256,
                            second.snapshot.source_sha256)

    def test_28_different_indicator_period_invalidates_cache(self) -> None:
        first = indicator_cache(bars(8), period=3, asof_utc=ASOF)
        other = indicator_cache(bars(8), period=4, asof_utc=ASOF,
                                cached=first.snapshot)
        self.assertFalse(other.reused)

    def test_29_indicator_gap_fails_closed(self) -> None:
        source = bars(8)
        missing = source[:3] + source[4:]
        with self.assertRaisesRegex(ValueError, "P046_INDICATOR_REQUIRES_CONTIGUOUS"):
            indicator_cache(missing, period=3, asof_utc=ASOF)

    def test_30_indicator_unsupported_period_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "P046_EXPLICIT_RESEARCH"):
            indicator_cache(bars(8), period=1, asof_utc=ASOF)

    def test_31_smart_fetch_no_request_when_candle_not_due(self) -> None:
        last = "2026-11-10T14:50:00+00:00"
        r = plan_fetch((candidate("EUR/USD", "M5", last=last),),
                       now_utc=ASOF,
                       minute_credits_remaining=7,
                       day_credits_remaining=720)
        self.assertEqual(r.selected, ())
        self.assertEqual(r.not_due, ("EUR/USD:M5",))

    def test_32_smart_fetch_due_old_data_budgeted(self) -> None:
        r = plan_fetch((candidate("EUR/USD", "M5",
                                  last="2026-11-10T14:40:00+00:00"),),
                       now_utc=ASOF,
                       minute_credits_remaining=7,
                       day_credits_remaining=720)
        self.assertEqual(len(r.selected), 1)
        self.assertEqual(r.credits_reserved, 1)
        self.assertEqual(r.market_api_calls, 0)

    def test_33_smart_fetch_deduplicates_poll_slot(self) -> None:
        r = plan_fetch((candidate(
            "EUR/USD","M5", polled="2026-11-10T15:00:00+00:00"),),
            now_utc=ASOF, minute_credits_remaining=7,
            day_credits_remaining=720)
        self.assertEqual(r.selected, ())
        self.assertEqual(r.not_due, ("EUR/USD:M5",))

    def test_34_budget_denies_excess_not_bypass(self) -> None:
        xs = (candidate("EUR/USD","M5",priority=0,cost=2),
              candidate("GBP/USD","M5",priority=1,cost=2),
              candidate("AUD/USD","M5",priority=2,cost=1))
        r = plan_fetch(xs, now_utc=ASOF,
                       minute_credits_remaining=3,
                       day_credits_remaining=3, max_requests=3)
        self.assertEqual([x.symbol for x in r.selected],
                         ["EUR/USD","AUD/USD"])
        self.assertEqual(r.due_but_deferred, ("GBP/USD:M5",))
        self.assertEqual(r.credits_reserved, 3)

    def test_35_no_daily_credits_means_no_calls(self) -> None:
        r = plan_fetch((candidate("EUR/USD","D1"),),
                       now_utc=ASOF, minute_credits_remaining=7,
                       day_credits_remaining=0)
        self.assertEqual(r.selected, ())
        self.assertEqual(r.due_but_deferred, ("EUR/USD:D1",))

    def test_36_h4_d1_due_independently_of_m5(self) -> None:
        r = plan_fetch((candidate("EUR/USD","M5",
                      last="2026-11-10T14:55:00+00:00"),
                      candidate("EUR/USD","H4",
                      last="2026-11-10T04:00:00+00:00"),
                      candidate("EUR/USD","D1",
                      last="2026-11-08T00:00:00+00:00")),
                       now_utc=ASOF, minute_credits_remaining=7,
                       day_credits_remaining=720)
        self.assertEqual({x.frame for x in r.selected}, {"H4","D1"})

    def test_37_refuse_invalid_symbols_mixed_price_frames(self) -> None:
        for invalid in ("EURUSD","eur/usd","../USD"):
            with self.subTest(s=invalid), self.assertRaisesRegex(
                ValueError, "P046_INVALID_SYMBOL"):
                plan_fetch((candidate(invalid,"M5"),),now_utc=ASOF,
                           minute_credits_remaining=7,
                           day_credits_remaining=720)

    def test_38_duplicate_fetch_target_denied(self) -> None:
        xs = (candidate("EUR/USD","M5"),candidate("EUR/USD","M5"))
        with self.assertRaisesRegex(ValueError, "P046_INVALID_SYMBOL"):
            plan_fetch(xs,now_utc=ASOF,minute_credits_remaining=7,
                       day_credits_remaining=720)

    def test_39_modeled_pressure_scenario_explicit_not_measured(self) -> None:
        r = modeled_write_pressure(
            polls_per_day=288, flushes_per_day=8, days=7)
        self.assertEqual(r["p045_max_two_files_per_poll_scenario"], 4032)
        self.assertEqual(r["p046_two_files_per_flush_scenario"], 112)
        self.assertEqual(r["potential_files_avoided_scenario"], 3920)
        self.assertEqual(r["classification"],
                         "SCENARIO_ONLY_NOT_MEASURED_DRIVE_IO")

    def test_40_model_pressure_disallows_invalid_assumptions(self) -> None:
        with self.assertRaisesRegex(ValueError, "P046_FLUSHES_CANNOT"):
            modeled_write_pressure(polls_per_day=1, flushes_per_day=2, days=7)

    def test_41_source_hash_is_deterministic_and_sensitive(self) -> None:
        original = bars(3)
        changed = original[:2] + (replace(original[2], close="1.10101"),)
        self.assertEqual(source_fingerprint(original), source_fingerprint(original))
        self.assertNotEqual(source_fingerprint(original), source_fingerprint(changed))
        self.assertEqual(len(source_fingerprint(original)),64)

    def test_42_empty_or_unbounded_source_denied(self) -> None:
        with self.assertRaisesRegex(ValueError, "P046_BOUNDED_M5"):
            validate_m5((), asof_utc=ASOF)

    def test_43_protection_against_forward_unverified_indicators(self) -> None:
        source = bars(8)
        future = replace(source[-1], start_utc=ASOF.isoformat())
        with self.assertRaisesRegex(ValueError, "P046_FUTURE_OPEN"):
            indicator_cache(source[:-1]+(future,),period=3,asof_utc=ASOF)

    def test_44_grouping_with_midnight_anchor(self) -> None:
        near = datetime(2026, 11, 10, 23, 45,tzinfo=UTC)
        r = derive_intraday(bars(6,start=near),"M15",
                            asof_utc=ASOF+timedelta(days=1))
        self.assertEqual(len(r.candles),2)
        self.assertEqual(r.candles[0].start_utc,
                         "2026-11-10T23:45:00+00:00")
        self.assertEqual(r.candles[1].start_utc,
                         "2026-11-11T00:00:00+00:00")

    def test_45_provider_quota_negative_and_type_denied(self) -> None:
        with self.assertRaisesRegex(ValueError, "P046_BOUNDED_FETCH"):
            plan_fetch((candidate("EUR/USD","M5"),),now_utc=ASOF,
                       minute_credits_remaining=-1,day_credits_remaining=720)
        with self.assertRaisesRegex(ValueError, "P046_BOUNDED_FETCH"):
            plan_fetch((candidate("EUR/USD","M5"),),now_utc=ASOF,
                       minute_credits_remaining=7,day_credits_remaining=720,
                       max_requests=8)

    def test_46_no_real_market_or_broker_in_pure_outputs(self) -> None:
        r = derive_intraday(bars(12),"H1",asof_utc=ASOF)
        self.assertEqual((r.provider_calls,r.broker_orders),(0,0))
        f = plan_fetch((candidate("EUR/USD","M5"),),now_utc=ASOF,
                       minute_credits_remaining=7,day_credits_remaining=720)
        self.assertEqual((f.market_api_calls, f.drive_file_writes),(0,0))
        self.assertEqual(VERSION, "MFX_A04_P46_CACHE_V2_CORE_V1")


if __name__ == "__main__":
    unittest.main()

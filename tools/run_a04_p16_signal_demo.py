"""GitHub CI-only demonstrator: actual synthetic BUY and SELL research receipts."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

from forex_trading.market_data import (
    BarCoverage, BarLifecycle, BarSide, MarketBar, MarketBarKey, Observation,
    SourceQuality, Timeframe,
)
from mfx_research.offline_ema_signals import (
    CandidateAction, research_only_ema_signal,
)

START = datetime(2026, 11, 9, tzinfo=timezone.utc)
BUY_CLOSES: tuple[str, ...] = ("12", "11", "10", "9", "8", "14")
SELL_CLOSES: tuple[str, ...] = ("8", "9", "10", "11", "12", "6")
FLAT_CLOSES: tuple[str, ...] = ("10", "10", "10", "10", "10", "10")


def synthetic_m15_bars(
    closes: tuple[str, ...], *, instrument: str = "SIM:PAIR-1",
) -> tuple[MarketBar, ...]:
    """Fabricated unit-test source, never a market-feed schema or entitlement."""
    bars: list[MarketBar] = []
    for index, value in enumerate(closes):
        begin = START + timedelta(minutes=15 * index)
        end = begin + timedelta(minutes=15)
        known = end + timedelta(seconds=1)
        price = Decimal(value)
        observation = Observation(
            provider_id="SIM:TEST-DATASET", stream_id="SIM:CLOSED-M15-OHLC",
            endpoint="SIM:NO-NETWORK", revision_id=f"SIM:REV-{index}",
            raw_sha256="0" * 64, first_known_utc=known,
            retrieved_at_utc=known, source_timezone_policy="SIM:UTC",
            license_scope_claim="SYNTHETIC_ONLY",
        )
        bar = MarketBar(
            key=MarketBarKey(
                instrument_version=instrument, timeframe=Timeframe.M15,
                bar_start_utc=begin, bar_end_utc=end,
                calendar_version="SIM:UTC-M15", aggregation_version="SIM:OHLC-1",
                side=BarSide.MID,
            ),
            observation=observation, revision_number=1, first_known_utc=known,
            open=price, high=price + Decimal("0.1"),
            low=price - Decimal("0.1"), close=price,
            lifecycle=BarLifecycle.CLOSED, coverage=BarCoverage.COMPLETE,
            quality=SourceQuality.VERIFIED,
        )
        bars.append(bar)
    return tuple(bars)


def main() -> None:
    result: list[dict[str, str | bool | int]] = []
    for values, expected in (
        (BUY_CLOSES, CandidateAction.BUY),
        (SELL_CLOSES, CandidateAction.SELL),
        (FLAT_CLOSES, CandidateAction.NO_SIGNAL),
    ):
        bars = synthetic_m15_bars(values)
        decision = bars[-1].first_known_utc + timedelta(seconds=1)
        candidate = research_only_ema_signal(bars, decision)
        if candidate.action is not expected:
            raise ValueError("P016_ACTUAL_RESEARCH_CANDIDATE_MISMATCH")
        row = candidate.as_record()
        if (row["stage"] != "UNVERIFIED" or
                row["source_verified"] is not False or
                row["economic_parity_proven"] is not False or
                row["can_trade"] is not False or
                row["provider_requests"] != 0 or
                row["drive_market_cache_writes"] != 0):
            raise ValueError("P016_FRAUDULENT_VERIFIED_SIGNAL_OR_TRADE")
        result.append(row)
    print("MFX_A04_P16_OFFLINE_RESEARCH_BUY_SELL_PASS")
    print("MFX_A04_P16_RECEIPT " + json.dumps({
        "cases": len(result), "actions": [x["action"] for x in result],
        "data": "SYNTHETIC_ONLY", "strategy": "NOT_ORIGINAL_FOREX_1_TO_1",
        "source_verified": False, "historical_bidask_proven": False,
        "actual_vendor_requests": 0, "drive_market_cache_writes": 0,
        "permission_to_trade": False, "release_ready": False,
    }, sort_keys=True))

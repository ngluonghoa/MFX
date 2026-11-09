"""Executable P0.20 synthetic right-confirmed swing + B2/S2 CI proof."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
import json

from forex_trading.market_data import MarketBar, Timeframe
from mfx_research.causal_multitf_context import SyntheticMultiTfBars
from mfx_research.confirmed_swings import (
    ConfirmedSwingResearchReceipt, PivotKind, SyntheticPivotParameters,
    derive_swing_b2_s2_research,
)
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.pullback_pilot import StructuralTrend
from tools.run_a04_p19_causal_context_demo import (
    _make_series, case_from_closed_bars,
)


_B2_UP: tuple[tuple[str, str, str, str], ...] = (
    ("1.090", "1.100", "1.080", "1.095"),
    ("1.095", "1.120", "1.090", "1.110"),
    ("1.095", "1.105", "1.060", "1.095"),
    ("1.095", "1.110", "1.075", "1.105"),
    ("1.105", "1.115", "1.085", "1.110"),
    ("1.110", "1.130", "1.095", "1.120"),
    ("1.110", "1.118", "1.080", "1.109"),
    ("1.110", "1.121", "1.090", "1.117"),
    ("1.117", "1.123", "1.092", "1.119"),
    ("1.119", "1.125", "1.094", "1.121"),
)
_S2_DOWN: tuple[tuple[str, str, str, str], ...] = (
    ("1.213", "1.230", "1.200", "1.218"),
    ("1.218", "1.240", "1.205", "1.234"),
    ("1.221", "1.226", "1.190", "1.217"),
    ("1.217", "1.224", "1.202", "1.215"),
    ("1.215", "1.216", "1.198", "1.210"),
    ("1.210", "1.225", "1.192", "1.215"),
    ("1.202", "1.210", "1.175", "1.190"),
    ("1.190", "1.212", "1.180", "1.208"),
    ("1.208", "1.211", "1.182", "1.205"),
    ("1.205", "1.213", "1.183", "1.209"),
)


def case_confirmed(
    rule: str,
) -> tuple[SyntheticMultiTfBars, SyntheticPivotParameters]:
    initial, _, _ = case_from_closed_bars(rule)
    raw = _B2_UP if rule == "B2" else _S2_DOWN if rule == "S2" else ()
    if not raw:
        raise ValueError("P020_SYNTHETIC_B2_S2_FIXTURE_ONLY")
    data = replace(
        initial,
        daily=_make_series(Timeframe.D1, raw),
        four_hour=_make_series(Timeframe.H4, raw),
    )
    return data, SyntheticPivotParameters(
        version="SIM:P020-LEFT1-RIGHT1-UNAPPROVED",
        left_bars=1, right_bars=1,
    )


def evaluate_case(rule: str) -> ConfirmedSwingResearchReceipt:
    data, policy = case_confirmed(rule)
    _, zone_policy, trigger_policy = case_from_closed_bars(rule)
    return derive_swing_b2_s2_research(
        rule, data, policy, zone_policy, trigger_policy,
        data.trigger_m15[-1].first_known_utc + timedelta(seconds=1),
        origin_event_id="SIM:P020-"+rule,
    )


def main() -> None:
    outcomes: list[str] = []
    for rule, expected, trend in (
        ("B2", CandidateAction.BUY, StructuralTrend.UP),
        ("S2", CandidateAction.SELL, StructuralTrend.DOWN),
    ):
        receipt = evaluate_case(rule)
        if (receipt.signal.action is not expected
                or receipt.daily_trend is not trend
                or receipt.four_hour_trend is not trend
                or receipt.signal.stage.value != "UNVERIFIED"
                or len([p for p in receipt.daily.pivots
                        if p.kind is PivotKind.HIGH]) < 2
                or len([p for p in receipt.daily.pivots
                        if p.kind is PivotKind.LOW]) < 2
                or any(p.confirmed_first_known_utc >
                       receipt.daily.asof_utc for p in receipt.daily.pivots)
                or receipt.may_send_confirmed_signal
                or receipt.source_forex_1to1_numerical_parity
                or receipt.can_trade or receipt.market_provider_calls != 0
                or receipt.drive_raw_market_cache_writes != 0):
            raise ValueError("P020_FAKE_CONFIRMED_SOURCE_SIGNAL_OR_BAD_SWINGS")
        outcomes.append(receipt.signal.action.value)
    print("MFX_A04_P20_CAUSAL_CONFIRMED_SWINGS_PASS")
    print("MFX_A04_P20_RECEIPT " + json.dumps({
        "research_actions": outcomes, "rules": ["B2", "S2"],
        "htf": ["D1", "H4"], "confirmation_rule": "RIGHT_BAR_CLOSED_FIRST_KNOWN",
        "research_pivots_not_source_approved": True,
        "tie_rule": "STRICT_EXTREMA_TIES_ARE_NOT_SWINGS",
        "approved_numerical_forex_detectors": 0,
        "confirmed_source_buy_sell_alerts": 0, "release_ready": False,
        "broker_orders": 0, "real_feed_requests": 0,
        "real_drive_cache_writes": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()

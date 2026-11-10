"""P0.33 hosted Cloud-only chronological SIM B2/S2 replay evidence demo."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
import json

from forex_trading.market_data import MarketBar
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.p033_asof_sim_replay import (
    SyntheticReplayWindow, run_asof_sim_ohlc_replay,
    verify_sim_replay_chain,
)
from tools.run_a04_p19_causal_context_demo import case_from_closed_bars


def shift(bar: MarketBar, delta: timedelta) -> MarketBar:
    return replace(
        bar,
        key=replace(
            bar.key, bar_start_utc=bar.key.bar_start_utc + delta,
            bar_end_utc=bar.key.bar_end_utc + delta,
        ),
        observation=replace(
            bar.observation,
            first_known_utc=bar.observation.first_known_utc + delta,
            retrieved_at_utc=bar.observation.retrieved_at_utc + delta,
        ),
        first_known_utc=bar.first_known_utc + delta,
    )


def fixture(rule: str, day: int, *, no_pattern: bool = False) -> SyntheticReplayWindow:
    bars, derivation, parameters = case_from_closed_bars(rule)
    delta = timedelta(days=day)
    shifted = replace(
        bars,
        daily=tuple(shift(x, delta) for x in bars.daily),
        four_hour=tuple(shift(x, delta) for x in bars.four_hour),
        hourly=tuple(shift(x, delta) for x in bars.hourly),
        micro_seed_m15=tuple(shift(x, delta) for x in bars.micro_seed_m15),
        trigger_m15=(shift(bars.trigger_m15[0], delta),
                     shift(bars.trigger_m15[1], delta)),
    )
    if no_pattern:
        old, last = shifted.trigger_m15
        shifted = replace(shifted, trigger_m15=(
            old, replace(last, close=old.close),
        ))
    return SyntheticReplayWindow(
        rule_id=rule, bars=shifted, derivation=derivation,
        parameters=parameters,
        decision_utc=shifted.trigger_m15[-1].first_known_utc
        + timedelta(seconds=1),
    )


def main() -> None:
    first = fixture("B2", 0)
    second = fixture("S2", 1)
    third = fixture("B2", 2, no_pattern=True)
    prefix = run_asof_sim_ohlc_replay((first,), first.decision_utc)
    complete = run_asof_sim_ohlc_replay(
        (first, second, third), third.decision_utc,
    )
    if (not verify_sim_replay_chain(complete)
            or complete.entries[0] != prefix.entries[0]
            or complete.entries[0].chain_sha256 != prefix.chain_tip_sha256
            or complete.executed_sim_snapshots != 3
            or complete.experimental_pattern_observations != 2
            or complete.no_pattern_snapshots != 1
            or [x.experimental_pattern for x in complete.entries]
            != [CandidateAction.BUY, CandidateAction.SELL,
                CandidateAction.NO_SIGNAL]
            or complete.entries[2].linked_research_labels != ()
            or any(x.action != "NO_SIGNAL" for x in complete.entries)
            or complete.owner_signed_entry_numeric_rules != 0
            or complete.actual_confirmed_buy_sell_signals != 0
            or complete.real_market_backtest_trades != 0
            or complete.actual_out_of_sample_performance_metrics != 0
            or complete.provider_calls != 0
            or complete.real_drive_market_cache_writes != 0
            or complete.broker_orders != 0
            or complete.publish_alerts or complete.may_trade
            or complete.release_ready):
        raise RuntimeError("P033_ASOF_REPLAY_CAUSAL_PREFIX_OR_SAFETY_FAILED")
    print("MFX_A04_P33_CAUSAL_SIM_REPLAY_CHAIN_NO_SIGNAL_PASS")
    print("MFX_A04_P33_RECEIPT " + json.dumps({
        "source": "SYNTHETIC_CLOSED_OHLC_NOT_MARKET_DATA",
        "snapshot_count": complete.executed_sim_snapshots,
        "computed_experimental_pattern_count":
            complete.experimental_pattern_observations,
        "no_pattern_count": complete.no_pattern_snapshots,
        "experimental_patterns": [
            x.experimental_pattern.value for x in complete.entries
        ],
        "linked_labels": [
            list(x.linked_research_labels) for x in complete.entries
        ],
        "prefix_invariant_under_future_append": True,
        "in_memory_chain_tip_sha256": complete.chain_tip_sha256,
        "signed_numerical_entry_rules": complete.owner_signed_entry_numeric_rules,
        "original_b2_s2_owner_obligations_pending":
            complete.original_b2_s2_owner_numeric_obligations_pending,
        "production_alerts": complete.actual_confirmed_buy_sell_signals,
        "real_market_backtest_trades": complete.real_market_backtest_trades,
        "real_out_of_sample_metrics":
            complete.actual_out_of_sample_performance_metrics,
        "real_provider_calls": complete.provider_calls,
        "drive_quote_cache_writes": complete.real_drive_market_cache_writes,
        "broker_orders": complete.broker_orders,
        "release_ready": complete.release_ready,
    }, sort_keys=True))


if __name__ == "__main__":
    main()

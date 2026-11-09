"""P0.19 cloud CI fixtures: derive D1/H4/H1 and prior M15 from CLOSED OHLC."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
import json

from forex_trading.market_data import (
    BarCoverage, BarLifecycle, BarSide, MarketBar, MarketBarKey, Observation,
    SourceQuality, Timeframe,
)
from mfx_research.causal_multitf_context import (
    DerivedResearchReceipt, SyntheticDerivationParameters, SyntheticMultiTfBars,
    derive_and_evaluate_b2_s2,
)
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.pullback_pilot import UnapprovedResearchParameters
from tools.run_a04_p18_pullback_demo import case
from tools.run_a04_p16_signal_demo import START


_DURATIONS = {
    Timeframe.D1: timedelta(days=1), Timeframe.H4: timedelta(hours=4),
    Timeframe.H1: timedelta(hours=1), Timeframe.M15: timedelta(minutes=15),
}


def _make_series(tf: Timeframe, values: tuple[tuple[str, str, str, str], ...],
                 *, last_known_delay_seconds: int = 0) -> tuple[MarketBar, ...]:
    series: list[MarketBar] = []
    for i, (o, h, low_value, c) in enumerate(values):
        end = START - _DURATIONS[tf] * (len(values) - i - 1)
        begin = end - _DURATIONS[tf]
        known = end + timedelta(seconds=last_known_delay_seconds)
        series.append(MarketBar(
            key=MarketBarKey(
                instrument_version="SIM:PAIR-1", timeframe=tf,
                bar_start_utc=begin, bar_end_utc=end,
                calendar_version="SIM:UTC-CLOSED",
                aggregation_version="SIM:OHLC-TR",
                side=BarSide.MID,
            ),
            observation=Observation(
                provider_id="SIM:P019-FAKE", stream_id="SIM:" + tf.value,
                endpoint="SIM:IN_MEMORY_NO_FEED", revision_id=f"SIM:{tf.value}:{i}",
                raw_sha256="0" * 64, first_known_utc=known,
                retrieved_at_utc=known, source_timezone_policy="SIM:UTC",
                license_scope_claim="SYNTHETIC_ONLY",
            ),
            revision_number=1, first_known_utc=known,
            open=Decimal(o), high=Decimal(h), low=Decimal(low_value), close=Decimal(c),
            lifecycle=BarLifecycle.CLOSED, coverage=BarCoverage.COMPLETE,
            quality=SourceQuality.VERIFIED,
        ))
    return tuple(series)


def case_from_closed_bars(rule: str) -> tuple[
    SyntheticMultiTfBars, SyntheticDerivationParameters,
    UnapprovedResearchParameters,
]:
    """All values are invented and restricted to unit-test simulation."""
    h1: tuple[tuple[str, str, str, str], ...]
    if rule == "B2":
        d1 = (
            ("1.090", "1.100", "1.070", "1.095"),
            ("1.095", "1.105", "1.085", "1.101"),
        )
        h4 = (
            ("1.095", "1.102", "1.083", "1.097"),
            ("1.097", "1.106", "1.089", "1.101"),
        )
        h1 = (
            ("1.1020", "1.1030", "1.1010", "1.1020"),
            ("1.1020", "1.1030", "1.1005", "1.1010"),
            ("1.1010", "1.1020", "1.1007", "1.1010"),
            ("1.1010", "1.1020", "1.1008", "1.1011"),
        )
        seed = (("1.1010", "1.1015", "1.1009", "1.1012"),)
    elif rule == "S2":
        d1 = (
            ("1.217", "1.230", "1.210", "1.214"),
            ("1.214", "1.220", "1.200", "1.204"),
        )
        h4 = (
            ("1.211", "1.216", "1.201", "1.206"),
            ("1.206", "1.209", "1.195", "1.199"),
        )
        h1 = (
            ("1.2000", "1.2019", "1.1998", "1.2010"),
            ("1.2010", "1.2007", "1.1996", "1.2000"),
            ("1.2000", "1.2005", "1.1995", "1.1999"),
            ("1.1999", "1.2004", "1.1992", "1.1996"),
        )
        seed = (("1.1999", "1.2001", "1.1996", "1.1998"),)
    else:
        raise ValueError("P019_ONLY_SYNTHETIC_B2_S2_CASES")
    # S2 H1 bar #2 is deliberately adjusted to physically consistent OHLC:
    # high must be >= open and close; the fixture is synthetic, not market data.
    if rule == "S2":
        h1 = tuple((a, max(Decimal(b), Decimal(a), Decimal(d)).__str__(),
                    c, d) for a, b, c, d in h1)
    prior_window, _, trigger = case(rule)
    # Rebuild the two M15 trigger bars in the same explicit SIM provider,
    # SIM calendar and SIM stream as all derived source series.
    synthetic_trigger: list[MarketBar] = []
    for i, original in enumerate(prior_window):
        end = START + timedelta(minutes=15 * (i + 1))
        known = end + timedelta(seconds=1)
        synthetic_trigger.append(replace(
            original,
            key=replace(original.key, calendar_version="SIM:UTC-CLOSED",
                        aggregation_version="SIM:OHLC-TR"),
            observation=replace(
                original.observation, provider_id="SIM:P019-FAKE",
                stream_id="SIM:M15",
                first_known_utc=known, retrieved_at_utc=known,
            ),
            first_known_utc=known,
        ))
    bars = SyntheticMultiTfBars(
        daily=_make_series(Timeframe.D1, d1),
        four_hour=_make_series(Timeframe.H4, h4),
        hourly=_make_series(Timeframe.H1, h1),
        micro_seed_m15=_make_series(Timeframe.M15, seed),
        trigger_m15=(synthetic_trigger[0], synthetic_trigger[1]),
    )
    derive = SyntheticDerivationParameters(
        version="SIM:P019-UNAPPROVED-CTX",
        atr_h1_periods=3, h1_zone_lookback=3,
        zone_width_atr_multiple=Decimal("0.3"),
    )
    return bars, derive, trigger


def evaluate_case(rule: str) -> DerivedResearchReceipt:
    bars, d, p = case_from_closed_bars(rule)
    return derive_and_evaluate_b2_s2(
        rule, bars, d, p, bars.trigger_m15[-1].first_known_utc +
        timedelta(seconds=1), origin_event_id="SIM:P019-" + rule,
    )


def main() -> None:
    cases = [("B2", CandidateAction.BUY), ("S2", CandidateAction.SELL)]
    observed: list[str] = []
    for rule, expected in cases:
        receipt = evaluate_case(rule)
        if (receipt.signal.action is not expected or
                receipt.signal.stage.value != "UNVERIFIED" or
                receipt.signal.original_forex_numerical_parity or
                receipt.original_forex_source_signal_parity or
                receipt.may_send_confirmed_signal or receipt.can_trade or
                receipt.provider_requests != 0 or
                receipt.drive_market_cache_writes != 0):
            raise ValueError("P019_INVALID_SYNTHETIC_DERIVATION_OR_AUTHORITY")
        observed.append(receipt.signal.action.value)
    print("MFX_A04_P19_CAUSAL_MULTI_TF_DERIVATION_PASS")
    print("MFX_A04_P19_RECEIPT " + json.dumps({
        "rules": ["B2", "S2"], "synthetic_actions": observed,
        "derived_from_closed_bars": ["D1", "H4", "H1", "M15"],
        "h1_atr_uses_prior_close": True,
        "structural_method": "2_BAR_EXTREMA_PROXY_NOT_CAUSAL_SWING_PIVOTS",
        "parameter_approval": False, "actual_forex_1to1_signal_parity": False,
        "confirmed_alerts": 0, "broker_orders": 0,
        "provider_calls": 0, "drive_market_cache_writes": 0,
        "release_ready": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()

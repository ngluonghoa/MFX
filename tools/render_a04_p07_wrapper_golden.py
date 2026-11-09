"""A04/P0.7: render identical wrapper+direct observations from one root.

Run this UNCHANGED script once with exact frozen Forex PYTHONPATH and once
with MFX src PYTHONPATH in GitHub Actions. No runtime plugin/real provider.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Callable

from tools.render_golden_contract import record
from tools.a04_p07_readonly_wrappers import (
    readonly_quote, readonly_bar, readonly_asof, readonly_ema,
    readonly_ema_recompute, readonly_catalog_counts,
    readonly_catalog_validate,
)

SCOPE = "CI_ONLY_EXISTING_PURE_SOURCE_FUNCTIONS_NO_ADAPTER_RUNTIME"


def render(source_root: Path) -> dict[str, Any]:
    import forex_trading
    from forex_trading.cache_indicators import ema_full, ema_recompute
    from forex_trading.catalog import ZONES, catalog_counts, validate_catalog
    from forex_trading.market_data import (
        BarCoverage, BarLifecycle, BarSide, MarketBar, MarketBarKey,
        Observation, SourceQuality, Timeframe, evaluate_closed_bar,
        select_asof_revision,
    )
    from forex_trading.model import ActionIntent, ZoneDefinition, ZonePurpose
    from forex_trading.quotes import (
        Quote, QuoteQuality, indicative_price,
    )
    expected_root = (source_root.resolve() / "forex_trading" / "__init__.py")
    if Path(forex_trading.__file__).resolve() != expected_root:
        raise ValueError("A04P07_WRONG_FOREX_PACKAGE_ROOT")

    t = datetime(2026, 11, 7, tzinfo=timezone.utc)
    minute = timedelta(minutes=1)
    scenarios: list[dict[str, Any]] = []

    def paired(
        name: str, wrapper_action: Callable[[], Any],
        original_action: Callable[[], Any],
        *, error: type[Exception] | None = None,
    ) -> None:
        first: list[dict[str, Any]] = []
        second: list[dict[str, Any]] = []
        record(first, name, wrapper_action, expected_error=error)
        record(second, name, original_action, expected_error=error)
        if first != second:
            raise ValueError("A04P07_WRAPPER_VS_DIRECT_SEMANTIC_DRIFT:" + name)
        scenarios.append(first[0])

    quote = Quote("SYNTH_ONLY", "REV-A", t, t + minute,
                  Decimal("1.1001"), Decimal("1.1003"),
                  QuoteQuality.VERIFIED)
    for intent in ActionIntent:
        paired(
            "quote." + intent.value.lower(),
            lambda intent=intent: readonly_quote(
                quote, intent, t + 2 * minute, 5 * minute),
            lambda intent=intent: indicative_price(
                quote, intent, t + 2 * minute, 5 * minute),
        )
    quote_errors: tuple[tuple[str, Quote, datetime, timedelta], ...] = (
        ("future_known", quote, t, 5 * minute),
        ("stale", quote, t + 30 * minute, 5 * minute),
        ("quality_unverified", replace(
            quote, quality=QuoteQuality.UNVERIFIED), t + 2 * minute, 5 * minute),
        ("zero_age", quote, t + 2 * minute, timedelta(0)),
    )
    for name, q, when, age in quote_errors:
        paired(
            "quote.reject_" + name,
            lambda q=q, when=when, age=age:
                readonly_quote(q, ActionIntent.ENTRY_LONG, when, age),
            lambda q=q, when=when, age=age:
                indicative_price(q, ActionIntent.ENTRY_LONG, when, age),
            error=ValueError,
        )

    def bar(
        *, timeframe: Timeframe = Timeframe.M15,
        side: BarSide = BarSide.BID,
        revision: int = 1,
        known: datetime | None = None,
    ) -> MarketBar:
        length = 5 if timeframe is Timeframe.M5 else 15
        end = t + timedelta(minutes=length)
        observation_known = known if known is not None else end + minute
        return MarketBar(
            MarketBarKey("EURUSD-SYNTH", timeframe, t, end,
                         "UTC-CALENDAR-V1", "AGG-V1", side),
            Observation(
                "SYNTH_ONLY", "SYNTH-STREAM", "NO_NETWORK",
                "REV-" + str(revision), "a"*64, observation_known,
                observation_known, "UTC", "NO_VENDOR_RIGHTS",
            ),
            revision, observation_known, Decimal("1.10"),
            Decimal("1.20"), Decimal("1.00"), Decimal("1.15"),
            BarLifecycle.CLOSED, BarCoverage.COMPLETE,
            SourceQuality.VERIFIED,
        )
    m15 = bar()
    m5 = bar(timeframe=Timeframe.M5)
    bars: tuple[
        tuple[str, MarketBar | None, datetime, bool, datetime | None],
        ...,
    ] = (
        ("m15_verified", m15, t + 20 * minute, False, None),
        ("m15_not_yet_known", m15, t + 15 * minute, False, None),
        ("m15_open", replace(
            m15, lifecycle=BarLifecycle.OPEN), t + 20 * minute, False, None),
        ("m15_partial", replace(
            m15, coverage=BarCoverage.PARTIAL), t + 20 * minute, False, None),
        ("m15_mid_reference", bar(
            side=BarSide.MID), t + 20 * minute, False, None),
        ("m5_default_blocked", m5, t + 20 * minute, False, None),
        ("m5_prior_htf", m5, t + 20 * minute, True, t + 4 * minute),
        ("m5_future_htf", m5, t + 20 * minute, True, t + 17 * minute),
        ("m15_wrong_m5_flag", m15, t + 20 * minute, True, None),
        ("missing_bar", None, t + 20 * minute, False, None),
    )
    for name, sample, when, enabled, htf in bars:
        paired(
            "bar." + name,
            lambda sample=sample, when=when, enabled=enabled, htf=htf:
                readonly_bar(sample, when,
                             conditional_m5_early_enabled=enabled,
                             htf_context_first_known_utc=htf),
            lambda sample=sample, when=when, enabled=enabled, htf=htf:
                evaluate_closed_bar(sample, when,
                                    conditional_m5_early_enabled=enabled,
                                    htf_context_first_known_utc=htf),
        )

    corrected = bar(revision=2, known=t + 22 * minute)
    asof: tuple[tuple[str, tuple[MarketBar, ...], datetime, type[Exception] | None], ...] = (
        ("before_revision", (m15, corrected), t + 20 * minute, None),
        ("after_revision", (m15, corrected), t + 30 * minute, None),
        ("before_any", (m15, corrected), t, None),
        ("duplicate_revision", (m15, replace(
            m15, first_known_utc=t + 17 * minute)), t + 30 * minute, ValueError),
    )
    for name, revisions, when, error in asof:
        paired(
            "asof." + name,
            lambda revisions=revisions, when=when:
                readonly_asof(revisions, when),
            lambda revisions=revisions, when=when:
                select_asof_revision(revisions, when),
            error=error,
        )

    closes = (
        Decimal("1.100"), Decimal("1.200"),
        Decimal("1.150"), Decimal("1.250"),
    )
    full: tuple[tuple[str, tuple[Decimal, ...], int, type[Exception] | None], ...] = (
        ("empty", (), 3, None),
        ("single", (closes[0],), 1, None),
        ("series", closes, 3, None),
        ("invalid_period", closes, 0, ValueError),
        ("invalid_close", (Decimal("NaN"),), 3, ValueError),
    )
    for name, series, period, error in full:
        paired(
            "ema." + name,
            lambda series=series, period=period:
                readonly_ema(series, period),
            lambda series=series, period=period:
                ema_full(series, period),
            error=error,
        )
    prior = ema_full(closes, 3)
    revised = closes[:2] + (Decimal("1.180"), closes[3])
    for name, series, checkpoint, dirty, error in (
        ("incremental_checkpoint", closes, prior, 4, None),
        ("dirty_tail", revised, prior, 2, None),
        ("invalid_dirty", revised, prior, 10, ValueError),
    ):
        paired(
            "ema." + name,
            lambda series=series, checkpoint=checkpoint, dirty=dirty:
                readonly_ema_recompute(series, 3, checkpoint, dirty),
            lambda series=series, checkpoint=checkpoint, dirty=dirty:
                ema_recompute(series, 3, checkpoint, dirty),
            error=error,
        )

    paired(
        "catalog.counts", lambda: readonly_catalog_counts(ZONES),
        lambda: catalog_counts(ZONES),
    )
    paired(
        "catalog.valid", lambda: readonly_catalog_validate(ZONES),
        lambda: validate_catalog(ZONES),
    )
    paired(
        "catalog.reject_duplicate",
        lambda: readonly_catalog_validate(ZONES + (ZONES[0],)),
        lambda: validate_catalog(ZONES + (ZONES[0],)),
        error=ValueError,
    )
    research = (ZoneDefinition("FX-B9", "RESEARCH_ONLY", ZonePurpose.WATCH_ONLY),)
    paired(
        "catalog.reject_research",
        lambda: readonly_catalog_validate(research),
        lambda: validate_catalog(research),
        error=ValueError,
    )
    if len(scenarios) != 34 or len({x["id"] for x in scenarios}) != 34:
        raise ValueError("A04P07_EXPECT_EXACTLY_34_PURE_CASES")

    return {
        "kind": "MFX_A04_P07_CI_ONLY_SOURCE_WRAPPER_PARITY_V1",
        "scope": SCOPE,
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
        "wrapper_matches_direct_source": True,
        "real_provider_io": False,
        "adapter_runtime_wired": False,
        "numerical_zone_detector_executed": False,
        "tp_sl_engine_executed": False,
        "licensed_data_used": False,
        "may_release_or_trade": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = render(args.source_root)
    args.output.parent.mkdir(exist_ok=True, parents=True)
    args.output.write_text(json.dumps(
        result, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ) + "\n", encoding="utf-8")
    print("MFX_A04_P07_WRAPPER_RENDERED_" + str(result["scenario_count"]))


if __name__ == "__main__":
    main()

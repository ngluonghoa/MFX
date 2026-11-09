"""A04/P0.7: CI-only transparent wrappers for existing pure Forex functions.

This file lives under tools/, OUTSIDE the shipped src/ wheel. It introduces
no adapter loader, provider I/O, broker, model, trade, permissions or signal.
Every wrapper preserves its frozen source function's exceptions and outputs.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Sequence

from forex_trading.cache_indicators import ema_full, ema_recompute
from forex_trading.catalog import catalog_counts, validate_catalog
from forex_trading.market_data import (
    MarketBar, ReadOnlyBarGate, evaluate_closed_bar, select_asof_revision,
)
from forex_trading.model import ActionIntent, ZoneDefinition, ZonePurpose
from forex_trading.quotes import Quote, IndicativePrice, indicative_price


def readonly_quote(
    quote: Quote, intent: ActionIntent, decision_utc: datetime,
    max_age: timedelta,
) -> IndicativePrice:
    """Pass through causal bid/ask reference only; NEVER a fill or signal."""
    return indicative_price(quote, intent, decision_utc, max_age)


def readonly_bar(
    bar: MarketBar | None, decision_utc: datetime,
    *,
    conditional_m5_early_enabled: bool = False,
    htf_context_first_known_utc: datetime | None = None,
) -> ReadOnlyBarGate:
    """Pass through original source's quality gate, never authorizing trade."""
    return evaluate_closed_bar(
        bar, decision_utc,
        conditional_m5_early_enabled=conditional_m5_early_enabled,
        htf_context_first_known_utc=htf_context_first_known_utc,
    )


def readonly_asof(
    revisions: Sequence[MarketBar], decision_utc: datetime,
) -> MarketBar | None:
    """Select only the causal source revision, no provider acquisition."""
    return select_asof_revision(revisions, decision_utc)


def readonly_ema(
    closes: tuple[Decimal, ...], period: int,
) -> tuple[Decimal, ...]:
    """Experimental EMA reference arithmetic, NOT an indicator plugin."""
    return ema_full(closes, period)


def readonly_ema_recompute(
    closes: tuple[Decimal, ...], period: int,
    previous_ema: tuple[Decimal, ...], dirty_index: int,
) -> tuple[Decimal, ...]:
    """Exact source dirty-prefix helper; checkpoint rights NOT verified."""
    return ema_recompute(closes, period, previous_ema, dirty_index)


def readonly_catalog_counts(
    zones: tuple[ZoneDefinition, ...],
) -> dict[ZonePurpose, int]:
    """Taxonomy counts ONLY, not numerical 18-zone signal detection."""
    return catalog_counts(zones)


def readonly_catalog_validate(
    zones: tuple[ZoneDefinition, ...],
) -> None:
    """Taxonomy validation ONLY; no detector or TP/SL execution."""
    return validate_catalog(zones)

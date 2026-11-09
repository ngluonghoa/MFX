"""A04/P0.17: source-native 18-label classification proof in GitHub CI."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json

from forex_trading.catalog import ZONES
from forex_trading.model import ZonePurpose
from mfx_research.zone_catalog_gate import (
    UnverifiedZoneClaim, route_unverified_zone_claims,
)

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)


def main() -> None:
    claims = tuple(
        UnverifiedZoneClaim(
            pair="SIM:EUR_USD", label=zone.label, origin_event_id="SIM:ORIGIN-1",
            first_known_utc=NOW,
        )
        for zone in ZONES
    )
    receipt = route_unverified_zone_claims(claims, NOW)
    counts = Counter(item.purpose for item in receipt.classified)
    expected = {
        ZonePurpose.ENTRY_LONG_CANDIDATE: 7,
        ZonePurpose.ENTRY_SHORT_CANDIDATE: 8,
        ZonePurpose.WATCH_ONLY: 1,
        ZonePurpose.EXIT_LONG_WARNING_ONLY: 2,
    }
    if (counts != expected or len(receipt.classified) != 18
            or len(receipt.candidate_groups) != 2
            or any(group.primary_rule_id is not None
                   for group in receipt.candidate_groups)
            or any(x.signal_confirmed or x.can_trade or
                   x.numerical_predicate_implemented
                   for x in receipt.classified)
            or receipt.actual_confirmed_signals != 0
            or receipt.may_send_buy_sell_alert
            or receipt.may_trade
            or receipt.provider_requests != 0
            or receipt.drive_market_cache_writes != 0):
        raise ValueError("P017_CATALOG_ROUTING_OR_AUTHORITY_MISMATCH")

    print("MFX_A04_P17_FROZEN_18_ZONE_ROUTING_PASS")
    print("MFX_A04_P17_RECEIPT " + json.dumps({
        "catalog_labels": 18, "long_candidates": 7, "short_candidates": 8,
        "watch_only": 1, "exit_long_warning_only": 2,
        "directional_claim_groups_same_origin": len(receipt.candidate_groups),
        "actual_numeric_detectors": receipt.callable_numeric_detectors,
        "confirmed_signals": receipt.actual_confirmed_signals,
        "can_send_buy_sell_alert": receipt.may_send_buy_sell_alert,
        "provider_requests": receipt.provider_requests,
        "drive_market_cache_writes": receipt.drive_market_cache_writes,
        "can_trade": receipt.may_trade,
        "original_forex_strategy_parity_proven": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()

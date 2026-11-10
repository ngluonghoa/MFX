"""Hosted Cloud-only A04/P0.31: 22-zone SIM role grouping, never alerts."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from mfx_research.p031_sim_22_zone_router import (
    SimZoneLabelClaim, route_sim_22_zone_labels,
)


def main() -> None:
    t = datetime(2026, 11, 10, 4, tzinfo=timezone.utc)

    def make(label: str, origin: str) -> SimZoneLabelClaim:
        return SimZoneLabelClaim(
            instrument_version="SIM:EURUSD",
            calendar_version="SIM:UTC_RESEARCH",
            origin_event_id=origin,
            provider_id="SIM:OFFLINE_CANDLES",
            stream_id="SIM:M15_CLOSED",
            label=label,
            closed_candle_end_utc=t,
            first_known_utc=t + timedelta(seconds=1),
            retrieved_at_utc=t + timedelta(seconds=2),
        )

    claims = (
        make("B2", "SIM:UP_EVENT"), make("B5", "SIM:UP_EVENT"),
        make("B7", "SIM:UP_EVENT"), make("FX-B10", "SIM:UP_EVENT"),
        make("S2", "SIM:DOWN_EVENT"), make("FX-S11", "SIM:DOWN_EVENT"),
        make("B3", "SIM:CONFLICT_EVENT"),
        make("S4", "SIM:CONFLICT_EVENT"),
    )
    receipt = route_sim_22_zone_labels(
        claims, t + timedelta(seconds=5),
    )
    by_origin = {x.origin_event_id: x for x in receipt.events}
    if (receipt.mfx_design_labels != 22 or len(receipt.events) != 3
            or len(receipt.classified) != len(claims)
            or by_origin["SIM:UP_EVENT"].display_outcome
            != "UNVERIFIED_BUY_RESEARCH_GROUP_ONLY"
            or by_origin["SIM:DOWN_EVENT"].display_outcome
            != "UNVERIFIED_SELL_RESEARCH_GROUP_ONLY"
            or by_origin["SIM:CONFLICT_EVENT"].display_outcome
            != "CONFLICT_NO_SIGNAL"
            or receipt.confirmed_buy_sell_signals != 0
            or receipt.numeric_entry_predicates_approved != 0
            or receipt.broker_orders != 0
            or receipt.may_send_live_alerts
            or receipt.may_trade):
        raise RuntimeError("P031_ROLE_OR_CROSS_EVENT_SAFETY_GATE_FAILED")
    if any(row.action != "NO_SIGNAL" or row.may_publish
           for row in receipt.classified):
        raise RuntimeError("P031_RESEARCH_ONLY_ACTION_DENIAL_FAILED")
    print("MFX_A04_P31_22_ZONE_SIM_ROUTER_NO_SIGNAL_PASS")
    print("MFX_A04_P31_RECEIPT " + json.dumps({
        "design_labels": receipt.mfx_design_labels,
        "research_claims": len(receipt.classified),
        "unique_research_opportunities": len(receipt.events),
        "candidate_entry_design": (
            receipt.mfx_entry_long_design_candidates
            + receipt.mfx_entry_short_design_candidates),
        "watch_labels": receipt.mfx_watch_only_labels,
        "exit_warning_labels": receipt.mfx_exit_warning_labels,
        "numeric_rules_approved": receipt.numeric_entry_predicates_approved,
        "confirmed_signals": receipt.confirmed_buy_sell_signals,
        "may_publish": receipt.may_send_live_alerts,
        "provider_calls": receipt.live_provider_calls,
        "drive_market_cache_writes": receipt.real_drive_quote_cache_writes,
        "broker_orders": receipt.broker_orders,
        "may_release": receipt.release_ready,
        "observed_sim_outcomes": [
            {"origin": group.origin_event_id,
             "outcome": group.display_outcome,
             "labels": list(group.matched_labels),
             "action": group.action}
            for group in receipt.events
        ],
    }, sort_keys=True))


if __name__ == "__main__":
    main()

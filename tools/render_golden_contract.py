"""A01/P0.2 deterministic read-only golden contract renderer.

Run this same script against the frozen Forex source checkout AND MFX checkout
using separate PYTHONPATH values on GitHub-hosted CI. No vendor data, network
connection, broker, system clock, paid service or nonstdlib dependencies.
"""
from __future__ import annotations

import argparse
from dataclasses import fields, is_dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
import json
from pathlib import Path
from typing import Any, Callable


def stable(value: Any) -> Any:
    """Serialize typed domain outputs with no incidental paths or repr addresses."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: stable(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, (tuple, list)):
        return [stable(v) for v in value]
    if isinstance(value, dict):
        return {str(stable(k)): stable(v) for k, v in sorted(
            value.items(), key=lambda item: str(stable(item[0]))
        )}
    if isinstance(value, (str, bool, int, float)) or value is None:
        return value
    raise TypeError("UNSUPPORTED_GOLDEN_OUTPUT_TYPE:" + type(value).__name__)


def record(
    results: list[dict[str, Any]],
    key: str,
    action: Callable[[], Any],
    *,
    expected_error: type[Exception] | None = None,
) -> None:
    if any(x["id"] == key for x in results):
        raise ValueError("DUPLICATE_GOLDEN_SCENARIO")
    try:
        result = action()
    except (ValueError, TypeError) as err:
        if expected_error is None or type(err) is not expected_error:
            raise
        outcome = {"error_type": type(err).__name__, "reason": str(err)}
    else:
        if expected_error is not None:
            raise AssertionError("EXPECTED_GOLDEN_ERROR_DID_NOT_OCCUR:" + key)
        outcome = {"value": stable(result)}
    results.append({"id": key, "outcome": outcome})


def render(source_root: Path) -> dict[str, Any]:
    """Build synthetic deterministic scenarios from the selected import root."""
    import forex_trading
    from forex_trading.catalog import ZONES, catalog_counts, validate_catalog
    from forex_trading.model import (
        ActionIntent, Direction, Horizon, SignalDisplay, SignalStage,
        ZoneDefinition, ZonePurpose,
    )
    from forex_trading.quotes import (
        Quote, QuoteQuality, indicative_price,
    )
    from forex_trading.pipeline import (
        STEPS, PipelineSnapshot, StepStatus, can_publish_full_analysis,
    )
    from forex_trading.scan_contract import ScanMode, plan_scan_selection
    from forex_trading.scan_selection import plan_scan_selection as legacy_scan
    from forex_trading.market_data import (
        BarCoverage, BarLifecycle, BarSide, MarketBar, MarketBarKey,
        Observation, SourceQuality, Timeframe, evaluate_closed_bar,
        select_asof_revision,
    )
    from forex_trading.cache_core import (
        CachePartition, CandleSnapshot, IncrementalPolicy,
        SourceHeadClaim, plan_incremental_refresh, reconcile_closed_delta,
    )
    from forex_trading.cache_dependency import (
        CacheLayer, CacheNode, dirty_dependency_closure,
    )
    from forex_trading.versioning import ExecutionProfile, assess_rollback

    expected_module = (
        source_root.resolve() / "forex_trading" / "__init__.py"
    )
    if Path(forex_trading.__file__).resolve() != expected_module:
        raise RuntimeError("WRONG_PACKAGE_IMPORT_ROOT")

    t = datetime(2026, 11, 7, tzinfo=timezone.utc)
    minute = timedelta(minutes=1)
    results: list[dict[str, Any]] = []

    # Fixed approved design catalog. This does not execute any detector.
    record(results, "catalog.labels_and_purposes", lambda: [
        (z.label, z.family, z.purpose.value) for z in ZONES
    ])
    record(results, "catalog.counts", lambda: {
        k.value: v for k, v in catalog_counts(ZONES).items()
    })
    record(results, "catalog.reject_duplicate", lambda: validate_catalog(
        (ZONES[0], ZONES[0])
    ), expected_error=ValueError)
    record(results, "catalog.reject_research_fx_b9", lambda: validate_catalog(
        (ZoneDefinition("FX-B9", "RESEARCH_ONLY", ZonePurpose.WATCH_ONLY),)
    ), expected_error=ValueError)

    # Three selectable scan modes never authorize source calls or trading.
    universe = tuple(f"TESTPAIR{i:02d}" for i in range(20))
    for mode, pairs in (
        (ScanMode.SINGLE, ("TESTPAIR03",)),
        (ScanMode.CUSTOM, ("TESTPAIR12", "TESTPAIR00", "TESTPAIR11")),
        (ScanMode.ALL, ()),
    ):
        record(results, f"scan.{mode.value.lower()}",
               lambda mode=mode, pairs=pairs: plan_scan_selection(
                   universe, mode, pairs
               ))
    record(results, "scan.legacy_export_same", lambda:
           legacy_scan is plan_scan_selection)
    record(results, "scan.reject_unknown_pair", lambda: plan_scan_selection(
        universe, ScanMode.SINGLE, ("EURUSD",)
    ), expected_error=ValueError)
    record(results, "scan.reject_duplicate_request", lambda: plan_scan_selection(
        universe, ScanMode.CUSTOM, ("TESTPAIR00", "TESTPAIR00")
    ), expected_error=ValueError)
    record(results, "scan.reject_custom_one", lambda: plan_scan_selection(
        universe, ScanMode.CUSTOM, ("TESTPAIR00",)
    ), expected_error=ValueError)

    quote = Quote("SYNTH_ONLY", "REV-1", t, t + minute,
                  Decimal("1.1001"), Decimal("1.1003"),
                  QuoteQuality.VERIFIED)
    for action in ActionIntent:
        record(results, f"quote.{action.value.lower()}", lambda action=action:
               indicative_price(quote, action, t + 2 * minute,
                                5 * minute))
    record(results, "quote.reject_future_known", lambda:
           indicative_price(quote, ActionIntent.ENTRY_LONG, t,
                            5 * minute), expected_error=ValueError)
    record(results, "quote.reject_stale", lambda:
           indicative_price(quote, ActionIntent.ENTRY_SHORT, t + 20 * minute,
                            5 * minute), expected_error=ValueError)
    record(results, "quote.reject_unverified", lambda:
           indicative_price(replace(quote, quality=QuoteQuality.UNVERIFIED),
                            ActionIntent.EXIT_SHORT, t + 2 * minute,
                            5 * minute), expected_error=ValueError)
    record(results, "quote.reject_crossed_bid_ask", lambda:
           replace(quote, bid=Decimal("1.101")), expected_error=ValueError)

    record(results, "signal.verified_early", lambda: SignalDisplay(
        Direction.LONG, Horizon.FAST, SignalStage.EARLY_SIGNAL,
        "B1", True, "SYNTHETIC_GOOD_SOURCE_NOT_TRADE_PERMISSION"
    ))
    record(results, "signal.short_unverified", lambda: SignalDisplay(
        Direction.SHORT, Horizon.SWING, SignalStage.UNVERIFIED,
        None, False, "NO_LICENSED_SOURCE"
    ))
    record(results, "signal.reject_early_without_source", lambda:
           SignalDisplay(Direction.LONG, Horizon.FAST,
                         SignalStage.EARLY_SIGNAL, "B1", False, "NOT_VERIFIED"),
           expected_error=ValueError)
    record(results, "signal.reject_confirm_without_zone", lambda:
           SignalDisplay(Direction.SHORT, Horizon.SWING,
                         SignalStage.CONFIRMED_SIGNAL, None, True, "NO_ZONE"),
           expected_error=ValueError)
    full = PipelineSnapshot(tuple((step, StepStatus.COMPLETE) for step in STEPS))
    blocked = PipelineSnapshot(tuple((step,
        StepStatus.BLOCKED if i == 5 else StepStatus.COMPLETE)
        for i, step in enumerate(STEPS)))
    record(results, "pipeline.complete_read_only", lambda:
           (full, can_publish_full_analysis(full)))
    record(results, "pipeline.blocked", lambda:
           (blocked, can_publish_full_analysis(blocked)))
    record(results, "pipeline.reject_wrong_stage_count", lambda:
           PipelineSnapshot(full.step_states[:-1]), expected_error=ValueError)

    # Bars are invented test fixtures, not Twelve Data or broker executable.
    def observation(idx: int, revision: int = 1, known: datetime | None = None):
        at = known if known is not None else t + (idx + 1) * 5 * minute + timedelta(seconds=1)
        return Observation(
            provider_id="SYNTH_ONLY", stream_id="bid-synthetic",
            endpoint="NO_PROVIDER_REQUEST", revision_id=f"rev-{revision}",
            raw_sha256=(str(revision % 10) * 64), first_known_utc=at,
            retrieved_at_utc=at, source_timezone_policy="UTC-v1",
            license_scope_claim="NO_EXTERNAL_RIGHTS",
        )

    def bar(idx: int, *, tf: Timeframe = Timeframe.M5,
            side: BarSide = BarSide.BID, revision: int = 1,
            known: datetime | None = None, close: str = "1.14"):
        duration = {Timeframe.M5: 5, Timeframe.M15: 15}[tf]
        start = t + idx * duration * minute
        end = start + duration * minute
        at = known if known is not None else end + timedelta(seconds=1)
        return MarketBar(
            MarketBarKey("EURUSD-SYNTH-V1", tf, start, end, "UTC-CALENDAR-V1",
                         "AGG-V1", side),
            observation(idx, revision, at), revision, at,
            Decimal("1.10"), Decimal("1.20"), Decimal("1.00"),
            Decimal(close), BarLifecycle.CLOSED,
            BarCoverage.COMPLETE, SourceQuality.VERIFIED,
        )

    m15 = bar(0, tf=Timeframe.M15)
    record(results, "bar.m15_closed", lambda:
           evaluate_closed_bar(m15, t + 20 * minute))
    record(results, "bar.m15_not_yet_known", lambda:
           evaluate_closed_bar(m15, t + 15 * minute))
    record(results, "bar.m15_open_provisional", lambda:
           evaluate_closed_bar(replace(m15, lifecycle=BarLifecycle.OPEN),
                               t + 20 * minute))
    record(results, "bar.m15_mid_reference_only", lambda:
           evaluate_closed_bar(bar(0, tf=Timeframe.M15, side=BarSide.MID),
                               t + 20 * minute))
    record(results, "bar.m5_default_arm_blocked", lambda:
           evaluate_closed_bar(bar(0), t + 20 * minute))
    record(results, "bar.m5_prior_htf_early", lambda:
           evaluate_closed_bar(bar(0), t + 20 * minute,
                               conditional_m5_early_enabled=True,
                               htf_context_first_known_utc=t + 4 * minute))
    record(results, "bar.m5_future_htf_blocked", lambda:
           evaluate_closed_bar(bar(0), t + 20 * minute,
                               conditional_m5_early_enabled=True,
                               htf_context_first_known_utc=t + 17 * minute))
    updated = bar(0, tf=Timeframe.M15, revision=2,
                  known=t + 22 * minute, close="1.15")
    record(results, "bar.asof_before_correction", lambda:
           select_asof_revision((m15, updated), t + 20 * minute))
    record(results, "bar.asof_after_correction", lambda:
           select_asof_revision((m15, updated), t + 30 * minute))
    record(results, "bar.reject_incomplete", lambda:
           evaluate_closed_bar(replace(m15, coverage=BarCoverage.PARTIAL),
                               t + 20 * minute))

    partition = CachePartition(
        "SYNTH_ONLY", "DEMO-NOT-BROKER", "EURUSD-SYNTH-V1",
        BarSide.BID, Timeframe.M5, "UTC-CALENDAR-V1", "AGG-V1",
        "UTC-v1", "NO_REAL_RIGHTS", "SCHEMA-V1",
    )
    snapshot = CandleSnapshot(partition, tuple(bar(i) for i in range(3)),
                              t + 16 * minute, "SYNTH-HEAD-1")
    policy = IncrementalPolicy(2, 5 * minute)
    record(results, "cache.initial_snapshot", lambda:
           {"fingerprint": snapshot.fingerprint,
            "last_closed": snapshot.last_closed_end_utc,
            "partition": partition.fingerprint})
    record(results, "cache.delta_refresh", lambda:
           plan_incremental_refresh(snapshot, policy, t + 20 * minute,
                                    supports_bounded_range=True))
    record(results, "cache.no_range_endpoint", lambda:
           plan_incremental_refresh(snapshot, policy, t + 20 * minute,
                                    supports_bounded_range=False))
    head = SourceHeadClaim(partition.fingerprint, "SYNTH-HEAD-1",
                           t + 15 * minute, t + 17 * minute)
    record(results, "cache.same_unverified_head", lambda:
           plan_incremental_refresh(snapshot, policy, t + 20 * minute,
                                    supports_bounded_range=True, head=head))
    record(results, "cache.append", lambda:
           reconcile_closed_delta(snapshot, (bar(3),), t + 21 * minute,
                                  new_source_head_claim="SYNTH-HEAD-2"))
    record(results, "cache.revise", lambda:
           reconcile_closed_delta(snapshot, (
               bar(1, revision=2, known=t + 19 * minute, close="1.16"),
           ), t + 21 * minute, new_source_head_claim="SYNTH-HEAD-R2"))
    record(results, "cache.reject_same_revision_change", lambda:
           reconcile_closed_delta(snapshot, (bar(1, close="1.17"),),
                                  t + 21 * minute,
                                  new_source_head_claim="SYNTH-HEAD-1"),
           expected_error=ValueError)

    chain = [
        CacheNode(f"EUR-{i}", CacheLayer(i), "EURUSD", "ALG-V1",
                  "PARAM-V1", () if i == 1 else (f"EUR-{i-1}",))
        for i in range(1, 6)
    ]
    chain += [
        CacheNode(f"GBP-{i}", CacheLayer(i), "GBPUSD", "ALG-V1",
                  "PARAM-V1", () if i == 1 else (f"GBP-{i-1}",))
        for i in range(1, 6)
    ]
    record(results, "cache.dependency_closure_eurusd", lambda:
           dirty_dependency_closure(tuple(chain), ("EUR-1",)))
    record(results, "cache.dependency_closure_empty", lambda:
           dirty_dependency_closure(tuple(chain), ()))
    record(results, "cache.reject_unknown_changed_node", lambda:
           dirty_dependency_closure(tuple(chain), ("AUD-99",)),
           expected_error=ValueError)

    profile = ExecutionProfile(
        "CODE-LOCKED", "DEPS-LOCKED", "RULES-18", "PARAM-NONE",
        "PROVIDER-NO-LICENCE", "DATA-SYNTH", "UTC-CALENDAR", "BID-ASK",
        "COST-UNQUALIFIED", "RISK-NOT-QUALIFIED", "SCHEMA-0", "REPORT-0",
    )
    record(results, "version.profile_fingerprint", lambda: profile.fingerprint)
    record(results, "version.rollback_matching", lambda:
           assess_rollback(replace(profile, rule_ref="RULES-EXPERIMENT"), profile))
    record(results, "version.rollback_source_and_quote_changed", lambda:
           assess_rollback(replace(
               profile, provider_ref="OTHER", bid_ask_basis_ref="MID",
               data_revision_ref="DIFFERENT", persistence_schema_ref="SCHEMA-1",
           ), profile))
    record(results, "version.reject_empty_profile_ref", lambda:
           replace(profile, provider_ref=""), expected_error=ValueError)

    if len(results) < 40:
        raise AssertionError("INSUFFICIENT_GOLDEN_CASE_COVERAGE")
    return {
        "kind": "MFX_A01_SYNTHETIC_GOLDEN_CONTRACT_V1",
        "schema": 1,
        "scenario_count": len(results),
        "scope": "READ_ONLY_SYNTHETIC_CONTRACTS_NO_DETECTOR_EXECUTION",
        "may_trade": False,
        "is_oos_backtest": False,
        "scenarios": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    proof = render(args.source_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(proof, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        + "\n", encoding="utf-8",
    )
    print("MFX_A01_GOLDEN_SNAPSHOT_GENERATED " + str(proof["scenario_count"]))


if __name__ == "__main__":
    main()

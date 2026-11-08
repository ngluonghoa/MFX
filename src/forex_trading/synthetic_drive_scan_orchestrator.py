"""P2.1-B: isolated synthetic-only Forex mixed-scope cache orchestrator.

Reads caller-provided fixture snapshots; never talks to providers or Google
Drive, never grants data rights, and never turns a synthetic scan into a trade.
The store does not depend on this module; legacy imports remain re-exported.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from .cache_core import (
    CandleSnapshot, IncrementalPolicy, RefreshMode,
    plan_incremental_refresh, reconcile_closed_delta,
)
from .market_data import BarSide, Timeframe
from .quotes import ensure_utc
from .scan_contract import ScanMode, ScanSelection, plan_scan_selection
from .synthetic_drive_cache_store import SyntheticDriveCacheStaging


@dataclass(frozen=True, slots=True)
class MixedScanResult:
    selection: ScanSelection
    bootstrapped_streams: int
    delta_plans: int
    source_rows_selected_from_oracle: int
    appended: int
    revised: int
    unchanged_streams: int
    simulated_new_chunk_writes: int
    unchanged_existing_streams: int
    # Explicitly zero: fixture row counts are NOT upstream HTTP metrics.
    actual_drive_api_calls: int = 0
    actual_vendor_api_calls: int = 0
    may_store_real_market_data: bool = False
    may_trade: bool = False


def run_mixed_scope_synthetic_drive_scan(
    cache: SyntheticDriveCacheStaging,
    oracle_by_pair: Mapping[str, tuple[CandleSnapshot, ...]],
    universe: tuple[str, ...],
    mode: ScanMode,
    policy: IncrementalPolicy,
    decision_utc: datetime,
    *,
    requested_pairs: tuple[str, ...] = (),
    timeframes: tuple[Timeframe, ...] = (
        Timeframe.M5, Timeframe.M15, Timeframe.H1,
        Timeframe.H4, Timeframe.D1,
    ),
) -> MixedScanResult:
    """Read only selected partitions; keep valid previously committed history.

    For first selected appearance, bootstrap from synthetic oracle; subsequent
    scans query the oracle only over bounded overlap+new windows. For safety
    NO self-declared source-head skip: head=None forces recheck of overlap.
    A real source might revise outside this overlap; remain UNVERIFIED.
    """
    if not isinstance(cache, SyntheticDriveCacheStaging):
        raise TypeError("SyntheticDriveCacheStaging required")
    if not isinstance(oracle_by_pair, Mapping):
        raise TypeError("Typed synthetic oracle mapping required")
    if not isinstance(policy, IncrementalPolicy):
        raise TypeError("IncrementalPolicy required")
    ensure_utc(decision_utc, "decision_utc")
    if (not isinstance(timeframes, tuple) or not timeframes
            or any(not isinstance(tf, Timeframe) for tf in timeframes)
            or len(set(timeframes)) != len(timeframes)):
        raise ValueError("INVALID_EXPECTED_TIMEFRAMES")
    selection = plan_scan_selection(universe, mode, requested_pairs)

    # Preflight selected inputs BEFORE committing any partition: absent BID,
    # ASK or TF must fail closed instead of leaving a partial success.
    selected_groups: list[tuple[CandleSnapshot, ...]] = []
    expected = {(tf, side) for tf in timeframes for side in (BarSide.BID, BarSide.ASK)}
    for pair in selection.selected_pairs:
        if pair not in oracle_by_pair:
            raise ValueError("SELECTED_PAIR_NOT_IN_SYNTHETIC_ORACLE")
        snapshots = oracle_by_pair[pair]
        if not isinstance(snapshots, tuple) or any(
            not isinstance(snapshot, CandleSnapshot) for snapshot in snapshots
        ):
            raise TypeError("PAIR_SNAPSHOTS_MUST_BE_TYPED_IMMUTABLE")
        keys = [(s.partition.timeframe, s.partition.side) for s in snapshots]
        if (len(keys) != len(expected) or len(set(keys)) != len(keys)
                or set(keys) != expected
                or any(s.partition.instrument_version != pair for s in snapshots)):
            raise ValueError("SELECTED_PAIR_BID_ASK_TF_INCOMPLETE_OR_DUPLICATE")
        if any(s.checked_at_utc > decision_utc for s in snapshots):
            raise ValueError("FUTURE_SOURCE_ORACLE")
        selected_groups.append(snapshots)

    bootstrap = delta = rows = appended = revised = unchanged = writes = unchanged_old = 0
    for snapshots in selected_groups:
        for oracle in snapshots:
            existing = cache.load(oracle.partition.fingerprint)
            active_history = cache.manifest_history(oracle.partition.fingerprint)
            expected_digest = active_history[-1].manifest_sha256 if active_history else None
            if existing is None:
                if not oracle.closed_bars:
                    raise ValueError("EMPTY_SYNTHETIC_BOOTSTRAP")
                bootstrap += 1
                rows += len(oracle.closed_bars)
                if cache.stage_and_commit(
                    oracle, decision_utc, expected_active_sha256=None
                ):
                    writes += 1
                continue
            plan = plan_incremental_refresh(
                existing, policy, decision_utc,
                supports_bounded_range=True, head=None,
            )
            if plan.mode is not RefreshMode.DELTA_WINDOW:
                raise ValueError("NO_BOUNDED_DELTA_AVAILABLE")
            delta += 1
            bounded_rows = tuple(
                bar for bar in oracle.closed_bars
                if bar.key.bar_start_utc >= plan.from_utc
            )
            rows += len(bounded_rows)
            changed = reconcile_closed_delta(
                existing, bounded_rows, decision_utc,
                new_source_head_claim=oracle.source_head_claim,
            )
            appended += changed.appended
            revised += changed.revised
            if changed.appended or changed.revised:
                if cache.stage_and_commit(
                    changed.snapshot, decision_utc,
                    expected_active_sha256=expected_digest,
                ):
                    writes += 1
            else:
                unchanged += 1
                unchanged_old += 1
    return MixedScanResult(
        selection, bootstrap, delta, rows, appended, revised, unchanged,
        writes, unchanged_old,
    )

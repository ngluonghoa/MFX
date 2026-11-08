"""M2/P0.7 selectable Forex scan scope; deterministic SYNTHETIC-only routing.

Select instruments BEFORE cache/delta planning. This wrapper does not fetch
quotes, start a scheduler, modify cache, grant data rights, or trade.
A 20-instrument approved catalog must be supplied externally: this module
does NOT pretend the actual trading universe has been source-qualified.
"""
from dataclasses import dataclass
from datetime import datetime

from .cache_core import IncrementalPolicy
from .scan_contract import ScanMode, ScanSelection, plan_scan_selection
from .quotes import ensure_utc
from .synthetic_scan_workload import (
    SyntheticScanFixture, SyntheticSweepReport, run_synthetic_five_minute_sweep,
)




@dataclass(frozen=True, slots=True)
class SelectedSyntheticScanReport:
    selection: ScanSelection
    sweep: SyntheticSweepReport
    actual_provider_requests: int = 0
    may_run_real_scan: bool = False


def run_selected_synthetic_scan(
    fixtures: tuple[SyntheticScanFixture, ...],
    policy: IncrementalPolicy,
    decision_utc: datetime,
    *,
    universe: tuple[str, ...],
    mode: ScanMode,
    requested_pairs: tuple[str, ...] = (),
    supports_bounded_range: bool = True,
) -> SelectedSyntheticScanReport:
    """Dispatch ONLY selected fixtures into the existing L1 delta planner.

    A real adapter must honor the selection *before* issuing source calls.
    Passing a full in-memory oracle here is test scaffolding, not proof that
    an upstream provider/download would avoid reading unrelated instruments.
    Selected pairs require BID and ASK completeness per timeframe as in the
    underlying sweep. Missing selected pairs fail closed, never disappear.
    """
    selection = plan_scan_selection(universe, mode, requested_pairs)
    ensure_utc(decision_utc, "decision_utc")
    if not isinstance(fixtures, tuple):
        raise TypeError("IMMUTABLE_FIXTURES_REQUIRED")
    if not isinstance(policy, IncrementalPolicy):
        raise TypeError("IncrementalPolicy required")
    if type(supports_bounded_range) is not bool:
        raise TypeError("supports_bounded_range must be bool")

    selected_set = set(selection.selected_pairs)
    by_pair: dict[str, list[SyntheticScanFixture]] = {
        pair: [] for pair in selection.selected_pairs
    }
    for fixture in fixtures:
        if not isinstance(fixture, SyntheticScanFixture):
            raise TypeError("Typed SyntheticScanFixture required")
        pair = fixture.cached.partition.instrument_version
        if pair in selected_set:
            by_pair[pair].append(fixture)

    if any(not by_pair[pair] for pair in selection.selected_pairs):
        raise ValueError("SELECTED_PAIR_FIXTURES_MISSING")
    selected_fixtures = tuple(
        fixture for pair in selection.selected_pairs for fixture in by_pair[pair]
    )
    sweep = run_synthetic_five_minute_sweep(
        selected_fixtures, policy, decision_utc,
        supports_bounded_range=supports_bounded_range,
    )
    if sweep.pair_count != len(selection.selected_pairs):
        raise ValueError("SELECTED_PAIR_COUNT_MISMATCH")
    return SelectedSyntheticScanReport(selection, sweep)

"""Synthetic five-minute 20-pair Smart Cache workload — ZERO provider IO.

An explicit in-memory *oracle* is allowed only in controlled tests. A real
trading system cannot see unseen vendor corrections without fetching them.
This workload reports hypothetical queried candle ROWS, not HTTP bytes,
latency, provider API quotas or actual network savings.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import cast

from .cache_core import (
    CachePartition, CandleSnapshot, IncrementalPolicy, RefreshMode,
    SourceHeadClaim, plan_incremental_refresh, reconcile_closed_delta,
)
from .market_data import BarSide, MarketBar
from .quotes import ensure_utc


@dataclass(frozen=True, slots=True)
class SyntheticScanFixture:
    """Baseline and full synthetic oracle must describe one typed partition."""
    cached: CandleSnapshot
    complete_oracle: CandleSnapshot
    head_claim: SourceHeadClaim | None

    def __post_init__(self) -> None:
        if not isinstance(self.cached, CandleSnapshot) or not isinstance(
            self.complete_oracle, CandleSnapshot
        ):
            raise TypeError("Synthetic fixtures require typed CandleSnapshot")
        if self.cached.partition != self.complete_oracle.partition:
            raise ValueError("SOURCE_ORACLE_PARTITION_MISMATCH")
        if self.head_claim is not None and not isinstance(
            self.head_claim, SourceHeadClaim
        ):
            raise TypeError("Typed SourceHeadClaim required")
        if not self.cached.closed_bars:
            raise ValueError("SYNTHETIC_WARM_SCAN_REQUIRES_CACHED_BARS")


class SyntheticSweepVerdict(str, Enum):
    ORACLE_PARITY = "ORACLE_PARITY"
    UNSEEN_HISTORY_CORRECTION = "UNSEEN_HISTORY_CORRECTION"
    SOURCE_RANGE_UNAVAILABLE = "SOURCE_RANGE_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class SyntheticStreamResult:
    partition_fingerprint: str
    refresh_mode: RefreshMode
    verdict: SyntheticSweepVerdict
    simulated_returned_bar_rows: int
    unchanged_old_rows_retained: int
    appended: int
    revised: int
    first_dirty_utc: datetime | None
    # A synthetic oracle can prove fixture parity, NOT genuine vendor truth.
    actual_provider_verified: bool = False
    may_fetch_or_cache_real_prices: bool = False


@dataclass(frozen=True, slots=True)
class SyntheticSweepReport:
    pair_count: int
    stream_count: int
    baseline_naive_full_history_rows: int
    planned_bounded_range_queries: int
    simulated_returned_bar_rows: int
    simulated_head_claim_reuses: int
    old_cached_rows_retained: int
    appended: int
    revised: int
    unobservable_old_correction_cases: int
    stream_results: tuple[SyntheticStreamResult, ...]
    actual_http_calls: int = 0
    actual_http_bytes: int = 0
    actual_elapsed_ms_measured: bool = False
    may_run_real_scan: bool = False

    @property
    def hypothetical_history_rows_avoided(self) -> int:
        """Counterfactual for fixture only, NOT actual bytes/API savings."""
        return self.baseline_naive_full_history_rows - self.simulated_returned_bar_rows


def _pair_group(p: CachePartition) -> tuple[str, ...]:
    return (
        p.provider_id, p.broker_product_ref, p.instrument_version,
        p.timeframe.value, p.calendar_version, p.aggregation_version,
        p.source_timezone_policy, p.rights_policy_ref, p.schema_version,
    )


def run_synthetic_five_minute_sweep(
    fixtures: tuple[SyntheticScanFixture, ...],
    policy: IncrementalPolicy,
    decision_utc: datetime,
    *,
    supports_bounded_range: bool = True,
) -> SyntheticSweepReport:
    """Compare naive full re-fetch against planned DELTA/HEAD on a known oracle.

    Does not call external sources, trust self-supplied head IDs or promote
    synthetic VERIFIED to provider authorization. Pair completeness is strict.
    """
    ensure_utc(decision_utc, "decision_utc")
    if not isinstance(fixtures, tuple) or not fixtures:
        raise ValueError("NONEMPTY_IMMUTABLE_FIXTURE_SET_REQUIRED")
    if not isinstance(policy, IncrementalPolicy):
        raise TypeError("IncrementalPolicy required")
    if type(supports_bounded_range) is not bool:
        raise TypeError("supports_bounded_range must be bool")
    partition_keys: set[str] = set()
    paired: dict[tuple[str, ...], set[BarSide]] = {}
    pair_ids: set[str] = set()
    for entry in fixtures:
        if not isinstance(entry, SyntheticScanFixture):
            raise TypeError("Typed fixture required")
        p = entry.cached.partition
        if p.side is BarSide.MID:
            raise ValueError("MISSING_EXECUTABLE_BID_ASK_PARTITION")
        if p.fingerprint in partition_keys:
            raise ValueError("DUPLICATE_SOURCE_PARTITION")
        partition_keys.add(p.fingerprint)
        paired.setdefault(_pair_group(p), set()).add(p.side)
        pair_ids.add(p.instrument_version)
    if any(sides != {BarSide.BID, BarSide.ASK} for sides in paired.values()):
        raise ValueError("PAIR_REQUIRES_BOTH_BID_AND_ASK")

    count_full = count_delta = count_head = row_count = retained = added = corrected = missed = 0
    outputs: list[SyntheticStreamResult] = []
    for entry in fixtures:
        base, oracle = entry.cached, entry.complete_oracle
        if oracle.checked_at_utc > decision_utc:
            raise ValueError("FUTURE_ORACLE_SNAPSHOT")
        plan = plan_incremental_refresh(
            base, policy, decision_utc,
            supports_bounded_range=supports_bounded_range, head=entry.head_claim,
        )
        count_full += len(oracle.closed_bars)
        fetch_rows: tuple[MarketBar, ...] = ()
        if plan.mode is RefreshMode.DELTA_WINDOW:
            count_delta += 1
            fetch_rows = tuple(
                b for b in oracle.closed_bars if b.key.bar_start_utc >= cast(datetime, plan.from_utc)
            )
        elif plan.mode is RefreshMode.REUSE_HEAD_CLAIM:
            count_head += 1
        # A real full-history request is intentionally NEVER scheduled, even
        # when this simulated oracle is insufficient to validate correctness.
        row_count += len(fetch_rows)
        if plan.mode in (RefreshMode.REUSE_HEAD_CLAIM, RefreshMode.DELTA_WINDOW):
            reconciled = reconcile_closed_delta(
                base, fetch_rows, decision_utc,
                new_source_head_claim=oracle.source_head_claim,
            )
            same_as_oracle = (
                reconciled.snapshot.fingerprint == oracle.fingerprint
            )
            if not same_as_oracle:
                verdict = SyntheticSweepVerdict.UNSEEN_HISTORY_CORRECTION
                missed += 1
            else:
                verdict = SyntheticSweepVerdict.ORACLE_PARITY
            old_rows_retained = len(base.closed_bars) - reconciled.revised
            retained += old_rows_retained
            added += reconciled.appended
            corrected += reconciled.revised
            outputs.append(SyntheticStreamResult(
                base.partition.fingerprint, plan.mode, verdict,
                len(fetch_rows), old_rows_retained, reconciled.appended,
                reconciled.revised, reconciled.first_dirty_utc,
            ))
        else:
            outputs.append(SyntheticStreamResult(
                base.partition.fingerprint, plan.mode,
                SyntheticSweepVerdict.SOURCE_RANGE_UNAVAILABLE,
                0, 0, 0, 0, None,
            ))
    return SyntheticSweepReport(
        len(pair_ids), len(fixtures), count_full, count_delta,
        row_count, count_head, retained, added, corrected, missed,
        tuple(outputs),
    )

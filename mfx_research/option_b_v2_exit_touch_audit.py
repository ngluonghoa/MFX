"""MFX P0.167: read-only SIM stop/target TOUCH audit after P0.166 net-R.

Detect FIRST closed BID (long) / ASK (short) M5 candle whose OHLC range
touches a hypothetical exit level. Never claim intrabar order, fills or PnL.
No vendor/Drive call, broker order, historical real OOS or source approval.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from hashlib import sha256
import json

from forex_trading.market_data import (
    BarCoverage, BarLifecycle, BarSide, MarketBar, SourceQuality, Timeframe,
)
from forex_trading.model import ActionIntent
from forex_trading.quotes import PriceSide
from mfx_research.option_b_v2_bidask_replay_bridge import (
    OptionBNetRReplayReceipt, verify_option_b_v2_risk_replay,
)

VERSION = "MFX_OPTION_B_V2_BIDASK_M5_EXIT_TOUCH_SIM_AUDIT_V1"
MAX_M5_BARS_PER_WINDOW = 96
GENESIS = sha256(b"MFX:P0.167:UNAPPROVED-SIM-M5-EXIT-TOUCH").hexdigest()

NO_PATH = "NO_CLOSED_SIM_M5_EXIT_PATH"
NO_ECONOMICS = "NO_HYPOTHETICAL_RISK_NO_EXIT_REVIEW"
DUPLICATE = "DUPLICATE_EVENT_OUTCOME_NOT_RECOUNTED"
NO_TOUCH = "NO_EXIT_LEVEL_TOUCHED_IN_SUPPLIED_WINDOW"
STOP = "STOP_LEVEL_ONLY_TOUCHED_NO_FILL_CLAIM"
TARGET = "TARGET_LEVEL_ONLY_TOUCHED_NO_FILL_CLAIM"
AMBIGUOUS = "BOTH_STOP_TARGET_SAME_M5_ORDER_UNKNOWN"
OPEN_STOP = "STOP_BREACHED_AT_FIRST_VISIBLE_OPEN_NO_FILL_CLAIM"
OPEN_TARGET = "TARGET_BREACHED_AT_FIRST_VISIBLE_OPEN_NO_FILL_CLAIM"


@dataclass(frozen=True, slots=True, repr=False)
class SimExitTouchStep:
    event_sha256: str
    status: str
    first_touch_m5_bar_index: int | None
    inspected_closed_m5_bars: int
    private_path_sha256: str = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class SimExitTouchAudit:
    version: str
    prior: OptionBNetRReplayReceipt = field(repr=False)
    paths: tuple[tuple[MarketBar, ...], ...] = field(repr=False)
    evaluation_utc: datetime
    steps: tuple[SimExitTouchStep, ...] = field(repr=False)
    chain_sha256: str = field(repr=False)
    stop_only: int = 0
    target_only: int = 0
    same_bar_ambiguous: int = 0
    first_visible_open_breach: int = 0
    no_touch: int = 0
    missing_future_path: int = 0
    skipped_not_qualified: int = 0
    action: str = "NO_SIGNAL"
    stage: str = "UNVERIFIED"
    simulated_only: bool = True
    actual_fill_or_order_known: bool = False
    realized_profit_verified: bool = False
    original_forex_numeric_parity_approved: bool = False
    source_license_verified: bool = False
    source_d1_revision_qualified: bool = False
    publisher_first_known_verified: bool = False
    real_bidask_or_tick_data_verified: bool = False
    true_oos_qualified: bool = False
    may_publish_buy_sell: bool = False
    may_trade: bool = False
    broker_orders: int = 0
    provider_requests: int = 0
    drive_market_writes: int = 0

    def as_safe_record(self) -> dict[str, str | bool | int]:
        """Aggregate counts only: do not show simulated price, direction or SHA."""
        return {
            "version": self.version,
            "snapshots_checked": self.prior.replay.snapshots_checked,
            "stop_only": self.stop_only,
            "target_only": self.target_only,
            "same_bar_ambiguous": self.same_bar_ambiguous,
            "first_visible_open_breach": self.first_visible_open_breach,
            "no_touch": self.no_touch,
            "missing_future_path": self.missing_future_path,
            "skipped_not_qualified": self.skipped_not_qualified,
            "action": self.action,
            "stage": self.stage,
            "simulated_only": self.simulated_only,
            "actual_fill_or_order_known": self.actual_fill_or_order_known,
            "realized_profit_verified": self.realized_profit_verified,
            "original_forex_numeric_parity_approved":
                self.original_forex_numeric_parity_approved,
            "source_license_verified": self.source_license_verified,
            "source_d1_revision_qualified": self.source_d1_revision_qualified,
            "publisher_first_known_verified": self.publisher_first_known_verified,
            "real_bidask_or_tick_data_verified":
                self.real_bidask_or_tick_data_verified,
            "true_oos_qualified": self.true_oos_qualified,
            "may_publish_buy_sell": self.may_publish_buy_sell,
            "may_trade": self.may_trade,
            "broker_orders": self.broker_orders,
            "provider_requests": self.provider_requests,
            "drive_market_writes": self.drive_market_writes,
        }


def _digest(value: object) -> str:
    return sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def _exact_utc(value: object) -> datetime:
    if (type(value) is not datetime or value.tzinfo is None
            or value.utcoffset() != timedelta(0)):
        raise ValueError("P167_EXACT_UTC_EVALUATION_REQUIRED")
    return value


def _bar_private_digest(bar: MarketBar) -> list[str | int]:
    """Typed price lineage hashed privately; never rendered in safe output."""
    return [
        bar.key.instrument_version, bar.key.timeframe.value,
        bar.key.bar_start_utc.isoformat(), bar.key.bar_end_utc.isoformat(),
        bar.key.calendar_version, bar.key.aggregation_version,
        bar.key.side.value,
        bar.observation.provider_id, bar.observation.stream_id,
        bar.observation.endpoint, bar.observation.revision_id,
        bar.observation.raw_sha256,
        bar.observation.source_timezone_policy,
        bar.observation.license_scope_claim, bar.revision_number,
        bar.first_known_utc.isoformat(),
        bar.observation.first_known_utc.isoformat(),
        bar.observation.retrieved_at_utc.isoformat(),
        str(bar.open), str(bar.high), str(bar.low), str(bar.close),
        bar.lifecycle.value, bar.coverage.value, bar.quality.value,
    ]


def audit_option_b_v2_sim_exit_touches(
    prior: OptionBNetRReplayReceipt,
    paths: tuple[tuple[MarketBar, ...], ...],
    *,
    evaluation_utc: datetime,
) -> SimExitTouchAudit:
    """Classify only possible level touches, never implied realized fills.

    The evaluator's evaluation_utc is a *later* audit clock than entry.
    Never re-use these later bars when computing past candidate signals.
    """
    now = _exact_utc(evaluation_utc)
    if type(prior) is not OptionBNetRReplayReceipt:
        raise TypeError("P167_TYPED_P166_REPLAY_REQUIRED")
    if (type(paths) is not tuple or len(paths) != len(prior.steps)
            or any(type(p) is not tuple or len(p) > MAX_M5_BARS_PER_WINDOW
                   or any(type(b) is not MarketBar for b in p)
                   for p in paths)):
        raise ValueError("P167_EXACT_BOUNDED_TYPED_M5_PATHS_REQUIRED")
    if not verify_option_b_v2_risk_replay(prior):
        raise ValueError("P167_UNVERIFIED_P166_INPUT")
    rows: list[SimExitTouchStep] = []
    chain = GENESIS
    counts = {
        "stop_only": 0,
        "target_only": 0,
        "same_bar_ambiguous": 0,
        "first_visible_open_breach": 0,
        "no_touch": 0,
        "missing_future_path": 0,
        "skipped_not_qualified": 0,
    }
    for step, path, source_step in zip(
            prior.steps, paths, prior.replay.steps):
        economic = step.economics
        decision = source_step.snapshot.decision_utc
        if now <= decision:
            raise ValueError("P167_EVALUATION_MUST_FOLLOW_ENTRY_DECISION")
        if source_step.duplicate_suppressed or economic is None:
            if path:
                raise ValueError("P167_NO_EXIT_PATH_FOR_DUPLICATE_OR_NO_RISK")
            status = DUPLICATE if source_step.duplicate_suppressed else NO_ECONOMICS
            first_index = None
            inspected = 0
            counts["skipped_not_qualified"] += 1
        elif not path:
            status = NO_PATH
            first_index = None
            inspected = 0
            counts["missing_future_path"] += 1
        else:
            if economic.intent is ActionIntent.ENTRY_LONG:
                side = BarSide.BID
                if economic.exit_side is not PriceSide.BID:
                    raise ValueError("P167_LONG_REQUIRES_BID_EXIT_SIDE")
            elif economic.intent is ActionIntent.ENTRY_SHORT:
                side = BarSide.ASK
                if economic.exit_side is not PriceSide.ASK:
                    raise ValueError("P167_SHORT_REQUIRES_ASK_EXIT_SIDE")
            else:
                raise ValueError("P167_UNEXPECTED_ENTRY_INTENT")
            stop = economic.stop_exit_reference_price
            target = economic.target_exit_reference_price
            quote = prior.bundles[len(rows)]
            if quote is None:
                raise ValueError("P167_ECONOMIC_WITHOUT_SIM_QUOTE_BUNDLE")
            anchor = source_step.snapshot.bars.trigger_m15[-1]
            prev_end: datetime | None = None
            first_index = None
            status = NO_TOUCH
            for index, bar in enumerate(path):
                if (bar.key.timeframe is not Timeframe.M5
                        or bar.key.side is not side
                        or bar.lifecycle is not BarLifecycle.CLOSED
                        or bar.coverage is not BarCoverage.COMPLETE
                        or bar.quality is not SourceQuality.VERIFIED
                        or not bar.observation.provider_id.startswith("SIM:")
                        or not bar.observation.revision_id.startswith("SIM:")
                        or bar.observation.provider_id != quote.quote.provider
                        or bar.observation.provider_id != anchor.observation.provider_id
                        or bar.observation.stream_id != anchor.observation.stream_id
                        or bar.key.instrument_version != anchor.key.instrument_version
                        or bar.key.calendar_version != anchor.key.calendar_version
                        or bar.key.aggregation_version != anchor.key.aggregation_version
                        or bar.first_known_utc > now
                        or bar.observation.retrieved_at_utc > now
                        or bar.key.bar_start_utc < decision
                        or (prev_end is not None
                            and bar.key.bar_start_utc != prev_end)):
                    raise ValueError("P167_NONCAUSAL_MIXED_OR_INCOMPLETE_M5_EXIT_PATH")
                prev_end = bar.key.bar_end_utc
                if economic.intent is ActionIntent.ENTRY_LONG:
                    touched_stop = bar.low <= stop
                    touched_target = bar.high >= target
                    open_stop = bar.open <= stop
                    open_target = bar.open >= target
                else:
                    touched_stop = bar.high >= stop
                    touched_target = bar.low <= target
                    open_stop = bar.open >= stop
                    open_target = bar.open <= target
                if first_index is None:
                    if open_stop and open_target:
                        status = AMBIGUOUS
                    elif open_stop:
                        status = OPEN_STOP
                    elif open_target:
                        status = OPEN_TARGET
                    elif touched_stop and touched_target:
                        status = AMBIGUOUS
                    elif touched_stop:
                        status = STOP
                    elif touched_target:
                        status = TARGET
                    if status != NO_TOUCH:
                        first_index = index
            inspected = len(path)
            if status == NO_TOUCH:
                counts["no_touch"] += 1
            elif status == AMBIGUOUS:
                counts["same_bar_ambiguous"] += 1
            elif status in (OPEN_STOP, OPEN_TARGET):
                counts["first_visible_open_breach"] += 1
            elif status == STOP:
                counts["stop_only"] += 1
            elif status == TARGET:
                counts["target_only"] += 1
        path_sha = _digest([_bar_private_digest(bar) for bar in path])
        chain = _digest([
            VERSION, chain, step.replay_step_event_sha256,
            step.risk_input_sha256, path_sha,
            now.isoformat(), status, first_index, inspected,
        ])
        rows.append(SimExitTouchStep(
            event_sha256=step.replay_step_event_sha256,
            status=status,
            first_touch_m5_bar_index=first_index,
            inspected_closed_m5_bars=inspected,
            private_path_sha256=path_sha,
        ))
    return SimExitTouchAudit(
        version=VERSION, prior=prior, paths=paths,
        evaluation_utc=now, steps=tuple(rows), chain_sha256=chain,
        **counts,
    )


def verify_option_b_v2_sim_exit_touch_audit(
    audit: SimExitTouchAudit,
) -> bool:
    """Recompute from private inputs; reject any mutated report or permissions."""
    if type(audit) is not SimExitTouchAudit:
        raise TypeError("P167_TYPED_EXIT_TOUCH_AUDIT_REQUIRED")
    replayed = audit_option_b_v2_sim_exit_touches(
        audit.prior, audit.paths,
        evaluation_utc=audit.evaluation_utc,
    )
    if audit != replayed:
        raise ValueError("P167_EXIT_TOUCH_CHAIN_OR_RIGHTS_DRIFT")
    return True

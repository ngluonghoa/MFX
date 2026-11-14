"""P0.161 Option B: executable CLOSED synthetic B2/S2 right-confirmed pivots.

Reuses P020 D1/H4 swing/ATR/H1 and newly right-confirmed M15 micro level,
plus P031 22-role classification. Explicitly MFX-owned numeric DRAFT V2,
never source-approved original Forex numeric 1:1 or real market BUY/SELL.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from hashlib import sha1, sha256
import json
from pathlib import Path
from typing import Any

from forex_trading.model import SignalStage
from mfx_research.causal_multitf_context import (
    SyntheticDerivationParameters, SyntheticMultiTfBars,
)
from mfx_research.confirmed_swings import (
    ConfirmedSwingResearchReceipt, SyntheticPivotParameters,
    derive_swing_b2_s2_research,
)
from mfx_research.mfx_b2s2_independent_policy_draft import (
    CONFIG_PATH as P160_PATH, LINEAGE, read_independent_mfx_policy_draft,
)
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.p031_sim_22_zone_router import (
    ResearchZoneReport, SimZoneLabelClaim, route_sim_22_zone_labels,
)
from mfx_research.pullback_pilot import UnapprovedResearchParameters

VERSION = "MFX:B2S2-NEW-STRATEGY-DRAFT-002"
SCHEMA = "MFX_OPTION_B_CONFIRMED_SWING_DRAFT_V1"
CONFIG_PATH = Path("docs/MFX_V1_B2S2_CONFIRMED_SWING_DRAFT_V2.json")
PINNED_PARENT_GIT_BLOB = "dbaed8ca436904fd83c528818358e677def43be3"
_PARAM_KEYS = frozenset((
    "d1_h4_confirmed_swing_left_bars",
    "d1_h4_confirmed_swing_right_bars",
    "m15_confirmed_micro_left_bars",
    "m15_confirmed_micro_right_bars",
    "requires_two_confirmed_highs_and_lows_per_htf",
    "requires_m15_pivot_confirmed_before_trigger_open",
    "requires_source_closed_at_asof",
))
_RIGHTS = frozenset((
    "numeric_policy_approved", "original_forex_numeric_1to1_parity",
    "real_source_licence_approved", "source_d1_revision_qualified",
    "live_bidask_risk_approved", "historical_oos_approved",
    "public_buy_sell_allowed", "broker_order_allowed",
))
_ROOT = frozenset((
    "schema", "version", "strategy_lineage",
    "parent_numeric_config_git_blob", "scope", "experimental_params",
    "validation", "owner_numeric_review", "permissions",
))


def _only_keys(obj: object, allowed: frozenset[str], name: str) -> dict[str, Any]:
    if type(obj) is not dict or set(obj) != allowed:
        raise ValueError("P161_EXACT_DRAFT_SCHEMA:" + name)
    return obj


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    record: dict[str, Any] = {}
    for key, val in pairs:
        if key in record:
            raise ValueError("P161_DUPLICATE_DRAFT_JSON_KEY")
        record[key] = val
    return record


def _same(value: object, expected: object, field_name: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise ValueError("P161_DRAFT_LINEAGE_OR_RIGHTS_DRIFT:" + field_name)


@dataclass(frozen=True, slots=True)
class MfxConfirmedB2S2V2Policy:
    version: str
    fingerprint_sha256: str
    htf_left: int
    htf_right: int
    micro_left: int
    micro_right: int
    lineage: str = LINEAGE
    numeric_rules_approved: bool = False
    forex_original_numeric_parity: bool = False
    market_rights_verified: bool = False
    publisher_first_known_verified: bool = False
    native_d1_revision_hold_cleared: bool = False
    real_oos_qualified: bool = False
    live_signals_allowed: bool = False
    broker_orders_allowed: bool = False


@dataclass(frozen=True, slots=True, repr=False)
class MfxB2S2V2ClosedResearch:
    rule_id: str
    version: str
    policy_fingerprint_sha256: str
    source: ConfirmedSwingResearchReceipt = field(repr=False)
    routed: ResearchZoneReport = field(repr=False)
    experimental_action: CandidateAction = field(repr=False)
    lineage: str = LINEAGE
    public_action: str = "NO_SIGNAL"
    stage: str = "UNVERIFIED"
    independent_numeric_rule_approved: bool = False
    original_forex_numeric_1to1: bool = False
    source_market_rights_verified: bool = False
    native_d1_revision_hold_cleared: bool = False
    true_historical_oos_qualified: bool = False
    live_buy_sell_allowed: bool = False
    may_trade: bool = False
    new_provider_requests: int = 0
    new_drive_market_writes: int = 0
    broker_orders: int = 0

    def as_safe_record(self) -> dict[str, str | bool | int]:
        return {
            "rule_id": self.rule_id,
            "version": self.version,
            "lineage": self.lineage,
            "public_action": self.public_action,
            "stage": self.stage,
            "numeric_rule_approved": self.independent_numeric_rule_approved,
            "source_market_rights_verified": self.source_market_rights_verified,
            "native_d1_revision_hold_cleared":
                self.native_d1_revision_hold_cleared,
            "historical_oos_qualified": self.true_historical_oos_qualified,
            "live_buy_sell_allowed": self.live_buy_sell_allowed,
            "may_trade": self.may_trade,
            "broker_orders": self.broker_orders,
        }


def verify_mfx_confirmed_b2s2_v2(obj: object) -> MfxConfirmedB2S2V2Policy:
    root = _only_keys(obj, _ROOT, "root")
    for name, expected in (
        ("schema", SCHEMA), ("version", VERSION),
        ("strategy_lineage", LINEAGE),
        ("parent_numeric_config_git_blob", PINNED_PARENT_GIT_BLOB),
        ("scope", "OPTION_B_DEVELOPMENT_ONLY_NOT_NUMERIC_REVIEW"),
        ("validation", "SYNTHETIC_ONLY_NOT_LIVE_POINT_IN_TIME_OOS"),
        ("owner_numeric_review", "PENDING"),
    ):
        _same(root[name], expected, name)
    rights = _only_keys(root["permissions"], _RIGHTS, "permissions")
    for name in _RIGHTS:
        _same(rights[name], False, "permissions." + name)
    params = _only_keys(root["experimental_params"], _PARAM_KEYS, "params")
    widths = []
    for name in (
        "d1_h4_confirmed_swing_left_bars",
        "d1_h4_confirmed_swing_right_bars",
        "m15_confirmed_micro_left_bars",
        "m15_confirmed_micro_right_bars",
    ):
        val = params[name]
        if type(val) is not int or not 1 <= val <= 3:
            raise ValueError("P161_CANDIDATE_PIVOT_WIDTH_INVALID:" + name)
        widths.append(val)
    for name in (
        "requires_two_confirmed_highs_and_lows_per_htf",
        "requires_m15_pivot_confirmed_before_trigger_open",
        "requires_source_closed_at_asof",
    ):
        _same(params[name], True, "params." + name)
    fingerprint = sha256(json.dumps(
        root, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return MfxConfirmedB2S2V2Policy(
        version=VERSION, fingerprint_sha256=fingerprint,
        htf_left=widths[0], htf_right=widths[1],
        micro_left=widths[2], micro_right=widths[3],
    )


def read_mfx_confirmed_b2s2_v2(path: Path = CONFIG_PATH) -> MfxConfirmedB2S2V2Policy:
    if not isinstance(path, Path):
        raise TypeError("P161_TYPED_DRAFT_PATH_REQUIRED")
    raw = path.read_bytes()
    if not raw or len(raw) > 8192:
        raise ValueError("P161_INVALID_DRAFT_SIZE")
    obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
    return verify_mfx_confirmed_b2s2_v2(obj)


def _p160_still_pinned() -> None:
    # Verify exact P160 Git blob bytes; no silent parent-policy change.
    raw = P160_PATH.read_bytes()
    actual = sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
    ).hexdigest()
    if actual != PINNED_PARENT_GIT_BLOB:
        raise ValueError("P161_PARENT_P160_NUMERIC_DRAFT_BLOB_CHANGED")
    p160 = read_independent_mfx_policy_draft()
    if (p160.specific_numeric_policy_approved
            or p160.original_forex_numerical_parity_verified
            or p160.source_license_verified or p160.may_trade
            or p160.may_publish_buy_sell):
        raise ValueError("P161_PARENT_POLICY_FALSE_AUTHORITY")


def compute_mfx_b2s2_v2_closed_candidate(
    rule_id: str,
    bars: SyntheticMultiTfBars,
    confirmed_m15_history: tuple,
    policy: MfxConfirmedB2S2V2Policy,
    decision_utc: datetime,
) -> MfxB2S2V2ClosedResearch:
    """Use exact historical closed SIM bars; all research events private.

    No result can claim real source first-known, account rights or release.
    """
    if type(rule_id) is not str or rule_id not in ("B2", "S2"):
        raise ValueError("P161_ONLY_OPTION_B_B2_S2")
    if type(bars) is not SyntheticMultiTfBars:
        raise TypeError("P161_TYPED_SYNTHETIC_MULTI_TF_REQUIRED")
    if type(policy) is not MfxConfirmedB2S2V2Policy:
        raise TypeError("P161_TYPED_EXACT_DRAFT_POLICY_REQUIRED")
    if (policy != read_mfx_confirmed_b2s2_v2()
            or policy.version != VERSION
            or policy.lineage != LINEAGE
            or policy.numeric_rules_approved
            or policy.forex_original_numeric_parity
            or policy.market_rights_verified
            or policy.publisher_first_known_verified
            or policy.native_d1_revision_hold_cleared
            or policy.real_oos_qualified or policy.live_signals_allowed
            or policy.broker_orders_allowed):
        raise ValueError("P161_DRAFT_MODIFICATION_OR_FAKE_SIGNOFF")
    _p160_still_pinned()
    numeric = read_independent_mfx_policy_draft()
    htf = SyntheticPivotParameters(
        version="SIM:MFX-V2-HTF-RIGHT-CLOSED-DRAFT",
        left_bars=policy.htf_left, right_bars=policy.htf_right,
    )
    micro = SyntheticPivotParameters(
        version="SIM:MFX-V2-M15-RIGHT-CLOSED-DRAFT",
        left_bars=policy.micro_left, right_bars=policy.micro_right,
    )
    zone = SyntheticDerivationParameters(
        version="SIM:MFX-V2-TR-ZONE-DRAFT",
        atr_h1_periods=numeric.h1_tr_mean_period,
        h1_zone_lookback=numeric.h1_zone_lookback,
        zone_width_atr_multiple=numeric.h1_width_multiple,
    )
    trigger = UnapprovedResearchParameters(
        version="SIM:MFX-V2-NEAR-CHASE-DRAFT",
        near_zone_atr_multiple=numeric.h1_near_multiple,
        max_chase_atr_multiple=numeric.max_chase_multiple,
    )
    # One identity per symbol + CLOSED trigger time, not an arbitrary event
    # claimed by a caller or a public signal. P020 independently checks it.
    if not isinstance(bars.trigger_m15, tuple) or len(bars.trigger_m15) != 2:
        raise ValueError("P161_EXACT_TWO_CLOSED_TRIGGER_CANDLES_REQUIRED")
    last = bars.trigger_m15[-1]
    origin_id = "SIM:MFX-V2-" + rule_id + "-" + (
        last.key.bar_end_utc.strftime("%Y%m%dT%H%M%S")
    )
    swing = derive_swing_b2_s2_research(
        rule_id, bars, htf, zone, trigger, decision_utc,
        origin_event_id=origin_id,
        confirmed_m15_history=confirmed_m15_history,
        confirmed_m15_policy=micro,
    )
    if (swing.m15_confirmed_pivots is None
            or swing.daily_trend.value not in ("UP", "DOWN", "UNKNOWN")
            or swing.four_hour_trend.value not in ("UP", "DOWN", "UNKNOWN")
            or swing.signal.stage is not SignalStage.UNVERIFIED
            or swing.signal.may_send_confirmed_signal
            or swing.signal.original_forex_numerical_parity
            or swing.may_send_confirmed_signal or swing.can_trade
            or swing.market_provider_calls or swing.drive_raw_market_cache_writes):
        raise ValueError("P161_CONFIRMED_SIM_CONTEXT_AUTHORITY_DRIFT")
    expected = CandidateAction.BUY if rule_id == "B2" else CandidateAction.SELL
    if swing.signal.action not in (CandidateAction.NO_SIGNAL, expected):
        raise ValueError("P161_OPPOSITE_DIRECTION_FROM_COMPUTED_PIVOT")
    claims: tuple[SimZoneLabelClaim, ...] = ()
    if swing.signal.action is expected:
        claims = (SimZoneLabelClaim(
            instrument_version=last.key.instrument_version,
            calendar_version=last.key.calendar_version,
            origin_event_id=origin_id,
            provider_id=last.observation.provider_id,
            stream_id=last.observation.stream_id,
            label=rule_id,
            closed_candle_end_utc=last.key.bar_end_utc,
            first_known_utc=last.first_known_utc,
            retrieved_at_utc=last.observation.retrieved_at_utc,
        ),)
    routed = route_sim_22_zone_labels(claims, decision_utc)
    if (len(routed.classified) != len(claims)
            or routed.numeric_entry_predicates_approved
            or routed.confirmed_buy_sell_signals
            or routed.may_send_live_alerts or routed.broker_orders
            or routed.may_trade):
        raise ValueError("P161_ORIGINAL_22_ZONE_SIM_ROUTER_GATE")
    return MfxB2S2V2ClosedResearch(
        rule_id=rule_id, version=policy.version,
        policy_fingerprint_sha256=policy.fingerprint_sha256,
        source=swing, routed=routed,
        experimental_action=swing.signal.action,
    )

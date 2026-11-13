"""User-selected Option B: versioned *independent MFX* B2/S2 numeric draft.

This is a genuine, executable SYNTHETIC research parameter profile, NOT an
original-Forex 1:1 numerical rule, a numeric owner signoff or a live signal.
Rather than copying the already-implemented P019/P032 OHLC arithmetic,
this adapter verifies its versioned MFX-only config and runs that existing
closed-bar/zone/trend/trigger/22-role bridge with explicit parameters.

The current two-HTF-candle and M15 seed proxies are deliberately disclosed
as methodological gaps, not misrepresented as validated causal pivots.
No market vendor, Drive cache, broker, scheduled job, or alert is used.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

from mfx_research.causal_multitf_context import (
    SyntheticDerivationParameters, SyntheticMultiTfBars,
)
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.p032_synthetic_ohlc_bridge import (
    ComputedSIMOHLCResearch, compute_and_route_sim_b2_s2,
)
from mfx_research.pullback_pilot import UnapprovedResearchParameters

SCHEMA = "MFX_B2S2_INDEPENDENT_NUMERIC_POLICY_DRAFT_V1"
VERSION = "MFX:B2S2-NEW-STRATEGY-DRAFT-001"
LINEAGE = "MFX_NEW_NUMERIC_FORMULA_NOT_ORIGINAL_FOREX_1TO1"
CONFIG_PATH = Path("docs/MFX_V1_B2S2_INDEPENDENT_POLICY_DRAFT.json")
_MODE = "OPTION_B_NEW_MFX_RULE_DEVELOPMENT_ONLY"
_NUMERIC_FIELDS = frozenset((
    "h1_true_range_mean_period", "h1_zone_lookback",
    "h1_zone_width_tr_multiple", "h1_near_zone_tr_multiple",
    "max_chase_tr_multiple",
))
_TECHNICAL_LIMITS = {
    "trend": "EXPERIMENTAL_TWO_CLOSED_HTF_CANDLE_EXTREMA_PROXY_NOT_CONFIRMED_SWINGS",
    "h1_tr": "SIMPLE_MEAN_TRUE_RANGE_NOT_WILDER_ATR",
    "micro": "PRIOR_CLOSED_M15_SEED_EXTREME_NOT_RIGHT_BAR_CONFIRMED_PIVOT",
    "fx_side": "MID_TECHNICAL_ONLY",
    "calendar": "SYNTHETIC_UTC_ONLY",
}
_PERMISSION_FLAGS = frozenset((
    "numeric_rule_owner_signed", "licensed_real_source_rights",
    "native_d1_revision_hold_cleared", "publisher_first_known_verified",
    "broker_bidask_economics_verified", "historical_oos_qualified",
    "may_publish_buy_sell", "may_trade",
))
_DECIMAL = re.compile(r"(?:0|[1-9][0-9]{0,2})(?:\.[0-9]{1,8})?")
MAX_BYTES = 8192


def _keys(x: object, target: frozenset[str], label: str) -> dict[str, Any]:
    if type(x) is not dict or set(x) != target:
        raise ValueError("P160_EXACT_MFX_DRAFT_SCHEMA:" + label)
    return x


def _same(value: object, expected: object, label: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise ValueError("P160_DRAFT_SCOPE_OR_PERMISSION_DRIFT:" + label)


def _decimal(value: object, label: str) -> Decimal:
    if type(value) is not str or _DECIMAL.fullmatch(value) is None:
        raise ValueError("P160_EXPLICIT_VERSIONED_NUMERIC_STRING_REQUIRED:" + label)
    result = Decimal(value)
    if not result.is_finite() or result <= 0 or result > Decimal("20"):
        raise ValueError("P160_UNREVIEWED_NUMERIC_INPUT:" + label)
    return result


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("P160_DUPLICATE_DRAFT_JSON_KEY")
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class IndependentMFXNumericDraft:
    version: str
    canonical_sha256: str
    h1_tr_mean_period: int
    h1_zone_lookback: int
    h1_width_multiple: Decimal
    h1_near_multiple: Decimal
    max_chase_multiple: Decimal
    strategy_lineage: str = LINEAGE
    user_option_b_development_scope_approved: bool = True
    specific_numeric_policy_approved: bool = False
    original_forex_numerical_parity_verified: bool = False
    source_license_verified: bool = False
    native_d1_source_revision_qualified: bool = False
    historical_oos_qualified: bool = False
    may_publish_buy_sell: bool = False
    may_trade: bool = False


@dataclass(frozen=True, slots=True, repr=False)
class MFXIndependentB2S2DraftResult:
    version: str
    strategy_lineage: str
    rule_id: str
    policy_sha256: str
    technical: ComputedSIMOHLCResearch = field(repr=False)
    experimental_action: CandidateAction = field(repr=False)
    stage: str = "UNVERIFIED"
    action: str = "NO_SIGNAL"
    parameter_rule_approved: bool = False
    historical_oos_qualified: bool = False
    live_quote_rights_verified: bool = False
    original_forex_numerical_parity_verified: bool = False
    may_publish_buy_sell: bool = False
    may_trade: bool = False
    provider_requests: int = 0
    drive_market_cache_writes: int = 0
    broker_orders: int = 0

    def as_safe_record(self) -> dict[str, str | bool | int]:
        # Never show a private price-derived direction, source fingerprint,
        # numerical candidate or opportunity identity in Actions logs.
        return {
            "strategy_lineage": self.strategy_lineage,
            "version": self.version,
            "rule_id": self.rule_id,
            "stage": self.stage,
            "action": self.action,
            "specific_numeric_policy_approved": self.parameter_rule_approved,
            "original_forex_numeric_parity_verified":
                self.original_forex_numerical_parity_verified,
            "historical_oos_qualified": self.historical_oos_qualified,
            "live_quote_rights_verified": self.live_quote_rights_verified,
            "may_publish_buy_sell": self.may_publish_buy_sell,
            "may_trade": self.may_trade,
            "broker_orders": self.broker_orders,
        }


def verify_independent_mfx_policy_draft(obj: object) -> IndependentMFXNumericDraft:
    """Verify an explicitly UNAPPROVED numeric draft, never an approval token."""
    root = _keys(obj, frozenset((
        "schema", "version", "strategy_lineage", "user_approved_scope",
        "rules", "qualitative_source", "source_policy_status",
        "technical_method_limits", "numeric_candidate",
        "numeric_review_status", "validation_status", "permission_flags",
    )), "root")
    for key, expected in (
        ("schema", SCHEMA), ("version", VERSION),
        ("strategy_lineage", LINEAGE), ("user_approved_scope", _MODE),
        ("qualitative_source", "SOURCE_LOCKED_03_DETECTOR_AUDIT_B2_S2_DESIGN_ONLY"),
        ("source_policy_status", "ORIGINAL_FOREX_NUMERIC_36_PENDING"),
        ("numeric_review_status", "PROPOSED_NOT_APPROVED"),
        ("validation_status", "SYNTHETIC_CLOSED_CANDLE_ONLY_NOT_HISTORICAL_OOS"),
    ):
        _same(root[key], expected, key)
    _same(root["rules"], ["B2", "S2"], "rules")
    limits = _keys(root["technical_method_limits"],
                   frozenset(_TECHNICAL_LIMITS), "technical_method_limits")
    for key, expected in _TECHNICAL_LIMITS.items():
        _same(limits[key], expected, "technical_method_limits." + key)
    permissions = _keys(root["permission_flags"], _PERMISSION_FLAGS, "permission_flags")
    for key, value in permissions.items():
        _same(value, False, "permission_flags." + key)
    numeric = _keys(root["numeric_candidate"], _NUMERIC_FIELDS, "numeric_candidate")
    periods: list[int] = []
    for key in ("h1_true_range_mean_period", "h1_zone_lookback"):
        val = numeric[key]
        if type(val) is not int or not 2 <= val <= 24:
            raise ValueError("P160_NUMERIC_PERIOD_NOT_REVIEWED:" + key)
        periods.append(val)
    width, near, chase = (
        _decimal(numeric[key], key) for key in (
            "h1_zone_width_tr_multiple",
            "h1_near_zone_tr_multiple",
            "max_chase_tr_multiple",
        )
    )
    canonical_sha = sha256(json.dumps(
        root, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return IndependentMFXNumericDraft(
        version=VERSION, canonical_sha256=canonical_sha,
        h1_tr_mean_period=periods[0], h1_zone_lookback=periods[1],
        h1_width_multiple=width, h1_near_multiple=near,
        max_chase_multiple=chase,
    )


def read_independent_mfx_policy_draft(
    path: Path = CONFIG_PATH,
) -> IndependentMFXNumericDraft:
    if not isinstance(path, Path):
        raise TypeError("P160_TYPED_DRAFT_PATH_REQUIRED")
    raw = path.read_bytes()
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("P160_EMPTY_OR_OVERSIZED_DRAFT")
    data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
    return verify_independent_mfx_policy_draft(data)


def calculate_independent_mfx_b2s2_offline_candidate(
    rule_id: str,
    bars: SyntheticMultiTfBars,
    draft: IndependentMFXNumericDraft,
    decision_utc: datetime,
) -> MFXIndependentB2S2DraftResult:
    """Actually calculate private candidate via existing validated SIM OHLC.

    All five parameters come from explicitly versioned MFX-specific JSON.
    Production is forbidden even for a positive research BUY/SELL candidate.
    """
    if type(draft) is not IndependentMFXNumericDraft:
        raise TypeError("P160_TYPED_INDEPENDENT_MFX_DRAFT_REQUIRED")
    if (draft.version != VERSION or draft.strategy_lineage != LINEAGE
            or not draft.user_option_b_development_scope_approved
            or draft.specific_numeric_policy_approved
            or draft.original_forex_numerical_parity_verified
            or draft.source_license_verified
            or draft.native_d1_source_revision_qualified
            or draft.historical_oos_qualified
            or draft.may_publish_buy_sell or draft.may_trade
            or type(draft.canonical_sha256) is not str
            or not re.fullmatch("[a-f0-9]{64}", draft.canonical_sha256)):
        raise ValueError("P160_FORGED_NUMERIC_APPROVAL_OR_SCOPE")
    if type(rule_id) is not str or rule_id not in ("B2", "S2"):
        raise ValueError("P160_ONLY_MFX_INDEPENDENT_B2_S2")
    # Revalidate immutable policy against separately read canonical config:
    # caller-mutated or fabricated decimal values must not become new rules.
    source = read_independent_mfx_policy_draft()
    if draft != source:
        raise ValueError("P160_DRAFT_DIFFERS_FROM_EXACT_VERSIONED_SPEC")
    d = SyntheticDerivationParameters(
        version="SIM:MFX-B2S2-OPTION-B-CTX-DRAFT-001",
        atr_h1_periods=draft.h1_tr_mean_period,
        h1_zone_lookback=draft.h1_zone_lookback,
        zone_width_atr_multiple=draft.h1_width_multiple,
    )
    p = UnapprovedResearchParameters(
        version="SIM:MFX-B2S2-OPTION-B-TRIGGER-DRAFT-001",
        near_zone_atr_multiple=draft.h1_near_multiple,
        max_chase_atr_multiple=draft.max_chase_multiple,
    )
    technical = compute_and_route_sim_b2_s2(rule_id, bars, d, p, decision_utc)
    if (type(technical) is not ComputedSIMOHLCResearch
            or technical.action != "NO_SIGNAL"
            or technical.may_send_buy_sell_or_exit_alert
            or technical.actual_market_data_verified
            or technical.pattern_source_numeric_approved
            or technical.real_provider_calls or technical.broker_orders
            or technical.real_drive_market_cache_writes):
        raise ValueError("P160_REAL_SIGNAL_PROMOTION_DENIED")
    expected = CandidateAction.BUY if rule_id == "B2" else CandidateAction.SELL
    if technical.experimental_numeric_action not in (
            CandidateAction.NO_SIGNAL, expected):
        raise ValueError("P160_WRONG_DIRECTION_OR_EXPERIMENTAL_POLICY")
    return MFXIndependentB2S2DraftResult(
        version=draft.version, strategy_lineage=draft.strategy_lineage,
        rule_id=rule_id, policy_sha256=draft.canonical_sha256,
        technical=technical,
        experimental_action=technical.experimental_numeric_action,
    )

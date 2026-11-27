"""P249: versioned shared B2/S2 research scenario, not calibrated rules."""
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

from forex_trading.market_data import Timeframe
from mfx_research.p188_b2s2_numeric_owner_review_candidates import compile_p188_review_draft
from mfx_research.p214_sim_htf_invalidation import SimInvalidationPolicy
from mfx_research.p215_sim_structural_tp1 import SimStructuralTargetPolicy
from mfx_research.p218_sim_monitoring_lifecycle import SimMonitoringPolicy

CONFIG = Path("docs/MFX_P249_B2S2_SIM_PROFILE.json")
SCHEMA = "MFX_P249_B2S2_SIM_PROFILE_V1"
PIP = Decimal("0.0001")
# Exact scenario V1; modifications need a new reviewable profile version.
_EXPECTED = {
    "schema": SCHEMA,
    "scope": "INDEPENDENT_MFX_SYNTHETIC_SCENARIO_ONLY",
    "rules": ["B2", "S2"],
    "entry_profile": "PINNED_P160_P161_P188",
    "price_unit": "EURUSD_STYLE_SIM_PRICE_0.0001_PER_PIP",
    "invalidation_frames": ["H1", "H4"],
    "invalidation_buffer_pips": "0.5",
    "stop_frame": "H1",
    "stop_buffer_pips": "1",
    "target_buffer_pips": "0.5",
    "mid_exit_offset_pips": "0.5",
    "minimum_net_r": "1.5",
    "expiry_m15_slots": 4,
    "quote_max_age_seconds": 30,
    "source_numeric_approved": False,
    "real_market_data_allowed": False,
    "may_publish_buy_sell": False,
    "may_trade": False,
}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("P249_DUPLICATE_CONFIG_KEY")
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class SharedSimProfile:
    fingerprint: str
    p160_fingerprint: str
    p161_fingerprint: str
    structural: SimStructuralTargetPolicy
    monitoring: SimMonitoringPolicy
    max_quote_age: timedelta

    def public_summary(self):
        return {
            "version": SCHEMA, "shared_rules": 2,
            "existing_entry_pairs": 11,
            "additional_sim_policy_pairs": 3,
            "remaining_external_or_method_pairs": 4,
            "source_numeric_approved": False,
            "original_numeric_approvals": 0,
            "calibrated": False, "historical_oos_qualified": False,
            "real_market_data_allowed": False,
            "action": "NO_SIGNAL", "may_publish_buy_sell": False,
            "may_trade": False, "broker_orders": 0,
        }


def read_shared_sim_profile(path: Path = CONFIG) -> SharedSimProfile:
    if not isinstance(path, Path):
        raise TypeError("P249_TYPED_CONFIG_PATH_REQUIRED")
    raw = path.read_bytes()
    if not 0 < len(raw) <= 4096:
        raise ValueError("P249_CONFIG_SIZE")
    config = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    if (type(config) is not dict or config.keys() != _EXPECTED.keys()
            or any(type(config[k]) is not type(v) or config[k] != v
                   for k, v in _EXPECTED.items())):
        raise ValueError("P249_EXACT_UNAPPROVED_SCENARIO_REQUIRED")
    draft = compile_p188_review_draft()
    if (draft.experimental_pairs_for_review != 11
            or draft.original_owner_numeric_approvals != 0
            or draft.action != "NO_SIGNAL" or draft.may_publish_buy_sell):
        raise ValueError("P249_ENTRY_SCOPE_DRIFT")
    def price(key):
        return Decimal(config[key]) * PIP
    structural = SimStructuralTargetPolicy(
        Timeframe.H1, price("stop_buffer_pips"),
        price("target_buffer_pips"), price("mid_exit_offset_pips"),
        Decimal(config["minimum_net_r"]),
    )
    monitoring = SimMonitoringPolicy(
        SimInvalidationPolicy((Timeframe.H1, Timeframe.H4),
                              price("invalidation_buffer_pips")),
        config["expiry_m15_slots"],
    )
    fingerprint = sha256(json.dumps(
        [config, draft.p160_policy_sha256, draft.p161_policy_sha256],
        sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    return SharedSimProfile(fingerprint, draft.p160_policy_sha256,
                            draft.p161_policy_sha256, structural, monitoring,
                            timedelta(seconds=config["quote_max_age_seconds"]))

"""P0.21 authoritative *review register* verifier, NEVER numeric approval.

This pure module validates complete B2/S2 qualitative-source-to-parameter
traceability and ensures SIM research numbers cannot be laundered into
Forex 1:1 source-approved strategy defaults, real feeds, or trade signals.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from forex_trading.model import SignalStage

SCHEMA = "MFX_A04_P21_SOURCE_PARAMETER_REVIEW_V1"
VERSION = "SIM:P021-RESEARCH-REVIEW-001"
DOCUMENT_ID = "10-XQxdssBTanOyTX7tSqAymRfS8XRO9YRKtjk_BsXmA"
# Source paragraph IDs are zero-based from the frozen copied Google Doc.
# Source paragraphs express qualitative requirements, NOT numeric approval.
REQUIREMENTS: tuple[tuple[str, str, int, int], ...] = (
    ("causal_d1_h4_trend", "R0", 29, 117),
    ("confirmed_pivot_left_bars", "R0", 29, 117),
    ("confirmed_pivot_right_bars", "R0", 29, 117),
    ("structural_hl_lh_invalidation", "INVALIDATION", 33, 121),
    ("h1_zone_origin_identity", "R_C", 30, 118),
    ("h1_zone_lookback", "R_C", 30, 118),
    ("h1_true_range_atr_period", "R_C", 30, 118),
    ("h1_near_zone_atr_multiple", "R_C", 30, 118),
    ("h1_zone_width_atr_multiple", "R_C", 30, 118),
    ("m15_early_reversal_structure", "R_E", 31, 119),
    ("known_micro_break_confirm_rule", "R_F", 32, 120),
    ("anti_chase_max_atr_multiple", "R_F", 37, 125),
    ("bid_ask_spread_and_cost_gate", "R_F", 34, 122),
    ("session_dst_rollover_news_gate", "R_F", 37, 125),
    ("structural_sl_tp_net_r_gate", "R_F", 34, 122),
    ("event_expiry_and_idempotence", "R_F", 9, 9),
    ("licensed_source_first_known_revision", "R0", 9, 9),
    ("historical_walkforward_oos_qualification", "QA", 38, 126),
)
APPROVED_SOURCE_NUMERIC_DETECTORS = 0
BLOCKING_COUNT = len(REQUIREMENTS) * 2


@dataclass(frozen=True, slots=True)
class ReviewGateReceipt:
    source_doc_id: str
    register_version: str
    rule_ids: tuple[str, str]
    expected_requirement_count: int
    pending_source_numerical_approvals: int
    simulated_research_examples: int
    register_complete_for_review: bool
    stage: SignalStage = SignalStage.UNVERIFIED
    source_numeric_rules_approved: int = 0
    authenticated_approval_evidence: bool = False
    historical_oos_passed: bool = False
    source_data_license_verified: bool = False
    original_forex_1to1_numerical_parity: bool = False
    may_send_confirmed_buy_sell_signal: bool = False
    may_write_real_drive_market_cache: bool = False
    may_execute_broker_order: bool = False
    may_release: bool = False

    def as_record(self) -> dict[str, str | int | bool]:
        return {
            "source_doc_id": self.source_doc_id,
            "register_version": self.register_version,
            "entry_rule_ids": ",".join(self.rule_ids),
            "expected_requirement_count": self.expected_requirement_count,
            "pending_source_numerical_approvals": self.pending_source_numerical_approvals,
            "simulated_research_examples": self.simulated_research_examples,
            "register_complete_for_review": self.register_complete_for_review,
            "stage": self.stage.value,
            "source_numeric_rules_approved": self.source_numeric_rules_approved,
            "authenticated_approval_evidence": self.authenticated_approval_evidence,
            "historical_oos_passed": self.historical_oos_passed,
            "source_data_license_verified": self.source_data_license_verified,
            "original_forex_1to1_numerical_parity": self.original_forex_1to1_numerical_parity,
            "may_send_confirmed_buy_sell_signal": self.may_send_confirmed_buy_sell_signal,
            "may_write_real_drive_market_cache": self.may_write_real_drive_market_cache,
            "may_execute_broker_order": self.may_execute_broker_order,
            "may_release": self.may_release,
        }


def _mapping(value: object, label: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("P021_EXPECTED_MAPPING:" + label)
    if set(value) != keys:
        raise ValueError("P021_EXACT_SCHEMA_KEYS:" + label)
    if any(not isinstance(k, str) for k in value):
        raise ValueError("P021_NONSTRING_KEY:" + label)
    return value


def _exact(value: object, expected: object, label: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise ValueError("P021_VALUE_NOT_APPROVED:" + label)


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for k, v in pairs:
        if k in result:
            raise ValueError("P021_DUPLICATE_JSON_KEY:" + k)
        result[k] = v
    return result


def verify_parameter_review_register(data: object) -> ReviewGateReceipt:
    """Validate exact qualitative obligations; NO path to policy promotion.

    Do not accept an APPROVED status even with local evidence fields set.
    Approval needs separately verified provenance, versioned source policy
    and independent review not available in this research-only module.
    """
    root = _mapping(data, "root",
                    {"schema", "version", "source", "rules", "permissions"})
    _exact(root["schema"], SCHEMA, "schema")
    _exact(root["version"], VERSION, "version")
    source = _mapping(root["source"], "source", {
        "document_id", "baseline", "source_mode",
        "paragraph_index_basis", "approved_numerical_strategy",
    })
    for key, expected in (
        ("document_id", DOCUMENT_ID),
        ("baseline", "SOURCE_LOCKED_03_DETECTOR_AUDIT"),
        ("source_mode", "QUALITATIVE_MANIFEST_DRAFT_SPEC_PENDING"),
        ("paragraph_index_basis", "ZERO_BASED_GOOGLE_DOCS_READBACK"),
        ("approved_numerical_strategy", False),
    ):
        _exact(source[key], expected, "source." + key)
    permissions = _mapping(root["permissions"], "permissions", {
        "confirmed_buy_sell_alerts", "real_market_data", "drive_price_cache",
        "broker_order_execution", "release_ready",
    })
    for name, value in permissions.items():
        _exact(value, False, "permissions." + name)

    rules = root["rules"]
    if not isinstance(rules, list) or len(rules) != 2:
        raise ValueError("P021_EXACT_B2_S2_REQUIRED")
    sim_count = 0
    for pos, obj in enumerate(rules):
        rule = _mapping(obj, "rule", {
            "rule_id", "direction", "catalog_purpose",
            "approval_status", "requirements",
        })
        rule_id = ("B2", "S2")[pos]
        direction = ("LONG", "SHORT")[pos]
        purpose = ("ENTRY_LONG_CANDIDATE", "ENTRY_SHORT_CANDIDATE")[pos]
        for name, expected in (
            ("rule_id", rule_id), ("direction", direction),
            ("catalog_purpose", purpose),
            ("approval_status", "REVIEW_ONLY_UNAPPROVED"),
        ):
            _exact(rule[name], expected, "rule." + name)
        rows = rule["requirements"]
        if not isinstance(rows, list) or len(rows) != len(REQUIREMENTS):
            raise ValueError("P021_MISSING_OR_DUPLICATE_NUMERIC_OBLIGATIONS")
        for idx, row in enumerate(rows):
            field = _mapping(row, "requirement", {
                "id", "phase", "source_paragraph_index",
                "source_numeric_status", "approved_value",
                "research_sim_example", "independently_verified_evidence",
            })
            name, phase, b_index, s_index = REQUIREMENTS[idx]
            for key, expected in (
                ("id", name), ("phase", phase),
                ("source_paragraph_index", b_index if pos == 0 else s_index),
                ("source_numeric_status", "SPEC_PENDING_CALIBRATION_NOT_RUN"),
                ("approved_value", None),
                ("independently_verified_evidence", None),
            ):
                _exact(field[key], expected, rule_id + "." + name + "." + key)
            proposed = field["research_sim_example"]
            if proposed is not None:
                if (not isinstance(proposed, str)
                        or not proposed.startswith("SIM:")
                        or len(proposed) <= 4 or len(proposed) > 128
                        or any(c.isspace() for c in proposed)):
                    raise ValueError("P021_RESEARCH_NUMBER_CANNOT_APPEAR_APPROVED")
                sim_count += 1
    return ReviewGateReceipt(
        source_doc_id=DOCUMENT_ID, register_version=VERSION,
        rule_ids=("B2", "S2"), expected_requirement_count=BLOCKING_COUNT,
        pending_source_numerical_approvals=BLOCKING_COUNT,
        simulated_research_examples=sim_count, register_complete_for_review=True,
    )


def read_review_register(path: Path) -> tuple[ReviewGateReceipt, str]:
    if not isinstance(path, Path):
        raise TypeError("P021_TYPED_PATH_REQUIRED")
    raw = path.read_bytes()
    if not raw or len(raw) > 131072:
        raise ValueError("P021_EMPTY_OR_OVERSIZED_REGISTER")
    data: Any = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicates)
    receipt = verify_parameter_review_register(data)
    # Integrity fingerprint is NOT an attestation or an approval signature.
    return receipt, sha256(raw).hexdigest()

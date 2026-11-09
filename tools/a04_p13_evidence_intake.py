"""A04/P0.13: synthetic-only evidence attestation intake and negative receipts.

No vendor docs, live feeds, credentials or real licensing validation are read.
A syntactically complete synthetic attestation still has zero live authority.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

from tools.a04_p12_synthetic_qualification import read_report, verify_report

ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / "docs/MFX_A04_P13_EVIDENCE_INTAKE_BASELINE.json"
P12_BLOB = "b28a79961c20921af0f5984f7735f22f4dd03bc1"
BASE: dict[str, Any] = {
  "record_kind": "SYNTHETIC_ATTESTATION_ONLY",
  "evidence_origin": "SIMULATED_PLACEHOLDER",
  "evidence_ref": "SIM:EVIDENCE-0001",
  "provider_id": "SIM:PROVIDER",
  "account_scope": "SIM:ACCOUNT",
  "instrument_id": "SIM:EURUSD",
  "data_product_id": "SIM:FX-QUOTE-M15",
  "timeframe": "M15",
  "intended_use": "RESEARCH_ONLY",
  "vendor_terms_digest": "SIM:DIGEST-UNVERIFIED",
  "vendor_signature": "NONE",
  "license_effective_utc": "2026-11-09T00:00:00Z",
  "license_expires_utc": "2026-12-09T00:00:00Z",
  "evidence_first_known_utc": "2026-11-09T08:00:00Z",
  "review_decision_utc": "2026-11-09T09:00:00Z",
  "rights_api": "UNVERIFIED",
  "rights_history": "UNVERIFIED",
  "rights_cloud_storage": "UNVERIFIED",
  "rights_retention": "UNVERIFIED",
  "rights_redistribute": "UNVERIFIED",
  "rights_derived_use": "UNVERIFIED",
  "rights_replay": "UNVERIFIED",
  "capability_bidask": "UNVERIFIED",
  "capability_candles": "UNVERIFIED",
  "historical_bidask": "UNVERIFIED",
  "clock_first_known": "UNVERIFIED",
  "revision_corrections": "UNVERIFIED",
  "tz_calendar_dst": "UNVERIFIED",
  "broker_product_mapping": "UNVERIFIED",
  "rate_limit_quota": "UNVERIFIED",
  "source_access_enabled": False,
  "credentials_present": False,
  "external_document_verified": False,
  "human_approval_received": False,
  "cloud_budget_approved": False,
  "live_cache_approved": False,
  "real_market_observed": False,
  "runtime_enabled": False,
  "broker_trades_enabled": False
}
SCENARIOS: list[dict[str, Any]] = [
  {
    "id": "complete_synthetic_still_unqualified",
    "changes": {},
    "drop": [],
    "extra": {},
    "expected_reason": "EXTERNAL_VENDOR_EVIDENCE_REQUIRED"
  },
  {
    "id": "evidence_origin_real_claim",
    "changes": {
      "evidence_origin": "VENDOR_SERVED"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "NON_SYNTHETIC_EVIDENCE_FORBIDDEN"
  },
  {
    "id": "record_kind_real_claim",
    "changes": {
      "record_kind": "PROVIDER_ATTESTED"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "NON_SYNTHETIC_RECORD_FORBIDDEN"
  },
  {
    "id": "untrusted_real_url_evidence",
    "changes": {
      "evidence_ref": "https://vendor.example/private-doc"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "EVIDENCE_REFERENCE_NOT_SIMULATED"
  },
  {
    "id": "provider_not_simulated",
    "changes": {
      "provider_id": "TWELVE_DATA"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "NON_SYNTHETIC_PROVIDER_ID"
  },
  {
    "id": "account_not_simulated",
    "changes": {
      "account_scope": "LIVE_ACCOUNT"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "NON_SYNTHETIC_ACCOUNT_SCOPE"
  },
  {
    "id": "instrument_not_simulated",
    "changes": {
      "instrument_id": "EURUSD"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "NON_SYNTHETIC_INSTRUMENT"
  },
  {
    "id": "product_not_simulated",
    "changes": {
      "data_product_id": "FX_NATIVE_BIDASK"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "NON_SYNTHETIC_PRODUCT_ID"
  },
  {
    "id": "timeframe_unsupported",
    "changes": {
      "timeframe": "S1"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "UNSUPPORTED_TIMEFRAME"
  },
  {
    "id": "execution_intent_forged",
    "changes": {
      "intended_use": "LIVE_EXECUTION"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "UNAUTHORIZED_USE_CASE"
  },
  {
    "id": "vendor_terms_digest_claimed",
    "changes": {
      "vendor_terms_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "EVIDENCE_DIGEST_UNTRUSTED"
  },
  {
    "id": "vendor_signature_self_claim",
    "changes": {
      "vendor_signature": "VERIFIED"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "VENDOR_SIGNATURE_NOT_VERIFIED"
  },
  {
    "id": "explicit_denied_api_right",
    "changes": {
      "rights_api": "DENIED"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "EXPLICIT_RIGHTS_DENIED"
  },
  {
    "id": "self_claimed_api_right",
    "changes": {
      "rights_api": "CLAIMED_VERIFIED"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "SELF_ATTESTED_RIGHTS_FORBIDDEN"
  },
  {
    "id": "explicit_denied_history_right",
    "changes": {
      "rights_history": "DENIED"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "EXPLICIT_RIGHTS_DENIED"
  },
  {
    "id": "self_claimed_storage_right",
    "changes": {
      "rights_cloud_storage": "CLAIMED_VERIFIED"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "SELF_ATTESTED_RIGHTS_FORBIDDEN"
  },
  {
    "id": "explicit_denied_retention_right",
    "changes": {
      "rights_retention": "DENIED"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "EXPLICIT_RIGHTS_DENIED"
  },
  {
    "id": "self_claimed_redistribution_right",
    "changes": {
      "rights_redistribute": "CLAIMED_VERIFIED"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "SELF_ATTESTED_RIGHTS_FORBIDDEN"
  },
  {
    "id": "explicit_denied_replay_right",
    "changes": {
      "rights_replay": "DENIED"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "EXPLICIT_RIGHTS_DENIED"
  },
  {
    "id": "self_claimed_derived_right",
    "changes": {
      "rights_derived_use": "CLAIMED_VERIFIED"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "SELF_ATTESTED_RIGHTS_FORBIDDEN"
  },
  {
    "id": "claimed_native_bidask",
    "changes": {
      "capability_bidask": "CLAIMED_VERIFIED"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "SELF_ATTESTED_CAPABILITY_FORBIDDEN"
  },
  {
    "id": "claimed_historical_bidask",
    "changes": {
      "historical_bidask": "CLAIMED_VERIFIED"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "SELF_ATTESTED_CAPABILITY_FORBIDDEN"
  },
  {
    "id": "claimed_closed_candles",
    "changes": {
      "capability_candles": "CLAIMED_VERIFIED"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "SELF_ATTESTED_CAPABILITY_FORBIDDEN"
  },
  {
    "id": "claimed_first_known_clock",
    "changes": {
      "clock_first_known": "CLAIMED_VERIFIED"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "SELF_ATTESTED_CAPABILITY_FORBIDDEN"
  },
  {
    "id": "claimed_revision_history",
    "changes": {
      "revision_corrections": "CLAIMED_VERIFIED"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "SELF_ATTESTED_CAPABILITY_FORBIDDEN"
  },
  {
    "id": "claimed_dst_calendar",
    "changes": {
      "tz_calendar_dst": "CLAIMED_VERIFIED"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "SELF_ATTESTED_CAPABILITY_FORBIDDEN"
  },
  {
    "id": "claimed_broker_alignment",
    "changes": {
      "broker_product_mapping": "CLAIMED_VERIFIED"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "SELF_ATTESTED_CAPABILITY_FORBIDDEN"
  },
  {
    "id": "claimed_api_rate_limits",
    "changes": {
      "rate_limit_quota": "CLAIMED_VERIFIED"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "SELF_ATTESTED_CAPABILITY_FORBIDDEN"
  },
  {
    "id": "real_source_access_claim",
    "changes": {
      "source_access_enabled": True
    },
    "drop": [],
    "extra": {},
    "expected_reason": "FORGED_SOURCE_ACCESS"
  },
  {
    "id": "credentials_present_claim",
    "changes": {
      "credentials_present": True
    },
    "drop": [],
    "extra": {},
    "expected_reason": "CREDENTIALS_NOT_PERMITTED_IN_FIXTURES"
  },
  {
    "id": "external_doc_verified_claim",
    "changes": {
      "external_document_verified": True
    },
    "drop": [],
    "extra": {},
    "expected_reason": "FORGED_EXTERNAL_DOCUMENT_VERIFICATION"
  },
  {
    "id": "user_approval_forged",
    "changes": {
      "human_approval_received": True
    },
    "drop": [],
    "extra": {},
    "expected_reason": "FORGED_HUMAN_APPROVAL"
  },
  {
    "id": "cloud_budget_forged",
    "changes": {
      "cloud_budget_approved": True
    },
    "drop": [],
    "extra": {},
    "expected_reason": "FORGED_CLOUD_BUDGET_APPROVAL"
  },
  {
    "id": "live_drive_cache_claim",
    "changes": {
      "live_cache_approved": True
    },
    "drop": [],
    "extra": {},
    "expected_reason": "FORGED_LIVE_CACHE_AUTHORIZATION"
  },
  {
    "id": "real_market_seen_claim",
    "changes": {
      "real_market_observed": True
    },
    "drop": [],
    "extra": {},
    "expected_reason": "FORGED_REAL_MARKET_OBSERVATION"
  },
  {
    "id": "runtime_enabled_claim",
    "changes": {
      "runtime_enabled": True
    },
    "drop": [],
    "extra": {},
    "expected_reason": "FORGED_RUNTIME_AUTHORIZATION"
  },
  {
    "id": "broker_trade_enabled_claim",
    "changes": {
      "broker_trades_enabled": True
    },
    "drop": [],
    "extra": {},
    "expected_reason": "FORGED_BROKER_TRADING_AUTHORIZATION"
  },
  {
    "id": "expired_vendor_terms",
    "changes": {
      "license_expires_utc": "2026-11-09T08:00:00Z"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "LICENSE_TERMS_NOT_EFFECTIVE_AT_REVIEW"
  },
  {
    "id": "future_effective_vendor_terms",
    "changes": {
      "license_effective_utc": "2026-11-10T00:00:00Z"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "LICENSE_TERMS_NOT_EFFECTIVE_AT_REVIEW"
  },
  {
    "id": "future_first_known_proof",
    "changes": {
      "evidence_first_known_utc": "2026-11-09T09:00:01Z"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "FUTURE_KNOWN_EVIDENCE"
  },
  {
    "id": "invalid_first_known_timestamp",
    "changes": {
      "evidence_first_known_utc": "2026-11-09T16:00:00+07:00"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "INVALID_ATTESTATION_UTC_TIMESTAMP"
  },
  {
    "id": "invalid_calendar_day",
    "changes": {
      "review_decision_utc": "2026-02-30T09:00:00Z"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "INVALID_ATTESTATION_UTC_TIMESTAMP"
  },
  {
    "id": "missing_rights_field",
    "changes": {},
    "drop": [
      "rights_cloud_storage"
    ],
    "extra": {},
    "expected_reason": "ATTESTATION_SCHEMA_FIELDS_INVALID"
  },
  {
    "id": "unapproved_extra_evidence_field",
    "changes": {},
    "drop": [],
    "extra": {
      "external_vendor_secret": "UNAUTHORIZED"
    },
    "expected_reason": "ATTESTATION_SCHEMA_FIELDS_INVALID"
  },
  {
    "id": "unqualified_rights_enum",
    "changes": {
      "rights_cloud_storage": "MAYBE"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "UNREVIEWED_RIGHTS_STATUS"
  },
  {
    "id": "unqualified_capability_enum",
    "changes": {
      "historical_bidask": "DEPENDS"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "UNREVIEWED_CAPABILITY_STATUS"
  }
]
RIGHTS: tuple[str, ...] = ("rights_api", "rights_history", "rights_cloud_storage", "rights_retention", "rights_redistribute", "rights_derived_use", "rights_replay",)
CAPABILITIES: tuple[str, ...] = ("capability_bidask", "capability_candles", "historical_bidask", "clock_first_known", "revision_corrections", "tz_calendar_dst", "broker_product_mapping", "rate_limit_quota",)
EVIDENCE_REQUIRED: tuple[str, ...] = ("SIGNED_VENDOR_PRODUCT_SPECIFIC_TERMS_AND_LICENSE_HOLDER", "API_READ_HISTORY_STORAGE_DRIVE_RETENTION_REPLAY_DERIVATIVE_RIGHTS", "NATIVE_BID_ASK_BROKER_PRODUCT_SIDE_PROOF", "VERIFIABLE_FIRST_KNOWN_CLOSED_BAR_REVISION_DST_CALENDAR", "SUPPORTED_TF_RATE_LIMIT_COST_AND_CLOUD_BUDGET", "TRUSTED_EVIDENCE_ORIGIN_DIGEST_EFFECTIVE_DATE_AND_MANUAL_REVIEW",)
AUTHORITY_FLAGS: tuple[str, ...] = ("vendor_terms_verified", "licensed_read_approved", "broker_native_bidask_verified", "rights_drive_storage_verified", "historical_replay_verified", "causal_clock_verified", "rate_limit_cost_verified", "real_market_observed", "human_runtime_authorization", "cloud_budget_approved", "live_cache_authorized", "adapter_runtime_enabled", "executable_tp_sl_verified", "trading_authorized",)
UTC_FORMAT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or UTC_FORMAT.fullmatch(value) is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def evaluate_attestation(value: dict[str, Any]) -> str:
    """Return a denial or manual-evidence-required status; never permission."""
    if set(value) != set(BASE):
        return "ATTESTATION_SCHEMA_FIELDS_INVALID"
    if value["record_kind"] != "SYNTHETIC_ATTESTATION_ONLY":
        return "NON_SYNTHETIC_RECORD_FORBIDDEN"
    if value["evidence_origin"] != "SIMULATED_PLACEHOLDER":
        return "NON_SYNTHETIC_EVIDENCE_FORBIDDEN"
    if not isinstance(value["evidence_ref"], str) or not value["evidence_ref"].startswith("SIM:"):
        return "EVIDENCE_REFERENCE_NOT_SIMULATED"
    for field, reason in (
        ("provider_id", "NON_SYNTHETIC_PROVIDER_ID"),
        ("account_scope", "NON_SYNTHETIC_ACCOUNT_SCOPE"),
        ("instrument_id", "NON_SYNTHETIC_INSTRUMENT"),
        ("data_product_id", "NON_SYNTHETIC_PRODUCT_ID"),
    ):
        if not isinstance(value[field], str) or not value[field].startswith("SIM:"):
            return reason
    if value["timeframe"] not in ("M5", "M15", "M30", "H1", "H4", "D1", "W1"):
        return "UNSUPPORTED_TIMEFRAME"
    if value["intended_use"] != "RESEARCH_ONLY":
        return "UNAUTHORIZED_USE_CASE"
    if value["vendor_terms_digest"] != "SIM:DIGEST-UNVERIFIED":
        return "EVIDENCE_DIGEST_UNTRUSTED"
    if value["vendor_signature"] != "NONE":
        return "VENDOR_SIGNATURE_NOT_VERIFIED"
    for key, reason in (
        ("source_access_enabled", "FORGED_SOURCE_ACCESS"),
        ("credentials_present", "CREDENTIALS_NOT_PERMITTED_IN_FIXTURES"),
        ("external_document_verified", "FORGED_EXTERNAL_DOCUMENT_VERIFICATION"),
        ("human_approval_received", "FORGED_HUMAN_APPROVAL"),
        ("cloud_budget_approved", "FORGED_CLOUD_BUDGET_APPROVAL"),
        ("live_cache_approved", "FORGED_LIVE_CACHE_AUTHORIZATION"),
        ("real_market_observed", "FORGED_REAL_MARKET_OBSERVATION"),
        ("runtime_enabled", "FORGED_RUNTIME_AUTHORIZATION"),
        ("broker_trades_enabled", "FORGED_BROKER_TRADING_AUTHORIZATION"),
    ):
        if value[key] is not False:
            return reason
    for key in RIGHTS:
        if value[key] == "DENIED":
            return "EXPLICIT_RIGHTS_DENIED"
        if value[key] == "CLAIMED_VERIFIED":
            return "SELF_ATTESTED_RIGHTS_FORBIDDEN"
        if value[key] != "UNVERIFIED":
            return "UNREVIEWED_RIGHTS_STATUS"
    for key in CAPABILITIES:
        if value[key] == "CLAIMED_VERIFIED":
            return "SELF_ATTESTED_CAPABILITY_FORBIDDEN"
        if value[key] != "UNVERIFIED":
            return "UNREVIEWED_CAPABILITY_STATUS"
    date_keys = (
        "license_effective_utc", "license_expires_utc",
        "evidence_first_known_utc", "review_decision_utc",
    )
    dates = {k: _utc(value[k]) for k in date_keys}
    if any(d is None for d in dates.values()):
        return "INVALID_ATTESTATION_UTC_TIMESTAMP"
    start, end, first, decision = (
        dates["license_effective_utc"], dates["license_expires_utc"],
        dates["evidence_first_known_utc"], dates["review_decision_utc"],
    )
    if start is None or end is None or first is None or decision is None:
        return "INVALID_ATTESTATION_UTC_TIMESTAMP"
    if decision < start or decision >= end or start >= end:
        return "LICENSE_TERMS_NOT_EFFECTIVE_AT_REVIEW"
    if first > decision:
        return "FUTURE_KNOWN_EVIDENCE"
    return "EXTERNAL_VENDOR_EVIDENCE_REQUIRED"


def scenario_payload(case: dict[str, Any]) -> dict[str, Any]:
    value = dict(BASE)
    changes, drop, extra = case["changes"], case["drop"], case["extra"]
    if not isinstance(changes, dict) or not isinstance(drop, list) or not isinstance(extra, dict):
        raise ValueError("P013_INVALID_CASE_SHAPE")
    if not set(changes).issubset(BASE) or len(set(drop)) != len(drop) or (
            set(extra) & set(BASE)):
        raise ValueError("P013_UNAUTHORIZED_CASE_MUTATION")
    value.update(changes)
    for key in drop:
        if key not in value:
            raise ValueError("P013_UNKNOWN_DROPPED_FIELD")
        del value[key]
    value.update(extra)
    return value


def expected_report() -> dict[str, Any]:
    previous = read_report()
    verify_report(previous)
    if previous["scenario_count"] != 32 or previous["p11_frozen_field_obligations"] != 58:
        raise ValueError("P013_P12_ANCESTOR_DRIFT")
    if len(SCENARIOS) != 46 or len({x["id"] for x in SCENARIOS}) != len(SCENARIOS):
        raise ValueError("P013_EXACT_CASE_SET_REQUIRED")
    receipts: list[dict[str, Any]] = []
    for case in SCENARIOS:
        result = evaluate_attestation(scenario_payload(case))
        if result != case["expected_reason"]:
            raise ValueError("P013_INCORRECT_NEGATIVE_CASE:" + case["id"])
        if result == "VERIFIED" or result == "AUTHORIZED":
            raise ValueError("P013_SYNTHETIC_CANNOT_AUTHORIZE")
        receipts.append({
            "scenario_id": case["id"], "reason": result,
            "source": "SYNTHETIC_ONLY", "external_authority": False,
            "may_read_vendor": False, "may_write_drive_cache": False,
            "may_trade": False,
        })
    return {
        "schema_version": 1,
        "kind": "MFX_A04_P13_EVIDENCE_ATTESTATION_INTAKE_DENIAL_GATE",
        "original_forex_source_sha": "7e1c1c012b1b189be5ad7b9d07756eac012a8309",
        "original_mfx_102_blob_import": "6ee5e7c07baf4ea8f06a28889175808ea53c2316",
        "p12_synthetic_gate_blob_sha": P12_BLOB,
        "p12_negative_scenario_count": 32,
        "rights_dimensions": list(RIGHTS),
        "capability_dimensions": list(CAPABILITIES),
        "scenario_count": len(SCENARIOS), "base_attestation": BASE,
        "scenarios": SCENARIOS, "results": receipts,
        "missing_external_evidence": list(EVIDENCE_REQUIRED),
        "authority_flags": {flag: False for flag in AUTHORITY_FLAGS},
        "outcome": "ATTESTATION_SCHEMA_AND_NEGATIVE_SCENARIOS_ONLY_NEEDS_EXTERNAL_PROOF",
        "release_status": "BLOCKED",
    }


def read_baseline() -> dict[str, Any]:
    if PIN.is_symlink() or not PIN.is_file():
        raise ValueError("P013_UNSAFE_OR_MISSING_BASELINE")
    obj: Any = json.loads(PIN.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("P013_BASELINE_NOT_OBJECT")
    return obj


def verify_baseline(value: dict[str, Any]) -> dict[str, Any]:
    actual = expected_report()
    if value != actual:
        raise ValueError("P013_PINNED_ATTESTATION_OR_RIGHTS_TAMPERED")
    if any(row["may_read_vendor"] or row["may_trade"] or row["may_write_drive_cache"]
           for row in actual["results"]):
        raise ValueError("P013_FORGED_OPERATION_AUTHORIZATION")
    return {
        "status": "P013_PINNED_SYNTHETIC_EVIDENCE_DENIAL_PASS",
        "cases": len(actual["results"]),
        "rights_dimensions": len(RIGHTS),
        "capability_dimensions": len(CAPABILITIES),
        "external_evidence_received": False,
        "live_data_authorized": False,
        "trading_authorized": False,
    }

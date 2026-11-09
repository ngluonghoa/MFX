"""A04/P0.12 pure synthetic, fail-closed quote/clock/rights scenario validator.

Only synthetic SIM: symbols and fabricated price/time data are permitted.
It NEVER grants real-market data, vendor entitlement, BID/ASK broker quality,
Google Drive live cache writes, runtime plugins, releases or broker orders.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
from typing import Any

from tools.a04_p11_field_lineage import read_pinned, verify_exact

ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / "docs/MFX_A04_P12_SYNTHETIC_GATE_BASELINE.json"
P11_BLOB = "8965ce6794dbac4abb850c6d18e25acdc358b4a7"
BASE: dict[str, Any] = {
  "fixture_kind": "SYNTHETIC_UNTRUSTED_NO_VENDOR_DATA",
  "symbol": "SIM:EURUSD",
  "timeframe": "M15",
  "price_basis": "SIMULATED_NATIVE_BID_ASK",
  "bid": "1.1000",
  "ask": "1.1002",
  "bid_native_simulated": True,
  "ask_native_simulated": True,
  "broker_product_matched_simulated": True,
  "quote_observed_utc": "2026-11-09T09:00:00Z",
  "bar_closed_utc": "2026-11-09T08:45:00Z",
  "first_known_utc": "2026-11-09T08:45:02Z",
  "revision_known_utc": "2026-11-09T08:45:03Z",
  "decision_utc": "2026-11-09T09:00:05Z",
  "max_age_seconds": 120,
  "calendar_state": "CONFIRMED_SIMULATED_UTC",
  "source_state": "AVAILABLE_SIMULATED",
  "rights_reference": "SYNTHETIC_ONLY_NO_VENDOR_ENTITLEMENT",
  "external_rights_verified": False,
  "drive_retention_verified": False,
  "can_trade": False
}
CASES: list[dict[str, Any]] = [
  {
    "id": "clean_structural_but_no_vendor_entitlement",
    "changes": {},
    "drop": [],
    "extra": {},
    "expected_reason": "BLOCKED_EXTERNAL_RIGHTS_UNVERIFIED"
  },
  {
    "id": "indicative_not_native_bidask",
    "changes": {
      "price_basis": "INDICATIVE_OHLCV"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "INDICATIVE_NOT_EXECUTION"
  },
  {
    "id": "broker_product_mismatch",
    "changes": {
      "broker_product_matched_simulated": False
    },
    "drop": [],
    "extra": {},
    "expected_reason": "BROKER_PRODUCT_MISMATCH"
  },
  {
    "id": "native_bid_missing",
    "changes": {
      "bid_native_simulated": False
    },
    "drop": [],
    "extra": {},
    "expected_reason": "NATIVE_BID_MISSING"
  },
  {
    "id": "native_ask_missing",
    "changes": {
      "ask_native_simulated": False
    },
    "drop": [],
    "extra": {},
    "expected_reason": "NATIVE_ASK_MISSING"
  },
  {
    "id": "crossed_bid_ask",
    "changes": {
      "ask": "1.0999"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "CROSSED_BID_ASK"
  },
  {
    "id": "nonpositive_bid",
    "changes": {
      "bid": "0"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "INVALID_BID_ASK"
  },
  {
    "id": "nan_bid",
    "changes": {
      "bid": "NaN"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "INVALID_BID_ASK"
  },
  {
    "id": "float_not_decimal_string",
    "changes": {
      "bid": 1.1
    },
    "drop": [],
    "extra": {},
    "expected_reason": "INVALID_BID_ASK"
  },
  {
    "id": "future_quote",
    "changes": {
      "quote_observed_utc": "2026-11-09T09:00:06Z"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "FUTURE_QUOTE"
  },
  {
    "id": "stale_quote",
    "changes": {
      "quote_observed_utc": "2026-11-09T08:50:00Z"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "STALE_QUOTE"
  },
  {
    "id": "future_first_known",
    "changes": {
      "first_known_utc": "2026-11-09T09:00:06Z"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "FUTURE_FIRST_KNOWN"
  },
  {
    "id": "provisional_bar",
    "changes": {
      "bar_closed_utc": "2026-11-09T09:00:06Z"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "BAR_NOT_CLOSED"
  },
  {
    "id": "future_revision",
    "changes": {
      "revision_known_utc": "2026-11-09T09:00:06Z"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "FUTURE_REVISION"
  },
  {
    "id": "first_known_before_close",
    "changes": {
      "first_known_utc": "2026-11-09T08:44:59Z"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "FIRST_KNOWN_BEFORE_BAR_CLOSE"
  },
  {
    "id": "revision_before_first_known",
    "changes": {
      "revision_known_utc": "2026-11-09T08:45:01Z"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "REVISION_BEFORE_FIRST_KNOWN"
  },
  {
    "id": "calendar_dst_unverified",
    "changes": {
      "calendar_state": "UNVERIFIED_DST"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "CALENDAR_UNVERIFIED"
  },
  {
    "id": "non_utc_offset_timestamp",
    "changes": {
      "first_known_utc": "2026-11-09T15:45:02+07:00"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "INVALID_UTC_TIMESTAMP"
  },
  {
    "id": "unsupported_timeframe",
    "changes": {
      "timeframe": "S1"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "UNSUPPORTED_TIMEFRAME"
  },
  {
    "id": "unqualified_real_symbol",
    "changes": {
      "symbol": "EURUSD"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "NON_SYNTHETIC_SYMBOL"
  },
  {
    "id": "rights_reference_missing",
    "changes": {
      "rights_reference": ""
    },
    "drop": [],
    "extra": {},
    "expected_reason": "RIGHTS_REFERENCE_MISSING"
  },
  {
    "id": "source_rate_limited",
    "changes": {
      "source_state": "RATE_LIMITED"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "SOURCE_RATE_LIMITED"
  },
  {
    "id": "source_missing",
    "changes": {
      "source_state": "MISSING"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "SOURCE_MISSING"
  },
  {
    "id": "forged_vendor_entitlement",
    "changes": {
      "external_rights_verified": True
    },
    "drop": [],
    "extra": {},
    "expected_reason": "FORGED_VENDOR_ENTITLEMENT"
  },
  {
    "id": "forged_drive_retention",
    "changes": {
      "drive_retention_verified": True
    },
    "drop": [],
    "extra": {},
    "expected_reason": "FORGED_DRIVE_RETENTION"
  },
  {
    "id": "forged_trade_authority",
    "changes": {
      "can_trade": True
    },
    "drop": [],
    "extra": {},
    "expected_reason": "FORGED_TRADING_AUTHORITY"
  },
  {
    "id": "omitted_required_ask",
    "changes": {},
    "drop": [
      "ask"
    ],
    "extra": {},
    "expected_reason": "SCHEMA_KEYS_INVALID"
  },
  {
    "id": "unexpected_runtime_field",
    "changes": {},
    "drop": [],
    "extra": {
      "runtime_enabled": True
    },
    "expected_reason": "SCHEMA_KEYS_INVALID"
  },
  {
    "id": "invalid_staleness_threshold",
    "changes": {
      "max_age_seconds": -1
    },
    "drop": [],
    "extra": {},
    "expected_reason": "INVALID_STALENESS_POLICY"
  },
  {
    "id": "impossible_calendar_timestamp",
    "changes": {
      "decision_utc": "2026-02-30T09:00:05Z"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "INVALID_UTC_TIMESTAMP"
  },
  {
    "id": "external_fixture_kind",
    "changes": {
      "fixture_kind": "REAL_MARKET"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "NON_SYNTHETIC_FIXTURE_BLOCKED"
  },
  {
    "id": "unsupported_source_state",
    "changes": {
      "source_state": "UNKNOWN"
    },
    "drop": [],
    "extra": {},
    "expected_reason": "SOURCE_UNVERIFIED"
  }
]
DENIED: tuple[str, ...] = (
    "real_market_data_observed", "vendor_entitlement_verified",
    "broker_native_bidask_qualified", "first_known_real_feed_qualified",
    "drive_cache_writes_authorized", "runtime_plugin_activated",
    "release_signed", "broker_trades_authorized",
)
TIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
DECIMAL_PATTERN = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or TIME_PATTERN.fullmatch(value) is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def _price(value: Any) -> Decimal | None:
    if not isinstance(value, str) or DECIMAL_PATTERN.fullmatch(value) is None:
        return None
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    if not number.is_finite() or number <= 0:
        return None
    return number


def evaluate_synthetic(payload: dict[str, Any]) -> str:
    """Return rejection or structural-only finding, NEVER executable approval."""
    if set(payload) != set(BASE):
        return "SCHEMA_KEYS_INVALID"
    if payload["fixture_kind"] != "SYNTHETIC_UNTRUSTED_NO_VENDOR_DATA":
        return "NON_SYNTHETIC_FIXTURE_BLOCKED"
    if payload["external_rights_verified"] is not False:
        return "FORGED_VENDOR_ENTITLEMENT"
    if payload["drive_retention_verified"] is not False:
        return "FORGED_DRIVE_RETENTION"
    if payload["can_trade"] is not False:
        return "FORGED_TRADING_AUTHORITY"
    if not isinstance(payload["symbol"], str) or not payload["symbol"].startswith("SIM:"):
        return "NON_SYNTHETIC_SYMBOL"
    if payload["timeframe"] not in ("M5", "M15", "M30", "H1", "H4", "D1", "W1"):
        return "UNSUPPORTED_TIMEFRAME"
    if payload["price_basis"] != "SIMULATED_NATIVE_BID_ASK":
        return "INDICATIVE_NOT_EXECUTION"
    if payload["broker_product_matched_simulated"] is not True:
        return "BROKER_PRODUCT_MISMATCH"
    if payload["bid_native_simulated"] is not True:
        return "NATIVE_BID_MISSING"
    if payload["ask_native_simulated"] is not True:
        return "NATIVE_ASK_MISSING"
    bid, ask = _price(payload["bid"]), _price(payload["ask"])
    if bid is None or ask is None:
        return "INVALID_BID_ASK"
    if bid > ask:
        return "CROSSED_BID_ASK"
    if not isinstance(payload["rights_reference"], str) or not payload["rights_reference"].startswith("SYNTHETIC_"):
        return "RIGHTS_REFERENCE_MISSING"
    if payload["calendar_state"] != "CONFIRMED_SIMULATED_UTC":
        return "CALENDAR_UNVERIFIED"
    if payload["source_state"] == "RATE_LIMITED":
        return "SOURCE_RATE_LIMITED"
    if payload["source_state"] == "MISSING":
        return "SOURCE_MISSING"
    if payload["source_state"] != "AVAILABLE_SIMULATED":
        return "SOURCE_UNVERIFIED"
    age = payload["max_age_seconds"]
    if not isinstance(age, int) or isinstance(age, bool) or age <= 0 or age > 86400:
        return "INVALID_STALENESS_POLICY"
    keys = ("quote_observed_utc", "bar_closed_utc", "first_known_utc",
            "revision_known_utc", "decision_utc")
    times = {key: _utc(payload[key]) for key in keys}
    if any(value is None for value in times.values()):
        return "INVALID_UTC_TIMESTAMP"
    quote = times["quote_observed_utc"]
    closed = times["bar_closed_utc"]
    first = times["first_known_utc"]
    revision = times["revision_known_utc"]
    decision = times["decision_utc"]
    if quote is None or closed is None or first is None or revision is None or decision is None:
        return "INVALID_UTC_TIMESTAMP"
    if quote > decision:
        return "FUTURE_QUOTE"
    if closed > decision:
        return "BAR_NOT_CLOSED"
    if first > decision:
        return "FUTURE_FIRST_KNOWN"
    if revision > decision:
        return "FUTURE_REVISION"
    if first < closed:
        return "FIRST_KNOWN_BEFORE_BAR_CLOSE"
    if revision < first:
        return "REVISION_BEFORE_FIRST_KNOWN"
    if (decision - quote).total_seconds() > age:
        return "STALE_QUOTE"
    # No fake rights evidence ever upgrades this structural-only result.
    return "BLOCKED_EXTERNAL_RIGHTS_UNVERIFIED"


def _fixture(case: dict[str, Any]) -> dict[str, Any]:
    payload = dict(BASE)
    changes = case["changes"]
    removals = case["drop"]
    additions = case["extra"]
    if (not isinstance(changes, dict) or not isinstance(additions, dict)
            or not isinstance(removals, list) or len(set(removals)) != len(removals)):
        raise ValueError("P012_MALFORMED_CASE")
    if not set(changes).issubset(BASE) or set(additions) & set(BASE):
        raise ValueError("P012_UNAUTHORIZED_MUTATION_SHAPE")
    payload.update(changes)
    for key in removals:
        if key not in BASE:
            raise ValueError("P012_DROP_NONEXISTENT_FIELD")
        del payload[key]
    payload.update(additions)
    return payload


def expected_report() -> dict[str, Any]:
    lineage = read_pinned()
    verify_exact(lineage)
    if (lineage["summary"]["field_obligations"] != 58 or
            lineage["summary"]["working_adapters"] != 0):
        raise ValueError("P012_P11_NOT_SOURCE_LOCKED")
    if len(CASES) != 32 or len({x["id"] for x in CASES}) != len(CASES):
        raise ValueError("P012_CASE_SET_DRIFT")
    results: list[dict[str, Any]] = []
    for case in CASES:
        result = evaluate_synthetic(_fixture(case))
        if result != case["expected_reason"]:
            raise ValueError("P012_EXPECTED_NEGATIVE_REASON_DRIFT:" + case["id"])
        if not result or result == "APPROVED":
            raise ValueError("P012_SYNTHETIC_CANNOT_AUTHORIZE")
        results.append({
            "scenario_id": case["id"],
            "reason_code": result,
            "source_kind": "SYNTHETIC_ONLY",
            "may_write_real_cache": False,
            "may_trade": False,
        })
    return {
        "schema_version": 1,
        "kind": "MFX_A04_P12_SYNTHETIC_FAIL_CLOSED_PROVENANCE_QUOTE_CLOCK",
        "frozen_forex_source_commit": "7e1c1c012b1b189be5ad7b9d07756eac012a8309",
        "mfx_initial_exact_import": "6ee5e7c07baf4ea8f06a28889175808ea53c2316",
        "p11_crosswalk_git_blob_sha": P11_BLOB,
        "p11_frozen_field_obligations": 58,
        "scenario_count": len(CASES),
        "source_and_rights_evidence": "SYNTHETIC_ONLY_NO_LICENCED_VENDOR_FEED_OR_STORAGE_RIGHTS",
        "base_fixture": BASE,
        "scenarios": CASES,
        "results": results,
        "absolute_denials": {k: False for k in DENIED},
        "acceptance_label": "NEGATIVE_CONTRACT_SIMULATION_ONLY_NOT_PRODUCTION",
        "decision": "NO_RUNTIME_NO_SOURCE_EDITS_NO_VENDOR_OR_TRADE_AUTHORITY",
    }


def verify_report(report: dict[str, Any]) -> dict[str, Any]:
    expected = expected_report()
    if report != expected:
        raise ValueError("P012_CASE_OR_AUTHORITY_TAMPERED")
    if any(row["may_trade"] or row["may_write_real_cache"] for row in expected["results"]):
        raise ValueError("P012_FORGED_EXECUTION_AUTHORITY")
    return {
        "status": "P012_SYNTHETIC_NEGATIVE_GATES_PASS",
        "cases": len(expected["results"]),
        "real_feed_rights": False,
        "runtime_adapters": 0,
        "can_trade": False,
    }


def read_report() -> dict[str, Any]:
    if PIN.is_symlink() or not PIN.is_file():
        raise ValueError("P012_PIN_MISSING_OR_UNSAFE")
    obj: Any = json.loads(PIN.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("P012_UNTYPED_PIN")
    return obj

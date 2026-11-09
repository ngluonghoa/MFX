"""A04/P0.14 PUBLIC vendor-document register structure gate, not a live entitlement.

No network access, Twelve Data credentials, user subscriptions or source runtime.
CI validates that public-doc summaries cannot become account-specific approval.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.a04_p13_evidence_intake import read_baseline, verify_baseline

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs/MFX_A04_P14_PUBLIC_VENDOR_EVIDENCE.json"
P13_BLOB = "a6cd9e44d957b8f07558041e9c725cfd9468afd9"
DOC_URLS: dict[str, str] = {
  "terms": "https://twelvedata.com/terms",
  "fxv2": "https://support.twelvedata.com/en/articles/12520817-forex-api-v2",
  "usage": "https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage",
  "ws": "https://twelvedata.com/docs/websocket/websocket-getting-started",
  "fx": "https://twelvedata.com/exchanges/physical_currency?group=reference",
  "history": "https://support.twelvedata.com/en/articles/5214728-getting-historical-data",
  "pricing": "https://twelvedata.com/pricing"
}
PUBLIC_FINDING_IDS: tuple[str, ...] = ("TDF-01", "TDF-02", "TDF-03", "TDF-04", "TDF-05", "TDF-06", "TDF-07", "TDF-08", "TDF-09", "TDF-10",)
RIGHTS_KEYS: tuple[str, ...] = ("rights_api", "rights_history", "rights_cloud_storage", "rights_retention", "rights_redistribute", "rights_derived_use", "rights_replay",)
CAPABILITY_KEYS: tuple[str, ...] = ("capability_bidask", "capability_candles", "historical_bidask", "clock_first_known", "revision_corrections", "tz_calendar_dst", "broker_product_mapping", "rate_limit_quota",)
MANDATORY_FALSE: tuple[str, ...] = (
    "evidence_provided_for_mfx_account", "real_provider_api_called",
    "cloud_cache_write_authorized", "historical_broker_bidask_proven",
    "temporal_revision_parity_proven", "signed_agreement_obtained",
    "source_runtime_modified", "broker_trading_authorized",
)
VALID_STATES: tuple[str, ...] = (
    "ACCOUNT_PRODUCT_LICENSE_UNVERIFIED",
    "CONDITIONAL_PUBLIC_EXAMPLE_NOT_QUALIFIED",
    "PUBLIC_ENDPOINT_DESCRIBED_ACCOUNT_UNVERIFIED",
    "NOT_ESTABLISHED_BY_PUBLIC_DOCS",
    "PUBLIC_PRICING_CONTEXT_ACCOUNT_UNVERIFIED",
)


def read_register() -> dict[str, Any]:
    if REGISTRY.is_symlink() or not REGISTRY.is_file():
        raise ValueError("P014_UNSAFE_OR_MISSING_PUBLIC_REGISTER")
    data: Any = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("P014_PUBLIC_REGISTER_NOT_OBJECT")
    return data


def verify_public_register(doc: dict[str, Any]) -> dict[str, Any]:
    prev = read_baseline()
    verify_baseline(prev)
    if prev["scenario_count"] != 46 or P13_BLOB != "a6cd9e44d957b8f07558041e9c725cfd9468afd9":
        raise ValueError("P014_P13_PROVENANCE_DRIFT")
    if doc.get("schema_version") != 1 or doc.get("kind") != "MFX_A04_P14_OFFICIAL_PUBLIC_DOCS_ACCOUNT_RIGHTS_UNVERIFIED":
        raise ValueError("P014_INVALID_DOCUMENT_TYPE")
    if doc.get("p13_public_git_blob_sha") != P13_BLOB or doc.get("p13_synthetic_case_count") != 46:
        raise ValueError("P014_P13_SHA_OR_CASE_DRIFT")
    if doc.get("source_scope") != "PUBLIC_OFFICIAL_DOCUMENTATION_ONLY_NO_ACCOUNT_OR_API_ACCESS":
        raise ValueError("P014_SCOPE_ESCALATION")
    sources = doc.get("official_sources")
    if not isinstance(sources, dict) or {
            k: v.get("url") for k, v in sources.items() if isinstance(v, dict)} != DOC_URLS:
        raise ValueError("P014_PUBLIC_SOURCE_URL_DRIFT")
    if set(sources) != set(DOC_URLS):
        raise ValueError("P014_PUBLIC_SOURCE_EXTRA_OR_MISSING")
    if any(v.get("origin") != "Twelve Data official public website or official support"
           for v in sources.values()):
        raise ValueError("P014_UNKNOWN_SOURCE_ORIGIN")
    findings = doc.get("findings")
    if (not isinstance(findings, list) or
            tuple(x.get("id") for x in findings if isinstance(x, dict)) != PUBLIC_FINDING_IDS):
        raise ValueError("P014_FINDING_SET_DRIFT")
    valid_classes = {
        "PUBLIC_TERMS_RESTRICTION", "PUBLIC_TECHNICAL_DESCRIPTION",
        "CONDITIONAL_PUBLIC_EXAMPLE", "PUBLIC_PRICING_CONTEXT",
    }
    for item in findings:
        if (not isinstance(item, dict) or item.get("source") not in DOC_URLS
                or item.get("classification") not in valid_classes
                or not all(isinstance(item.get(k), str) and item[k].strip()
                           for k in ("section", "public_finding", "mfx_impact"))):
            raise ValueError("P014_UNSUPPORTED_SOURCE_FINDING")
    requirements = doc.get("requirements")
    expected_keys = list(RIGHTS_KEYS) + list(CAPABILITY_KEYS)
    if (not isinstance(requirements, list) or len(requirements) != 15 or
            [r.get("key") for r in requirements if isinstance(r, dict)] != expected_keys):
        raise ValueError("P014_RIGHTS_AND_CAPABILITY_KEYS_CHANGED")
    for item in requirements:
        refs = item.get("public_refs")
        if (item.get("state") not in VALID_STATES or not isinstance(refs, list)
                or not refs or any(ref not in PUBLIC_FINDING_IDS for ref in refs)
                or not isinstance(item.get("required_written_proof"), str)
                or not item["required_written_proof"].strip()):
            raise ValueError("P014_FAKE_VERIFIED_ENTITLEMENT_OR_MISSING_PROOF")
    questions = doc.get("vendor_inquiry_questions")
    if (not isinstance(questions, list) or len(questions) != 6 or
            [x.get("id") for x in questions if isinstance(x, dict)] != [
                "TD-Q01", "TD-Q02", "TD-Q03", "TD-Q04", "TD-Q05", "TD-Q06"]):
        raise ValueError("P014_VENDOR_QUESTIONS_NOT_SIX")
    for question in questions:
        if not isinstance(question.get("question"), str) or not question["question"].strip():
            raise ValueError("P014_VENDOR_QUESTION_MISSING")
    if any(doc.get(key) is not False for key in MANDATORY_FALSE):
        raise ValueError("P014_UNAUTHORIZED_ACCOUNT_DATA_SOURCE_OR_TRADES")
    if (doc.get("architecture_decision") != "STOP_REAL_DATA_AND_DRIVE_CACHE_UNTIL_ACCOUNT_PRODUCT_SPECIFIC_WRITTEN_RIGHTS"
            or doc.get("review_status") != "PUBLIC_DOCUMENTATION_RESEARCH_ONLY"):
        raise ValueError("P014_UNAUTHORIZED_RELEASE_OR_PRODUCT_DECISION")
    return {
        "status": "P014_PUBLIC_OFFICIAL_DOCS_REVIEWED_ACCOUNT_RIGHTS_UNVERIFIED",
        "public_findings": len(findings), "rights": len(RIGHTS_KEYS),
        "capabilities": len(CAPABILITY_KEYS), "vendor_questions": len(questions),
        "licensed_storage_verified": False, "historical_bidask_verified": False,
        "can_activate_provider": False, "can_write_real_drive_cache": False,
        "can_trade": False,
    }

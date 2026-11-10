"""P0.35 — secure, read-only intake for proposed B2/S2 source-owner rules.

This module accepts PUBLIC-SAFE suggested decisions, never approvals.
An untrusted SHA256 evidence reference is merely a content fingerprint, NOT
an authenticated owner signature, numeric parity, vendor license or permission
to broadcast Forex BUY/SELL. No broker-order integration is ever allowed.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

from mfx_research.p034_sim_adversarial_review import (
    DOSSIER_BLOB_SHA, P021_BLOB_SHA, verify_owner_decision_dossier,
)

SCHEMA = "MFX_A04_P35_OWNER_EVIDENCE_PROPOSAL_INTAKE_V1"
VERSION = "MFX:P035-PUBLIC_SAFE_REVIEW_PROPOSAL-001"
MODE = "PUBLIC_SAFE_PROPOSALS_NOT_APPROVALS"
TEMPLATE = Path("docs/MFX_A04_P35_PUBLIC_SAFE_OWNER_PROPOSAL_TEMPLATE.json")
MAX_PROPOSALS = 36
MAX_INPUT_BYTES = 65536
INTENTS = ("PROPOSE_FORMULA", "SUGGEST_DEFER", "SUGGEST_REJECT")
PROPOSED_ROW_KEYS = frozenset((
    "rule_id", "requirement_id", "phase", "source_paragraph_index",
    "review_intent", "formula", "units", "causal_asof_notes",
    "evidence_sha256", "rationale",
))
FORBIDDEN_PUBLIC_TEXT = re.compile(
    r"(?i)(?:https?://|@|\b(?:password|passwd|api[_-]?key|bearer|"
    r"access[_-]?token|authorization|private[_-]?key|secret)\b)"
)
_SHA256 = re.compile(r"[a-f0-9]{64}")


def _same(actual: object, expected: object, label: str) -> None:
    if type(actual) is not type(expected) or actual != expected:
        raise ValueError("P035_SEALED_PROVENANCE_OR_VERSION_MISMATCH:" + label)


def _keys(obj: object, expected: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(obj, dict) or set(obj) != expected:
        raise ValueError("P035_EXACT_PUBLIC_SCHEMA_REQUIRED:" + label)
    if any(type(k) is not str for k in obj):
        raise ValueError("P035_EXACT_PUBLIC_SCHEMA_REQUIRED:" + label)
    return obj


def _safe_field(value: object, field: str, *, required: bool) -> str | None:
    if value is None:
        if required:
            raise ValueError("P035_REQUIRED_PUBLIC_REVIEW_FIELD:" + field)
        return None
    if (type(value) is not str or not value or len(value) > 512
            or any(ord(c) < 32 or ord(c) == 127 for c in value)
            or FORBIDDEN_PUBLIC_TEXT.search(value)):
        raise ValueError("P035_PUBLIC_REVIEW_FIELD_UNSAFE:" + field)
    return value


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    d: dict[str, Any] = {}
    for key, value in pairs:
        if key in d:
            raise ValueError("P035_DUPLICATE_JSON_KEY")
        d[key] = value
    return d


@dataclass(frozen=True, slots=True)
class OwnerProposalRow:
    rule_id: str
    requirement_id: str
    phase: str
    source_paragraph_index: int
    review_intent: str
    formula: str | None
    units: str | None
    causal_asof_notes: str | None
    evidence_sha256: str | None
    rationale: str | None

    @property
    def is_candidate_formula(self) -> bool:
        return self.review_intent == "PROPOSE_FORMULA"


@dataclass(frozen=True, slots=True)
class OwnerReviewLine:
    rule_id: str
    requirement_id: str
    phase: str
    source_paragraph_index: int
    intake_status: str
    proposal: OwnerProposalRow | None
    independently_authenticated_source_approval: bool = False
    eligible_for_signal_implementation: bool = False


@dataclass(frozen=True, slots=True)
class SourceOwnerIntakeReport:
    version: str
    bundle_sha256: str
    source_p021_git_blob: str
    source_p034_git_blob: str
    rows: tuple[OwnerReviewLine, ...]
    proposals_count: int
    formula_proposals: int
    suggest_defer: int
    suggest_reject: int
    awaiting_proposal_rows: int
    source_owner_decisions_still_pending: int = 36
    original_forex_source_labels: int = 18
    mfx_approved_design_labels: int = 22
    source_numeric_rules_approved: int = 0
    authenticated_owner_signoffs: int = 0
    research_sim_examples_not_approved: int = 14
    confirmed_user_buy_sell_alerts: int = 0
    real_market_provider_calls: int = 0
    real_drive_quote_cache_writes: int = 0
    broker_orders: int = 0
    may_promote_numeric_policy: bool = False
    may_publish_confirmed_alerts: bool = False
    release_ready: bool = False

    @property
    def action(self) -> str:
        return "NO_SIGNAL"


def _parse_row(obj: object, valid: dict[tuple[str, str], tuple[str, str, str, int]]) -> OwnerProposalRow:
    row = _keys(obj, PROPOSED_ROW_KEYS, "proposal")
    rule_id, requirement_id, phase, paragraph = (
        row["rule_id"], row["requirement_id"],
        row["phase"], row["source_paragraph_index"],
    )
    if type(rule_id) is not str or type(requirement_id) is not str:
        raise ValueError("P035_UNKNOWN_SOURCE_REQUIREMENT")
    anchor = valid.get((rule_id, requirement_id))
    if anchor is None:
        raise ValueError("P035_UNKNOWN_SOURCE_REQUIREMENT")
    if type(phase) is not str or phase != anchor[2]:
        raise ValueError("P035_SOURCE_PHASE_MISMATCH")
    if type(paragraph) is not int or paragraph != anchor[3]:
        raise ValueError("P035_SOURCE_PARAGRAPH_ANCHOR_MISMATCH")
    intent = row["review_intent"]
    if type(intent) is not str or intent not in INTENTS:
        raise ValueError("P035_NO_SELF_APPROVED_INTENT")
    is_formula = intent == "PROPOSE_FORMULA"
    formula = _safe_field(row["formula"], "formula", required=is_formula)
    units = _safe_field(row["units"], "units", required=is_formula)
    causal = _safe_field(row["causal_asof_notes"], "causal_asof_notes", required=is_formula)
    rationale = _safe_field(row["rationale"], "rationale", required=not is_formula)
    digest = row["evidence_sha256"]
    if is_formula:
        if type(digest) is not str or not _SHA256.fullmatch(digest):
            raise ValueError("P035_UNVERIFIED_OR_MISSING_EVIDENCE_SHA256")
    elif digest is not None:
        raise ValueError("P035_SUGGESTION_CANNOT_CARRY_EVIDENCE_CLAIM")
    if not is_formula and any(x is not None for x in (formula, units, causal)):
        raise ValueError("P035_SUGGESTION_CANNOT_CARRY_FORMULA")
    return OwnerProposalRow(
        rule_id=rule_id, requirement_id=requirement_id, phase=phase,
        source_paragraph_index=paragraph, review_intent=intent,
        formula=formula, units=units, causal_asof_notes=causal,
        evidence_sha256=digest, rationale=rationale,
    )


def verify_public_owner_proposals(data: object) -> SourceOwnerIntakeReport:
    """Create 36-row review receipt without any self-attested owner approval."""
    root = _keys(data, frozenset(
        ("schema", "version", "source", "submission_mode", "proposal_rows")),
        "root",
    )
    _same(root["schema"], SCHEMA, "schema")
    _same(root["version"], VERSION, "version")
    _same(root["submission_mode"], MODE, "submission_mode")
    source = _keys(root["source"], frozenset((
        "original_forex_commit", "source_p021_git_blob",
        "decision_p034_git_blob", "original_source_doc_id",
    )), "source")
    owner = verify_owner_decision_dossier()
    _same(source["original_forex_commit"],
          "7e1c1c012b1b189be5ad7b9d07756eac012a8309", "forex_commit")
    _same(source["source_p021_git_blob"], P021_BLOB_SHA, "p021")
    _same(source["decision_p034_git_blob"], DOSSIER_BLOB_SHA, "p034")
    _same(source["original_source_doc_id"], owner.source_locked_doc_id,
          "source_locked_doc")

    proposals = root["proposal_rows"]
    if not isinstance(proposals, list) or len(proposals) > MAX_PROPOSALS:
        raise ValueError("P035_BOUNDED_PUBLIC_PROPOSALS_LIST_REQUIRED")
    if len(owner.rows) != 36 or owner.pending_owner_decisions != 36:
        raise ValueError("P035_SOURCE_OWNER_REQUIREMENTS_INCOMPLETE")
    valid = {(rid, name): (rid, name, phase, idx)
             for rid, name, phase, idx in owner.rows}
    by_key: dict[tuple[str, str], OwnerProposalRow] = {}
    for obj in proposals:
        parsed = _parse_row(obj, valid)
        key = (parsed.rule_id, parsed.requirement_id)
        if key in by_key:
            raise ValueError("P035_DUPLICATE_SOURCE_ROW_PROPOSAL")
        by_key[key] = parsed

    lines: list[OwnerReviewLine] = []
    for rule_id, name, phase, paragraph in owner.rows:
        proposed = by_key.get((rule_id, name))
        state = ("AWAITING_PROPOSAL" if proposed is None else
                 "FORMULA_FOR_EXTERNAL_OWNER_REVIEW" if proposed.is_candidate_formula else
                 "DEFER_SUGGESTED_UNVERIFIED" if proposed.review_intent == "SUGGEST_DEFER" else
                 "REJECT_SUGGESTED_UNVERIFIED")
        lines.append(OwnerReviewLine(
            rule_id=rule_id, requirement_id=name, phase=phase,
            source_paragraph_index=paragraph, intake_status=state,
            proposal=proposed,
        ))
    ordered = [
        {"rule_id": p.rule_id, "requirement_id": p.requirement_id,
         "phase": p.phase, "source_paragraph_index": p.source_paragraph_index,
         "review_intent": p.review_intent, "formula": p.formula,
         "units": p.units, "causal_asof_notes": p.causal_asof_notes,
         "evidence_sha256": p.evidence_sha256, "rationale": p.rationale}
        for p in sorted(by_key.values(), key=lambda x: (
            x.rule_id, x.requirement_id))
    ]
    canonical: dict[str, object] = {
        "version": VERSION, "source": source, "proposal_rows": ordered,
    }
    fingerprint = sha256(
        json.dumps(canonical, sort_keys=True, ensure_ascii=True,
                   separators=(",", ":")).encode("utf-8"),
    ).hexdigest()
    count_formula = sum(p.is_candidate_formula for p in by_key.values())
    count_defer = sum(p.review_intent == "SUGGEST_DEFER" for p in by_key.values())
    count_reject = sum(p.review_intent == "SUGGEST_REJECT" for p in by_key.values())
    return SourceOwnerIntakeReport(
        version=VERSION,
        bundle_sha256=fingerprint,
        source_p021_git_blob=P021_BLOB_SHA,
        source_p034_git_blob=DOSSIER_BLOB_SHA,
        rows=tuple(lines),
        proposals_count=len(by_key),
        formula_proposals=count_formula,
        suggest_defer=count_defer,
        suggest_reject=count_reject,
        awaiting_proposal_rows=36 - len(by_key),
    )


def read_public_owner_proposal_template(path: Path = TEMPLATE) -> SourceOwnerIntakeReport:
    """Read a public-safe template, reject duplicate JSON keys and oversize."""
    if not isinstance(path, Path):
        raise TypeError("P035_TYPED_TEMPLATE_PATH_REQUIRED")
    raw = path.read_bytes()
    if not raw or len(raw) > MAX_INPUT_BYTES:
        raise ValueError("P035_BOUNDED_TEMPLATE_FILE_REQUIRED")
    data: Any = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
    return verify_public_owner_proposals(data)

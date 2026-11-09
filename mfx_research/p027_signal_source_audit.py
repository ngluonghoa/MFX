"""A04/P0.27: immutable qualitative Forex source-to-BUY/SELL evidence audit.

Reads pinned SOURCE_LOCKED_03 readback quotes, the frozen original catalog
and P0.21 review registry. This is a QA/provenance tool, NOT a numeric
Forex detector, real BUY/SELL notification, price adapter or order engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1, sha256
import json
from pathlib import Path
from typing import Any

from forex_trading.catalog import ZONES
from forex_trading.model import ActionIntent, SignalStage, ZonePurpose
from mfx_research.source_parameter_review import (
    BLOCKING_COUNT, DOCUMENT_ID, REQUIREMENTS, SCHEMA as P21_SCHEMA,
    VERSION as P21_VERSION, read_review_register,
)

SCHEMA = "MFX_A04_P27_SOURCE_ANCHORED_18_ZONE_REVIEW_V1"
VERSION = "REVIEW_ONLY:P027-ORIGINAL_FOREX_1_TO_1_QUALITATIVE"
MATRIX = Path("docs/MFX_A04_P27_SOURCE_EVIDENCE_MATRIX.json")
FROZEN = Path("docs/MFX_FROZEN_SOURCE_TREE.json")
REGISTER = Path("docs/MFX_A04_P21_SOURCE_PARAMETER_REGISTER.json")
SOURCE_COMMIT = "7e1c1c012b1b189be5ad7b9d07756eac012a8309"
SOURCE_TREE = "5df2058346f6dc96ed5bb02581b139fe2aa2d803"
CATALOG_BLOB_SHA = "dc0cd0d7eab7f8603071401aa51723f7e4b8ef20"
P21_BLOB_SHA = "ef88e20271ad93c34d9d09c0cc6148f67d321929"
P27_MATRIX_BLOB_SHA = "fbacde33cba58e75e49edc6fd1e490df5f1d5f79"
SOURCE_DOC_TITLE = (
    "SOURCE_LOCKED_03_DETECTOR_AUDIT — Forex Trading 1.0"
    " — MFX Baseline 2026-11-08"
)
# Independent original 03 source Doc zero-based paragraph indexes,
# inspected through authenticated readback, not inferred from source labels.
SOURCE_ANCHORS: tuple[tuple[str, int, int], ...] = (
    ("B1", 17, 27), ("B2", 28, 38), ("B3", 39, 49),
    ("B4", 50, 60), ("B5", 61, 71), ("B6", 72, 82),
    ("B7", 83, 93), ("B8", 94, 104),
    ("S1", 105, 115), ("S2", 116, 126),
    ("S3", 127, 137), ("S4", 138, 148),
    ("S5", 149, 159), ("S6", 160, 170),
    ("S7", 171, 181), ("S8", 182, 192),
    ("FX-S9", 231, 242), ("FX-S10", 243, 254),
)
_PHASES = ("R0", "R_C", "R_E", "R_F")
PERMISSION_KEYS = frozenset((
    "source_verified_real_buy_sell", "actual_forex_price_adapter",
    "drive_real_market_quote_cache", "broker_order_execution",
    "production_release",
))


@dataclass(frozen=True, slots=True)
class EntrySourceLine:
    label: str
    family: str
    catalog_purpose: ZonePurpose
    entry_intent_if_later_source_approved: ActionIntent | None
    action_if_later_approved: str
    entry_quote_side_if_later_approved: str
    review_scope: str
    source_heading_paragraph_index: int
    source_status_paragraph_index: int
    stage_now: SignalStage = SignalStage.UNVERIFIED
    current_action: str = "NO_SIGNAL"
    source_numeric_approved: bool = False
    may_publish: bool = False
    source_verified: bool = False


@dataclass(frozen=True, slots=True)
class SourceEvidenceReceipt:
    original_source_commit: str
    original_tree_sha: str
    source_doc_id: str
    frozen_catalog_sha: str
    matrix_git_blob_sha: str
    review_register_git_blob_sha: str
    matrix_sha256: str
    entries: tuple[EntrySourceLine, ...]
    long_entry_candidate_count: int
    short_entry_candidate_count: int
    protective_or_watch_count: int
    b2_s2_source_numeric_pending: int
    unapproved_sim_examples: int
    other_entry_candidate_numeric_unmapped: int
    approved_numeric_entry_rules: int = 0
    may_send_verified_buy_sell: bool = False
    may_write_real_drive_market_cache: bool = False
    may_trade: bool = False
    may_release: bool = False
    external_provider_calls: int = 0
    actual_drive_price_writes: int = 0
    broker_orders: int = 0

    def as_record(self) -> dict[str, str | int | bool]:
        return {
            "frozen_source_commit": self.original_source_commit,
            "source_doc_id": self.source_doc_id,
            "catalog_labels": len(self.entries),
            "long_buy_entry_candidates": self.long_entry_candidate_count,
            "short_sell_entry_candidates": self.short_entry_candidate_count,
            "non_entry_watch_or_warning": self.protective_or_watch_count,
            "b2_s2_numeric_obligations_pending":
                self.b2_s2_source_numeric_pending,
            "other_entry_numeric_cases_unmapped":
                self.other_entry_candidate_numeric_unmapped,
            "unapproved_sim_examples": self.unapproved_sim_examples,
            "numeric_entry_rules_approved": self.approved_numeric_entry_rules,
            "may_send_verified_buy_sell": self.may_send_verified_buy_sell,
            "may_write_real_drive_market_cache":
                self.may_write_real_drive_market_cache,
            "may_trade": self.may_trade,
            "may_release": self.may_release,
            "external_provider_calls": self.external_provider_calls,
            "actual_drive_price_writes": self.actual_drive_price_writes,
            "broker_orders": self.broker_orders,
        }


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for k, v in pairs:
        if k in result:
            raise ValueError("P027_DUPLICATE_JSON_KEY:" + k)
        result[k] = v
    return result


def _dict(value: object, required: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("P027_SOURCE_MATRIX_EXACT_KEYS:" + name)
    return value


def _eq(value: object, expected: object, name: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise ValueError("P027_SOURCE_MATRIX_MISMATCH:" + name)


def _git_blob(content: bytes) -> str:
    return sha1(
        b"blob " + str(len(content)).encode("ascii") + b"\0" + content
    ).hexdigest()


def _validate_frozen_source() -> None:
    frozen: Any = json.loads(FROZEN.read_text(encoding="utf-8"),
                             object_pairs_hook=_reject_duplicates)
    if not isinstance(frozen, dict):
        raise ValueError("P027_FROZEN_MANIFEST_NOT_OBJECT")
    for k, v in (
        ("source_repo", "ngluonghoa/forex-trading-1-0"),
        ("source_commit", SOURCE_COMMIT),
        ("source_tree_sha", SOURCE_TREE),
        ("source_file_count", 102),
    ):
        _eq(frozen.get(k), v, "frozen." + k)
    files = frozen.get("files")
    if not isinstance(files, list) or len(files) != 102:
        raise ValueError("P027_FROZEN_102_BLOBS_REQUIRED")
    found = [x for x in files if isinstance(x, dict)
             and x.get("path") == "src/forex_trading/catalog.py"]
    if len(found) != 1:
        raise ValueError("P027_FROZEN_CATALOG_UNIQUE_BLOB_MISSING")
    _eq(found[0].get("sha"), CATALOG_BLOB_SHA, "source_catalog_blob")
    # The MFX import is identical to this original source module.
    raw = Path("src/forex_trading/catalog.py").read_bytes()
    _eq(_git_blob(raw), CATALOG_BLOB_SHA, "mfx_source_catalog_bytes")


def verify_source_evidence_matrix(data: object) -> SourceEvidenceReceipt:
    root = _dict(data, {
        "schema", "version", "source", "source_review",
        "permissions", "rows",
    }, "root")
    _eq(root["schema"], SCHEMA, "schema")
    _eq(root["version"], VERSION, "version")
    source = _dict(root["source"], {
        "repo", "commit", "tree_sha", "file_count",
        "catalog_git_blob_sha", "catalog_path",
        "source_doc_id", "source_doc_title",
        "paragraph_index_basis", "source_doc_approval_class",
    }, "source")
    for field, expected in (
        ("repo", "ngluonghoa/forex-trading-1-0"),
        ("commit", SOURCE_COMMIT), ("tree_sha", SOURCE_TREE),
        ("file_count", 102),
        ("catalog_git_blob_sha", CATALOG_BLOB_SHA),
        ("catalog_path", "src/forex_trading/catalog.py"),
        ("source_doc_id", DOCUMENT_ID),
        ("source_doc_title", SOURCE_DOC_TITLE),
        ("paragraph_index_basis", "ZERO_BASED_GOOGLE_DOCS_READBACK"),
        ("source_doc_approval_class", "QUALITATIVE_DESIGN_ONLY"),
    ):
        _eq(source[field], expected, "source." + field)
    review = _dict(root["source_review"], {
        "register_path", "register_schema", "register_version",
        "b2_s2_number_obligations_pending",
        "approved_numerical_strategy_count",
        "unapproved_sim_examples",
        "other_candidate_numeric_review_scope",
    }, "review")
    for k, expected in (
        ("register_path", str(REGISTER)),
        ("register_schema", P21_SCHEMA),
        ("register_version", P21_VERSION),
        ("b2_s2_number_obligations_pending", BLOCKING_COUNT),
        ("approved_numerical_strategy_count", 0),
        ("unapproved_sim_examples", 14),
        ("other_candidate_numeric_review_scope",
         "UNINDEXED_NOT_APPROVED"),
    ):
        _eq(review[k], expected, "review." + k)
    permissions = _dict(root["permissions"], set(PERMISSION_KEYS),
                        "permissions")
    for name, value in permissions.items():
        _eq(value, False, "permissions." + name)
    rows = root["rows"]
    if not isinstance(rows, list) or len(rows) != 18:
        raise ValueError("P027_EXACT_18_ZONE_ROWS")
    if len(ZONES) != 18 or len(SOURCE_ANCHORS) != 18:
        raise ValueError("P027_FROZEN_18_ZONE_CATALOG_DRIFT")

    result: list[EntrySourceLine] = []
    for i, (row_object, zone, anchor) in enumerate(
        zip(rows, ZONES, SOURCE_ANCHORS, strict=True)
    ):
        row = _dict(row_object, {
            "label", "family", "catalog_purpose",
            "source_heading", "phases", "source_status",
            "source_review_state", "action_if_later_approved",
            "entry_quote_side_if_later_approved",
            "possible_exit_long_warning", "source_numeric_approved",
            "action_now", "signal_stage_now",
            "actual_source_qualification", "may_publish",
        }, "row")
        label, heading_idx, status_idx = anchor
        _eq(row["label"], label, f"row{i}.source_label")
        _eq(row["label"], zone.label, f"row{i}.catalog_label")
        _eq(row["family"], zone.family, f"row{i}.family")
        _eq(row["catalog_purpose"], zone.purpose.value,
            f"row{i}.purpose")
        heading = _dict(row["source_heading"], {
            "paragraph_index", "text",
        }, "heading")
        _eq(heading["paragraph_index"], heading_idx,
            f"row{i}.heading_index")
        if (not isinstance(heading["text"], str)
                or not heading["text"].startswith(label + ".")
                or "CANDIDATE" not in heading["text"]
                and label not in ("B7", "S3", "S8")):
            raise ValueError("P027_FROZEN_SOURCE_HEADING_MISMATCH:" + label)

        phases = _dict(row["phases"], set(_PHASES), "phases")
        for j, phase in enumerate(_PHASES):
            part = _dict(phases[phase], {"paragraph_index", "text"},
                         "phase")
            _eq(part["paragraph_index"], heading_idx + j + 1,
                f"row{i}.{phase}.paragraph")
            if (not isinstance(part["text"], str)
                    or not part["text"].startswith(phase + " ")
                    or len(part["text"]) < 30):
                raise ValueError("P027_MISSING_QUALITATIVE_PHASE:" + label)

        status = _dict(row["source_status"], {
            "paragraph_index", "text",
        }, "status")
        _eq(status["paragraph_index"], status_idx,
            f"row{i}.status_index")
        s = status["text"]
        marker = ("APPROVED_DESIGN_SCOPE", "FORMULA_PENDING") if (
            label.startswith("FX-S")
        ) else ("MANIFEST_DRAFT", "PREDICATES=SPEC_PENDING")
        if (not isinstance(s, str) or not s.startswith("STATUS:")
                or not all(x in s for x in (*marker,
                                             "ACTION_ELIGIBLE=FALSE"))):
            raise ValueError("P027_NOT_EXECUTABLE_SOURCE_STATUS:" + label)

        is_buy = zone.purpose is ZonePurpose.ENTRY_LONG_CANDIDATE
        is_sell = zone.purpose is ZonePurpose.ENTRY_SHORT_CANDIDATE
        is_warning = zone.purpose is ZonePurpose.EXIT_LONG_WARNING_ONLY
        _eq(row["action_if_later_approved"],
            "BUY" if is_buy else "SELL" if is_sell else "NONE",
            f"row{i}.candidate_action")
        _eq(row["entry_quote_side_if_later_approved"],
            "ASK" if is_buy else "BID" if is_sell else "NONE",
            f"row{i}.entry_quote_side")
        _eq(row["possible_exit_long_warning"], is_warning,
            f"row{i}.exit_warning")
        _eq(row["source_review_state"],
            ("P021_18_REQUIREMENTS_PENDING"
             if label in ("B2", "S2")
             else "NUMERIC_SOURCE_CASE_NOT_INDEXED"),
            f"row{i}.review_scope")
        for field, expected in (
            ("source_numeric_approved", False),
            ("action_now", "NO_SIGNAL"),
            ("signal_stage_now", "UNVERIFIED"),
            ("actual_source_qualification", False),
            ("may_publish", False),
        ):
            _eq(row[field], expected, f"row{i}.{field}")
        intent = (ActionIntent.ENTRY_LONG if is_buy
                  else ActionIntent.ENTRY_SHORT if is_sell else None)
        result.append(EntrySourceLine(
            label=label, family=zone.family,
            catalog_purpose=zone.purpose,
            entry_intent_if_later_source_approved=intent,
            action_if_later_approved=row["action_if_later_approved"],
            entry_quote_side_if_later_approved=(
                row["entry_quote_side_if_later_approved"]
            ),
            review_scope=row["source_review_state"],
            source_heading_paragraph_index=heading_idx,
            source_status_paragraph_index=status_idx,
        ))
    receipt, _ = read_review_register(REGISTER)
    if (receipt.pending_source_numerical_approvals != 36
            or receipt.simulated_research_examples != 14
            or receipt.source_numeric_rules_approved != 0
            or receipt.may_send_confirmed_buy_sell_signal
            or receipt.original_forex_1to1_numerical_parity
            or len(REQUIREMENTS) != 18
            or any(r.rule_ids != ("B2", "S2") for r in (receipt,))):
        raise ValueError("P027_P021_NUMERIC_APPROVAL_NOT_VERIFIED")
    n_buy = sum(x.catalog_purpose is ZonePurpose.ENTRY_LONG_CANDIDATE
                for x in result)
    n_sell = sum(x.catalog_purpose is ZonePurpose.ENTRY_SHORT_CANDIDATE
                 for x in result)
    n_other = len(result) - n_buy - n_sell
    if (n_buy, n_sell, n_other) != (7, 8, 3):
        raise ValueError("P027_7_LONG_8_SHORT_3_NON_ENTRY_REQUIRED")
    n_unmapped = sum(
        x.entry_intent_if_later_source_approved is not None
        and x.review_scope == "NUMERIC_SOURCE_CASE_NOT_INDEXED"
        for x in result
    )
    if n_unmapped != 13:
        raise ValueError("P027_13_OTHER_NUMERIC_CASES_UNINDEXED")
    return SourceEvidenceReceipt(
        original_source_commit=SOURCE_COMMIT,
        original_tree_sha=SOURCE_TREE,
        source_doc_id=DOCUMENT_ID,
        frozen_catalog_sha=CATALOG_BLOB_SHA,
        matrix_git_blob_sha=P27_MATRIX_BLOB_SHA,
        review_register_git_blob_sha=P21_BLOB_SHA,
        matrix_sha256="",  # filled by read-only file path below
        entries=tuple(result),
        long_entry_candidate_count=n_buy,
        short_entry_candidate_count=n_sell,
        protective_or_watch_count=n_other,
        b2_s2_source_numeric_pending=36,
        unapproved_sim_examples=14,
        other_entry_candidate_numeric_unmapped=n_unmapped,
    )


def read_source_evidence_matrix() -> SourceEvidenceReceipt:
    _validate_frozen_source()
    reg = REGISTER.read_bytes()
    _eq(_git_blob(reg), P21_BLOB_SHA, "P021_review_register_bytes")
    raw = MATRIX.read_bytes()
    if not raw or len(raw) > 131072:
        raise ValueError("P027_MATRIX_EMPTY_OR_TOO_LARGE")
    _eq(_git_blob(raw), P27_MATRIX_BLOB_SHA,
        "P027_original_source_quotes_locked_git_blob")
    data: Any = json.loads(raw.decode("utf-8"),
                           object_pairs_hook=_reject_duplicates)
    receipt = verify_source_evidence_matrix(data)
    from dataclasses import replace
    return replace(receipt, matrix_sha256=sha256(raw).hexdigest())

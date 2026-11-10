"""A04/P0.43: 14 still-unapproved entry labels, source-anchored review slots.

The 56 phase slots are qualitative source trace points, NOT 56 proposed,
approved, executable, or independently calibrated numerical strategies.
B2/S2 keep their separate 36 pending original-source owner obligations.
Never accesses market data, Drive price cache, brokers or live signal output.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
import json
from pathlib import Path
from typing import Any

from forex_trading.catalog import ZONES, validate_catalog
from mfx_research.p027_signal_source_audit import SOURCE_ANCHORS
from mfx_research.p030_approved_nonentry_design import (
    read_22_zone_design_manifest,
)

VERSION = "MFX_A04_P43_14_ENTRY_56_SOURCE_PHASE_GAPS_V1"
P029_FILE = Path("docs/MFX_A04_P29_ELEVEN_PAIR_SYMMETRY_AUDIT.json")
P029_BLOB = "08bc1896c2007f532367750f5f1eeb6be06d1ad6"
SOURCE_COMMIT = "7e1c1c012b1b189be5ad7b9d07756eac012a8309"
SOURCE_TREE = "5df2058346f6dc96ed5bb02581b139fe2aa2d803"
PHASES = ("R0", "R_C", "R_E", "R_F")
EXPECTED_PAIRS = (
    ("E01", "B1", "S1"),
    ("E03", "B3", "S4"),
    ("E04", "B4", "S5"),
    ("E05", "B5", "S7"),
    ("E06", "B6", "FX-S9"),
    ("E07", "B8", "FX-S10"),
    ("E08", "FX-B9", "S6"),
)


def _git_blob_sha(raw: bytes) -> str:
    return sha1(b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw).hexdigest()


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError("P043_DUPLICATE_SOURCE_JSON_KEY")
        output[key] = value
    return output


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(type(k) is not str for k in value):
        raise ValueError("P043_TYPED_SOURCE_MAPPING_REQUIRED:" + label)
    return value


@dataclass(frozen=True, slots=True)
class PhaseReviewSlot:
    rule_id: str
    side: str
    phase: str
    original_source_paragraph_index: int | None
    original_qualitative_description: str
    source_scope: str
    quantitative_predicate_status: str = "PENDING_OWNER_POLICY"
    approved_numeric_formula: None = None
    approved_units: None = None
    verified_owner_evidence: None = None
    action: str = "NO_SIGNAL"


@dataclass(frozen=True, slots=True)
class EntryRuleReview:
    label: str
    mirror_label: str
    pair_id: str
    side: str
    source_scope: str
    pair_qualitative_difference: str
    unresolved_source_topic: str
    source_heading_paragraph_index: int | None
    phases: tuple[PhaseReviewSlot, ...]
    eligible_for_confirmed_signal: bool = False
    source_numeric_approval: bool = False
    action: str = "NO_SIGNAL"


@dataclass(frozen=True, slots=True)
class RemainingEntryGapReport:
    version: str
    rules: tuple[EntryRuleReview, ...]
    original_forex_source_labels: int = 18
    approved_mfx_design_labels: int = 22
    total_mfx_entry_labels: int = 16
    separately_indexed_b2_s2_labels: int = 2
    original_b2_s2_numeric_owner_decisions_pending: int = 36
    remaining_entry_labels: int = 14
    remaining_original_source_entry_labels: int = 13
    remaining_mfx_only_entry_labels: int = 1
    qualitative_phase_review_slots: int = 56
    original_source_anchored_phases: int = 52
    mfx_design_only_phases_without_original_anchor: int = 4
    owner_signed_numeric_approvals_across_all_entries: int = 0
    real_market_provider_calls: int = 0
    real_drive_market_quote_writes: int = 0
    published_confirmed_signals: int = 0
    broker_orders: int = 0
    action: str = "NO_SIGNAL"
    release_ready: bool = False


def review_14_unapproved_entries(audit: object) -> RemainingEntryGapReport:
    """Check exact original-versus-extension provenance, never endorse formulas."""
    root = _mapping(audit, "root")
    if root.get("schema") != "MFX_A04_P29_ELEVEN_PAIR_SYMMETRY_AUDIT_V1":
        raise ValueError("P043_P029_SOURCE_SCHEMA_MISMATCH")
    frozen = _mapping(root.get("frozen_source"), "frozen_source")
    if (frozen.get("repository") != "ngluonghoa/forex-trading-1-0"
            or frozen.get("commit") != SOURCE_COMMIT
            or frozen.get("tree") != SOURCE_TREE
            or frozen.get("source_locked_docs_unchanged") != 11):
        raise ValueError("P043_FROZEN_SOURCE_IDENTITY_DRIFT")

    source_anchors = {label: (start, end) for label, start, end in SOURCE_ANCHORS}
    validate_catalog(ZONES)
    if ({z.label for z in ZONES} != set(source_anchors)
            or len(ZONES) != 18):
        raise ValueError("P043_FROZEN_ORIGINAL_18_SOURCE_RANGE_DRIFT")
    design = read_22_zone_design_manifest()
    all_roles = {z.label: z.purpose for z in design.zones}
    if (len(all_roles) != 22
            or len(design.entry_long_labels) != 8
            or len(design.entry_short_labels) != 8
            or design.numerical_rules_approved != 0
            or design.b2_s2_source_obligations_pending != 36):
        raise ValueError("P043_MFX_22_ROLE_OR_NUMERIC_APPROVAL_DRIFT")

    pairs = root.get("entry_pairs")
    if not isinstance(pairs, list) or len(pairs) != 8:
        raise ValueError("P043_EXACT_EIGHT_SOURCE_ENTRY_PAIRS_REQUIRED")
    expected_all = (("E01", "B1", "S1"), ("E02", "B2", "S2"),
                    *EXPECTED_PAIRS[1:])
    observed: list[tuple[str, str, str]] = []
    for obj in pairs:
        pair = _mapping(obj, "pair")
        buy = _mapping(pair.get("buy"), "buy")
        sell = _mapping(pair.get("sell"), "sell")
        pair_id = pair.get("pair_id")
        buy_label = buy.get("label")
        sell_label = sell.get("label")
        if (not isinstance(pair_id, str) or not isinstance(buy_label, str)
                or not isinstance(sell_label, str)):
            raise ValueError("P043_TYPED_MIRROR_PAIR_LABELS_REQUIRED")
        observed.append((pair_id, buy_label, sell_label))
        if (pair.get("mirror_classification") != "QUALITATIVE_ONLY"
                or pair.get("numeric_mirror_authorized") is not False
                or buy.get("source_numeric_approved") is not False
                or sell.get("source_numeric_approved") is not False):
            raise ValueError("P043_NO_NUMERIC_MIRROR_OR_SOURCE_APPROVAL")
    if tuple(observed) != expected_all:
        raise ValueError("P043_EXACT_MIRROR_PAIR_ORDER_OR_LABEL_DRIFT")

    gaps: list[EntryRuleReview] = []
    for p in pairs:
        pair = _mapping(p, "pair")
        if pair["pair_id"] == "E02":
            continue  # B2/S2 have 36 separately indexed source-owner decisions.
        delta, topic = pair.get("reviewed_delta"), pair.get("blocking_review_topic")
        if (not isinstance(delta, str) or len(delta) < 24
                or not isinstance(topic, str) or len(topic) < 12):
            raise ValueError("P043_PAIR_SPECIFIC_SOURCE_GAP_MISSING")
        for direction, side, other in (
            ("buy", "BUY", "sell"), ("sell", "SELL", "buy")
        ):
            record = _mapping(pair[direction], direction)
            other_record = _mapping(pair[other], other)
            label, mirror = record.get("label"), other_record.get("label")
            if type(label) is not str or type(mirror) is not str:
                raise ValueError("P043_INVALID_SOURCE_LABEL")
            expected_role = (
                "ENTRY_LONG_CANDIDATE" if side == "BUY"
                else "ENTRY_SHORT_CANDIDATE"
            )
            if (all_roles.get(label) != expected_role
                    or record.get("catalog_purpose") != expected_role
                    or record.get("current_action") != "NO_SIGNAL"):
                raise ValueError("P043_ROLE_OR_ACTION_PROMOTION_DENIED")
            is_original = label != "FX-B9"
            if record.get("inherited") is not is_original:
                raise ValueError("P043_FAKE_ORIGINAL_SOURCE_OWNERSHIP")
            heading = _mapping(record.get("source_heading"), "heading")
            paragraph = heading.get("paragraph_index")
            if is_original:
                if (label not in source_anchors
                        or type(paragraph) is not int
                        or paragraph != source_anchors[label][0]):
                    raise ValueError("P043_FROZEN_SOURCE_HEADING_ANCHOR_DRIFT")
            elif paragraph is not None or label in source_anchors:
                raise ValueError("P043_MFX_EXTENSION_HAS_NO_FROZEN_SOURCE_ANCHOR")

            phases = _mapping(record.get("phases"), "phases")
            if set(phases) != set(PHASES):
                raise ValueError("P043_EXACT_FOUR_SOURCE_PHASES_REQUIRED")
            slots: list[PhaseReviewSlot] = []
            for i, phase in enumerate(PHASES, start=1):
                phase_data = _mapping(phases[phase], "phase:" + phase)
                index, description = (
                    phase_data.get("paragraph_index"), phase_data.get("text")
                )
                if type(description) is not str or len(description.strip()) < 32:
                    raise ValueError("P043_EMPTY_OR_INVALID_QUALITATIVE_SOURCE")
                if is_original:
                    assert paragraph is not None
                    if (type(index) is not int
                            or index != paragraph + i
                            or index > source_anchors[label][1]):
                        raise ValueError("P043_SOURCE_PHASE_PARAGRAPH_ANCHOR_DRIFT")
                elif index is not None:
                    raise ValueError("P043_FORGED_EXTENSION_SOURCE_ANCHOR")
                slots.append(PhaseReviewSlot(
                    rule_id=label, side=side, phase=phase,
                    original_source_paragraph_index=index,
                    original_qualitative_description=description,
                    source_scope=(
                        "ORIGINAL_FOREX_FROZEN_03"
                        if is_original else "MFX_APPROVED_DESIGN_ONLY"
                    ),
                ))
            gaps.append(EntryRuleReview(
                label=label, mirror_label=mirror,
                pair_id=pair["pair_id"], side=side,
                source_scope=("ORIGINAL_FOREX_FROZEN_03"
                              if is_original else "MFX_APPROVED_DESIGN_ONLY"),
                pair_qualitative_difference=delta,
                unresolved_source_topic=topic,
                source_heading_paragraph_index=paragraph,
                phases=tuple(slots),
            ))
    labels = {r.label for r in gaps}
    all_entries = set(design.entry_long_labels + design.entry_short_labels)
    if (len(gaps) != 14 or len(labels) != 14
            or labels != all_entries - {"B2", "S2"}
            or sum(r.source_scope == "ORIGINAL_FOREX_FROZEN_03" for r in gaps) != 13
            or sum(r.source_scope == "MFX_APPROVED_DESIGN_ONLY" for r in gaps) != 1
            or sum(len(r.phases) for r in gaps) != 56
            or sum(s.original_source_paragraph_index is not None
                   for r in gaps for s in r.phases) != 52):
        raise ValueError("P043_14_LABEL_56_PHASE_COVERAGE_DRIFT")
    return RemainingEntryGapReport(version=VERSION, rules=tuple(gaps))


def read_remaining_entry_gap_report(path: Path = P029_FILE) -> RemainingEntryGapReport:
    if not isinstance(path, Path):
        raise TypeError("P043_TYPED_SOURCE_AUDIT_PATH_REQUIRED")
    raw = path.read_bytes()
    if not raw or len(raw) > 65536:
        raise ValueError("P043_BOUNDED_AUDIT_BYTES_REQUIRED")
    if _git_blob_sha(raw) != P029_BLOB:
        raise ValueError("P043_PINNED_P029_AUDIT_BLOB_DRIFT")
    parsed: Any = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_keys)
    return review_14_unapproved_entries(parsed)

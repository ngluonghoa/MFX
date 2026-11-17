"""P0.184: owner-review 18 paired F2 proposals → 36 exact P035 rows.

No owner signoff, source rule values, licensed market data or BUY/SELL
authority is created by this transformation. Source original immutable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from mfx_research.p035_owner_proposal_intake import (
    SCHEMA as P035_SCHEMA, VERSION as P035_VERSION, MODE as P035_MODE,
    _unique_pairs, verify_public_owner_proposals,
)
from mfx_research.source_parameter_review import REQUIREMENTS, DOCUMENT_ID

SCHEMA="MFX_P184_18_PAIRED_F2_OWNER_PROPOSAL_V1"
VERSION="MFX_P184_B2S2_EXPAND_TO_P035_V1"
MODE="PAIRED_PROPOSALS_NOT_APPROVALS"
TEMPLATE=Path("docs/MFX_P184_18_PAIRED_F2_OWNER_PROPOSAL_TEMPLATE.json")
MIRROR="OWNER_REVIEW_REQUIRED_NOT_APPROVED"
INTENTS=("PROPOSE_FORMULA","SUGGEST_DEFER","SUGGEST_REJECT")
PAIR_FIELDS=frozenset((
    "requirement_id","phase","b2_source_paragraph_index",
    "s2_source_paragraph_index","review_intent","b2_formula","s2_formula",
    "units","causal_asof_notes","evidence_sha256","rationale",
    "mirror_equivalence_status",
))
ROOT_FIELDS=frozenset((
    "schema","version","source","submission_mode","paired_rows",
))
SOURCE_FIELDS=frozenset((
    "original_forex_commit","source_p021_git_blob",
    "decision_p034_git_blob","original_source_doc_id",
))


def _mapping(value: Any, keys: frozenset[str]) -> dict[str, Any]:
    if type(value) is not dict or frozenset(value)!=keys:
        raise ValueError("P184_EXACT_PUBLIC_SCHEMA_REQUIRED")
    return value


@dataclass(frozen=True, slots=True)
class PairedF2OwnerReviewReceipt:
    version: str
    paired_rows: int
    actionable_proposal_pairs: int
    awaiting_input_pairs: int
    expanded_p035_proposal_rows: int
    expanded_p035_digest: str
    p035_result: Any = field(repr=False,compare=False)
    original_numeric_rules_approved: int = 0
    original_pending_numeric_rules: int = 36
    mirrored_formula_authenticated: bool = False
    may_publish_buy_sell: bool = False
    may_trade: bool = False
    provider_calls: int = 0
    drive_writes: int = 0
    broker_orders: int = 0
    action: str = "NO_SIGNAL"

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema":self.version,
            "paired_source_obligations":self.paired_rows,
            "proposal_pairs_prepared":self.actionable_proposal_pairs,
            "pairs_waiting_for_owner_review":self.awaiting_input_pairs,
            "expanded_p035_proposal_rows":self.expanded_p035_proposal_rows,
            "original_source_numeric_approved":0,
            "original_source_decisions_pending":36,
            "independently_authenticated_owner_rules":False,
            "mirrored_formula_authenticated":False,
            "real_market_data_approved":False,
            "may_publish_buy_sell":False,
            "may_trade":False,
            "provider_calls":0,
            "drive_writes":0,
            "broker_orders":0,
            "action":"NO_SIGNAL",
        }


def compile_paired_f2_owner_proposals(data: Any) -> PairedF2OwnerReviewReceipt:
    """Strict source-anchor-preserving expansion into the established P035 gate."""
    doc=_mapping(data,ROOT_FIELDS)
    for key,expected in (
        ("schema",SCHEMA),("version",VERSION),
        ("submission_mode",MODE),
    ):
        if type(doc[key]) is not str or doc[key]!=expected:
            raise ValueError("P184_UNRECOGNIZED_DRAFT_CONTRACT:"+key)
    src=_mapping(doc["source"],SOURCE_FIELDS)
    if src.get("original_source_doc_id")!=DOCUMENT_ID:
        raise ValueError("P184_SOURCE_DOC_ID_MISMATCH")
    entries=doc["paired_rows"]
    if type(entries) is not list or len(entries)!=len(REQUIREMENTS):
        raise ValueError("P184_EXACT_18_PAIRED_REQUIREMENTS_REQUIRED")
    expanded=[]
    proposed=0
    for index,(requirement_id,phase,b2_para,s2_para) in enumerate(REQUIREMENTS):
        entry=_mapping(entries[index],PAIR_FIELDS)
        expected={"requirement_id":requirement_id,"phase":phase,
                  "b2_source_paragraph_index":b2_para,
                  "s2_source_paragraph_index":s2_para,
                  "mirror_equivalence_status":MIRROR}
        for key,value in expected.items():
            if type(entry[key]) is not type(value) or entry[key]!=value:
                raise ValueError("P184_FROZEN_PAIR_SOURCE_MISMATCH:"+key)
        intent=entry["review_intent"]
        if intent is None:
            if any(entry[k] is not None for k in (
                "b2_formula","s2_formula","units","causal_asof_notes",
                "evidence_sha256","rationale",
            )):
                raise ValueError("P184_PARTIAL_PAIR_MUST_FAIL_CLOSED")
            continue
        if type(intent) is not str or intent not in INTENTS:
            raise ValueError("P184_ONLY_NON_APPROVING_INTENTS")
        formula=(intent=="PROPOSE_FORMULA")
        if formula:
            if (any(type(entry[k]) is not str or not entry[k]
                    for k in ("b2_formula","s2_formula","units",
                              "causal_asof_notes","evidence_sha256"))
                    or entry["rationale"] is not None):
                raise ValueError("P184_BOTH_SIDES_AND_EVIDENCE_REQUIRED")
            if ("SIM:" in entry["b2_formula"].upper()
                    or "SIM:" in entry["s2_formula"].upper()):
                raise ValueError("P184_NO_SIM_VALUES_AS_SOURCE_FORMULAS")
        elif (entry["b2_formula"] is not None
                or entry["s2_formula"] is not None
                or entry["units"] is not None
                or entry["causal_asof_notes"] is not None
                or entry["evidence_sha256"] is not None
                or type(entry["rationale"]) is not str
                or not entry["rationale"]):
            raise ValueError("P184_SUGGESTION_HAS_UNVERIFIED_FORMULA")
        # No auto-generated inversion or approval: the proposer must supply
        # both directional predicates explicitly and the source owner must
        # authenticate them separately. Shared evidence digest is not a sig.
        for rule_id,paragraph in (("B2",b2_para),("S2",s2_para)):
            expanded.append({
                "rule_id":rule_id,"requirement_id":requirement_id,
                "phase":phase,"source_paragraph_index":paragraph,
                "review_intent":intent,
                "formula":entry["b2_formula" if rule_id=="B2" else "s2_formula"],
                "units":entry["units"],
                "causal_asof_notes":entry["causal_asof_notes"],
                "evidence_sha256":entry["evidence_sha256"],
                "rationale":entry["rationale"],
            })
        proposed+=1
    # Delegate all public-safe field validation, fixed Git blob source
    # authority, and 36-row unverified NO_SIGNAL rules to existing P035.
    p035=verify_public_owner_proposals({
        "schema":P035_SCHEMA,"version":P035_VERSION,
        "source":src,"submission_mode":P035_MODE,
        "proposal_rows":expanded,
    })
    if (p035.proposals_count!=2*proposed or p035.source_numeric_rules_approved!=0
            or p035.source_owner_decisions_still_pending!=36
            or p035.may_publish_confirmed_alerts
            or p035.action!="NO_SIGNAL"):
        raise ValueError("P184_P035_NO_SIGNAL_INVARIANT_BROKEN")
    return PairedF2OwnerReviewReceipt(
        version=VERSION,paired_rows=18,actionable_proposal_pairs=proposed,
        awaiting_input_pairs=18-proposed,
        expanded_p035_proposal_rows=len(expanded),
        expanded_p035_digest=p035.bundle_sha256,p035_result=p035,
    )


def read_paired_f2_owner_template(
    path: Path = TEMPLATE,
) -> PairedF2OwnerReviewReceipt:
    if not isinstance(path, Path):
        raise TypeError("P184_TYPED_LOCAL_TEMPLATE_PATH_REQUIRED")
    raw=path.read_bytes()
    if not raw or len(raw)>65536:
        raise ValueError("P184_EMPTY_OR_OVERSIZED_TEMPLATE")
    data=json.loads(raw.decode("utf-8"),object_pairs_hook=_unique_pairs)
    return compile_paired_f2_owner_proposals(data)

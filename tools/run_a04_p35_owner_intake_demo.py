"""Hosted P0.35: public-safe external owner proposal intake, never numeric approval."""
from __future__ import annotations

from copy import deepcopy
import json

from mfx_research.p035_owner_proposal_intake import (
    TEMPLATE, read_public_owner_proposal_template,
    verify_public_owner_proposals,
)
from mfx_research.p034_sim_adversarial_review import (
    verify_owner_decision_dossier,
)


def main() -> None:
    original = read_public_owner_proposal_template()
    if (len(original.rows) != 36
            or original.proposals_count != 0
            or original.source_owner_decisions_still_pending != 36
            or original.source_numeric_rules_approved != 0
            or original.action != "NO_SIGNAL"):
        raise RuntimeError("P035_EMPTY_TEMPLATE_MUST_NOT_GRANT_APPROVAL")

    owner = verify_owner_decision_dossier()
    data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    b2 = next(x for x in owner.rows
              if x[0] == "B2" and x[1] == "h1_zone_lookback")
    s2 = next(x for x in owner.rows
              if x[0] == "S2" and x[1] == "session_dst_rollover_news_gate")
    data["proposal_rows"] = [
        {
            "rule_id": b2[0],
            "requirement_id": b2[1],
            "phase": b2[2],
            "source_paragraph_index": b2[3],
            "review_intent": "PROPOSE_FORMULA",
            "formula": "POSSIBLE_RULE: only already CLOSED H1 observations",
            "units": "bars",
            "causal_asof_notes": "Known prior to UTC decision, no look-ahead",
            "evidence_sha256": "a" * 64,
            "rationale": None,
        },
        {
            "rule_id": s2[0],
            "requirement_id": s2[1],
            "phase": s2[2],
            "source_paragraph_index": s2[3],
            "review_intent": "SUGGEST_DEFER",
            "formula": None,
            "units": None,
            "causal_asof_notes": None,
            "evidence_sha256": None,
            "rationale": "Needs original source-owner DST and news decision",
        },
    ]
    parsed = verify_public_owner_proposals(data)
    reversed_order = deepcopy(data)
    reversed_order["proposal_rows"].reverse()
    same = verify_public_owner_proposals(reversed_order)
    if (
        parsed != same
        or parsed.proposals_count != 2
        or parsed.formula_proposals != 1
        or parsed.suggest_defer != 1
        or parsed.awaiting_proposal_rows != 34
        or parsed.source_owner_decisions_still_pending != 36
        or parsed.source_numeric_rules_approved != 0
        or parsed.authenticated_owner_signoffs != 0
        or parsed.action != "NO_SIGNAL"
        or parsed.may_promote_numeric_policy
        or parsed.may_publish_confirmed_alerts
        or parsed.confirmed_user_buy_sell_alerts != 0
        or parsed.real_market_provider_calls != 0
        or parsed.real_drive_quote_cache_writes != 0
        or parsed.broker_orders != 0
        or parsed.release_ready
    ):
        raise RuntimeError("P035_PROPOSED_DECISIONS_CANNOT_SELF_APPROVE")

    forged = deepcopy(data)
    forged["proposal_rows"][0]["review_intent"] = "APPROVED"
    try:
        verify_public_owner_proposals(forged)
    except ValueError as error:
        if "P035_NO_SELF_APPROVED_INTENT" not in str(error):
            raise
    else:
        raise RuntimeError("P035_FORGED_APPROVAL_NOT_REJECTED")

    print("MFX_A04_P35_SOURCE_OWNER_PROPOSAL_INTAKE_NO_SIGNAL_PASS")
    print("MFX_A04_P35_RECEIPT " + json.dumps({
        "original_36_source_decisions_still_pending":
            parsed.source_owner_decisions_still_pending,
        "public_safe_proposals": parsed.proposals_count,
        "proposed_formulas_for_external_owner_review": parsed.formula_proposals,
        "defer_suggestions_unverified": parsed.suggest_defer,
        "remaining_not_proposed": parsed.awaiting_proposal_rows,
        "authenticated_numeric_source_approvals":
            parsed.source_numeric_rules_approved,
        "signed_owner_evidence": parsed.authenticated_owner_signoffs,
        "order_independent_fingerprint": parsed.bundle_sha256,
        "real_user_buy_sell_alerts": parsed.confirmed_user_buy_sell_alerts,
        "real_market_provider_calls": parsed.real_market_provider_calls,
        "real_drive_quote_cache_writes": parsed.real_drive_quote_cache_writes,
        "broker_orders": parsed.broker_orders,
        "release_ready": parsed.release_ready,
    }, sort_keys=True))


if __name__ == "__main__":
    main()

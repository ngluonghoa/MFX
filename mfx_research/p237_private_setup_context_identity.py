"""P237 bounded private setup-source context binding; never an event or approval."""
from __future__ import annotations

from dataclasses import dataclass, field
import re

from mfx_cache.td_m5_codec import digest
from mfx_research.p227_pretrigger_h1 import PrivatePretriggerH1
from mfx_research.p228_pretrigger_native import PrivatePretriggerNative
from mfx_research.p229_pretrigger_m15 import PrivatePretriggerM15, early_observation_coverage
from mfx_research.shared_b2s2_decision import B2S2Decision, decide_b2s2
from mfx_research.p231_private_trigger_identity import (
    PrivateTriggerIdentity, summarize_private_trigger_slots,
)
from mfx_research.mfx_b2s2_confirmed_policy_v2 import (
    _p160_still_pinned, read_mfx_confirmed_b2s2_v2,
)


@dataclass(frozen=True, slots=True, repr=False)
class PrivateSetupContextIdentity:
    bounded_context_sha256: str = field(repr=False)
    action: str = "NO_SIGNAL"
    full_setup_revision_identity_verified: bool = False
    persistent_idempotence_verified: bool = False
    expiry_policy_selected: bool = False
    may_publish_buy_sell: bool = False
    may_trade: bool = False
    private_candidate_decisions: tuple[B2S2Decision, ...] = field(default=(), repr=False)


def bind_private_setup_context(
    h1: PrivatePretriggerH1, native: PrivatePretriggerNative,
    m15: PrivatePretriggerM15, trigger: PrivateTriggerIdentity,
) -> PrivateSetupContextIdentity | None:
    """Bind exact consumed draft-source digests, not later decision prices.

    Only complete structural input coverage; D1 vintage is not calendar or
    source qualified. This is a bounded in-memory fingerprint, not a
    persistent event ID, publisher-first-known or original numeric rule.
    """
    if (type(h1) is not PrivatePretriggerH1 or type(native) is not PrivatePretriggerNative
            or type(m15) is not PrivatePretriggerM15
            or type(trigger) is not PrivateTriggerIdentity
            or h1.cutoff_utc != native.cutoff_utc or h1.cutoff_utc != m15.cutoff_utc
            or any(x.action != "NO_SIGNAL" or x.numeric_policy_approved
                   or x.publisher_first_known_verified or x.may_publish_buy_sell or x.may_trade
                   for x in (h1, native, m15))
            or native.d1_calendar_qualified or m15.d1_trend_qualified or m15.early_event_approved):
        raise ValueError("P237_SETUP_CONTEXT_AUTHORITY_DRIFT")
    summarize_private_trigger_slots((trigger,))
    early = early_observation_coverage(m15, h1)
    available = (
        h1.status == "PRETRIGGER_H1_DRAFT_CONTEXT_COMPUTED",
        native.h4_status == "PRETRIGGER_H4_DRAFT_STRUCTURE_COMPUTED",
        native.d1_status == "PRETRIGGER_D1_VINTAGE_PRESENT_CALENDAR_UNQUALIFIED",
        m15.status == "PRIVATE_M15_DRAFT_GEOMETRY_COMPUTED",
    )
    identities = (h1.source_context_sha256, native.h4_context_sha256,
                  native.d1_context_sha256, m15.history_context_sha256)
    for present, sha in zip(available, identities):
        if present != (type(sha) is str and re.fullmatch(r"[a-f0-9]{64}", sha) is not None):
            raise ValueError("P237_COMPONENT_SOURCE_DIGEST_DRIFT")
        if not present and sha is not None:
            raise ValueError("P237_UNAVAILABLE_COMPONENT_DIGEST")
    if not all(available) or not m15.history_to_setup_complete:
        return None
    if not early:
        raise ValueError("P237_EARLY_CONTEXT_MISSING")
    _p160_still_pinned()
    policy = read_mfx_confirmed_b2s2_v2()
    # A private observed D1 vintage does not establish a qualified trend.
    # P230 raw boundary observations likewise cannot choose an invalidation rule.
    # Invoke exactly the same decision core as SIM, with those inputs unknown.
    if tuple(side.rule_id for side in m15.sides) != ("B2", "S2"):
        raise ValueError("P276_BOUND_GEOMETRY_PAIR_REQUIRED")
    decisions_list: list[B2S2Decision] = []
    for side in m15.sides:
        values = (side.near, side.crossed, side.anti_chase)
        decisions_list.append(decide_b2s2(
            side.rule_id, "UNKNOWN", native.h4_trend, None, lambda: values,
        ))
    decisions = tuple(decisions_list)
    if any(x.action != "NO_SIGNAL" for x in decisions):
        raise ValueError("P276_OBSERVED_UNQUALIFIED_D1_CANNOT_SIGNAL")
    return PrivateSetupContextIdentity(digest({
        "schema": "MFX_P237_BOUNDED_SETUP_SOURCE_CONTEXT_V1",
        "cutoff": h1.cutoff_utc.isoformat(),
        "component_source_sha256": list(identities),
        "policy": policy.fingerprint_sha256,
        "trigger_slots": [[s.slot_sha256, s.trigger_payload_sha256] for s in trigger.private_slots],
    }), private_candidate_decisions=decisions)

"""P231: stable private trigger-slot identity within one archive replay.

No candidate or signal inferred. No persistent ledger, expiry default,
publisher-first-known proof, or full setup revision identity is claimed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from mfx_cache.td_m5_codec import ClosedM5Bar, PROVIDER, SYMBOL, digest
from mfx_cache.v2_engine import derive_intraday
from mfx_research.mfx_b2s2_confirmed_policy_v2 import (
    _p160_still_pinned, read_mfx_confirmed_b2s2_v2,
)
from mfx_research.six_tf_readonly_context import _expected_last_closed

VERSION = "MFX_P231_PRIVATE_TRIGGER_SLOT_IDENTITY_V1"
M15 = timedelta(minutes=15)
MAX_RECEIPTS = 64


@dataclass(frozen=True, slots=True, repr=False)
class PrivateTriggerSlot:
    slot_sha256: str = field(repr=False)
    trigger_payload_sha256: str = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class PrivateTriggerIdentity:
    private_slots: tuple[PrivateTriggerSlot, ...] = field(repr=False)
    action: str = "NO_SIGNAL"
    expiry_policy_selected: bool = False
    persistent_idempotence_verified: bool = False
    full_setup_revision_identity_verified: bool = False
    may_publish_buy_sell: bool = False
    may_trade: bool = False


def identify_private_trigger_pair(
    raw: tuple[ClosedM5Bar, ...], *, latest_m15_open: datetime, decision: datetime,
) -> PrivateTriggerIdentity:
    """Use the exact closed source pair, never decision clock as identity."""
    for clock in (latest_m15_open, decision):
        if (type(clock) is not datetime or clock.tzinfo is None
                or clock.utcoffset() != timedelta(0)):
            raise ValueError("P231_EXACT_UTC_CLOCK_REQUIRED")
    if (latest_m15_open+M15 != _expected_last_closed(decision,15)
            or type(raw) is not tuple or len(raw) < 6):
        raise ValueError("P231_EXACT_LATEST_TRIGGER_REQUIRED")
    return _identify_closed_trigger_pair(raw[-6:], latest_m15_open=latest_m15_open,
                                         decision=decision)


def _identify_closed_trigger_pair(
    trigger_raw: tuple[ClosedM5Bar, ...], *, latest_m15_open: datetime,
    decision: datetime,
) -> PrivateTriggerIdentity:
    """Internal exact-pair identity; only archive-bound callers may use a delayed pair."""
    if type(trigger_raw) is not tuple or len(trigger_raw) != 6:
        raise ValueError("P234_EXACT_SIX_TRIGGER_ROWS_REQUIRED")
    pair = derive_intraday(trigger_raw, "M15", asof_utc=decision).candles
    if (len(pair) != 2 or pair[0].end_utc != pair[1].start_utc
            or datetime.fromisoformat(pair[1].start_utc) != latest_m15_open):
        raise ValueError("P231_EXACT_CONTIGUOUS_TRIGGER_PAIR_REQUIRED")
    _p160_still_pinned()
    policy = read_mfx_confirmed_b2s2_v2()
    # Logical slots stay stable across repeated observations. A different
    # trigger payload for the same slot is a conflict, not a fresh event.
    slots = []
    for rule in ("B2", "S2"):
        slot = digest({"version": VERSION, "provider": PROVIDER, "symbol": SYMBOL,
                       "side_basis": "MID", "rule": rule, "frame": "M15",
                       "origin_open": pair[0].start_utc, "trigger_end": pair[1].end_utc})
        payload = digest({"slot": slot, "trigger_source_sha256": [b.source_sha256 for b in pair],
                          "policy_fingerprint": policy.fingerprint_sha256})
        slots.append(PrivateTriggerSlot(slot,payload))
    return PrivateTriggerIdentity(tuple(slots))


def summarize_private_trigger_slots(
    receipts: tuple[PrivateTriggerIdentity, ...],
) -> dict[str, object]:
    """Audit-scope duplicate detection only, not a durable signal ledger."""
    if type(receipts) is not tuple or len(receipts) > MAX_RECEIPTS:
        raise ValueError("P231_BOUNDED_RECEIPTS_REQUIRED")
    seen: dict[str,str] = {}
    repeated = 0
    seen_pairs: set[tuple[str, str]] = set()
    for receipt in receipts:
        if (type(receipt) is not PrivateTriggerIdentity or receipt.action != "NO_SIGNAL"
                or receipt.expiry_policy_selected or receipt.persistent_idempotence_verified
                or receipt.full_setup_revision_identity_verified
                or receipt.may_publish_buy_sell or receipt.may_trade
                or type(receipt.private_slots) is not tuple or len(receipt.private_slots) != 2):
            raise ValueError("P231_TRIGGER_IDENTITY_AUTHORITY_DRIFT")
        if (any(type(s) is not PrivateTriggerSlot for s in receipt.private_slots)
                or len({s.slot_sha256 for s in receipt.private_slots}) != 2):
            raise ValueError("P231_PAIRED_SLOT_IDENTITY_DRIFT")
        pair = (receipt.private_slots[0].slot_sha256, receipt.private_slots[1].slot_sha256)
        if pair not in seen_pairs and any(key in seen for key in pair):
            raise ValueError("P231_PARTIAL_OR_REORDERED_PAIR_CONFLICT")
        seen_pairs.add(pair)
        for slot in receipt.private_slots:
            if type(slot) is not PrivateTriggerSlot or any(
                    type(x) is not str or len(x) != 64
                    or any(c not in "0123456789abcdef" for c in x)
                    for x in (slot.slot_sha256,slot.trigger_payload_sha256)):
                raise ValueError("P231_SLOT_DIGEST_REQUIRED")
            previous = seen.get(slot.slot_sha256)
            if previous is not None:
                if previous != slot.trigger_payload_sha256:
                    raise ValueError("P231_SAME_LOGICAL_SLOT_PAYLOAD_CONFLICT")
                repeated += 1
            else:
                seen[slot.slot_sha256] = slot.trigger_payload_sha256
    return {"identity_basis": "SOURCE_TRIGGER_PAIR_ONLY_IN_MEMORY_REPLAY",
            "paired_slot_observations": len(receipts),
            "distinct_paired_trigger_slots": len(seen)//2,
            "repeated_paired_slot_observations": repeated//2,
            "expiry_policy_selected": False,
            "persistent_idempotence_verified": False,
            "full_setup_revision_identity_verified": False,
            "action": "NO_SIGNAL"}

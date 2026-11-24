"""P211: isolated six-TF technical comparison, never canonical source selection."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from mfx_cache.native_fx_htf import NativeFXBatch
from mfx_cache.native_d1_epoch_20261118 import FreshEpochState
from mfx_cache.td_m5_codec import ClosedM5Bar, digest
from mfx_research.six_tf_readonly_context import (
    SixTimeframeResearchReceipt, build_six_timeframe_readonly_context,
)
from tools.audit_mfx_p209_d1_private_cache import read_private_snapshots
from mfx_research.sealed_multibar_private_features import (
    PrivateMultiBarReceipt, calculate_private_multibar_from_sealed_rows,
)
from mfx_research.sealed_private_pivot_sensitivity import (
    scan_private_sealed_pivot_sensitivity,
)
from mfx_research.sealed_private_m15_microbreak import (
    compute_private_sealed_m15_microbreak,
)
from mfx_research.p177_real_source_b2s2_readiness import (
    PrivateB2S2Readiness, compute_private_option_b2s2_requirements,
)


@dataclass(frozen=True, slots=True, repr=False)
class PrivateRevisedSixTF:
    snapshot_count: int
    revised_rows: int
    context: SixTimeframeResearchReceipt | None = field(repr=False)
    private_identity: str | None = field(repr=False)
    private_multibar: PrivateMultiBarReceipt | None = field(default=None, repr=False)
    private_b2s2: PrivateB2S2Readiness | None = field(default=None, repr=False)

    def public_summary(self) -> dict[str, Any]:
        return {
            "status": ("P211_REVISED_D1_PRIVATE_SIX_TF_COMPOSED"
                       if self.context is not None else "P211_NO_VISIBLE_SNAPSHOT"),
            "snapshot_objects_verified": self.snapshot_count,
            "private_revised_d1_rows": self.revised_rows,
            "technical_frames_present": self.context.total_frames if self.context else 0,
            "technical_six_tf_complete": (
                self.context.research_technical_context_complete if self.context else False),
            "private_b2s2_requirements_computed": self.private_b2s2 is not None,
            "private_b2s2_rule_count": len(self.private_b2s2.gates) if self.private_b2s2 else 0,
            "canonical_source_selected": False,
            "historical_asof_replay_proven": False,
            "publisher_first_known_verified": False,
            "may_publish_buy_sell": False,
            "provider_requests_added": 0,
            "drive_writes": 0,
            "broker_orders": 0,
            "action": "NO_SIGNAL",
            "stage": "UNVERIFIED",
        }


def compose_private_revised_six_tf(
    store: Any, *, original: FreshEpochState,
    expected_original_sha: str, m5: tuple[ClosedM5Bar, ...],
    h4: NativeFXBatch, canonical: SixTimeframeResearchReceipt,
    asof_utc: datetime,
) -> PrivateRevisedSixTF:
    """Use same audited intraday buffers and independently checked sidecar.

    The original technical receipt is never modified or returned as a
    revised canonical receipt. M5/H4 close checks are not proof of their
    historical publication time. This branch is private research only.
    """
    if (original.last_manifest is None
            or digest(original.last_manifest) != expected_original_sha
            or type(canonical) is not SixTimeframeResearchReceipt
            or canonical.asof_utc != asof_utc.isoformat()
            or canonical.action != "NO_SIGNAL"
            or canonical.may_publish_verified_buy_sell or canonical.may_trade
            or canonical.provider_requests or canonical.drive_market_cache_writes
            or canonical.broker_orders):
        raise ValueError("P211_CANONICAL_CONTEXT_OR_ROOT_DRIFT")
    receipt, snapshot = read_private_snapshots(
        store, original=original, now_utc=asof_utc, asof_utc=asof_utc,
    )
    if snapshot is None:
        return PrivateRevisedSixTF(receipt["snapshot_objects_verified"], 0, None, None)
    revised = NativeFXBatch(
        symbol="EUR/USD", interval="1day",
        exchange_timezone="Australia/Sydney",
        time_reference="EXCHANGE_LOCAL_SESSION_DATE",
        closed_bars=snapshot.rows, incomplete_excluded=0,
    )
    alternate = build_six_timeframe_readonly_context(
        m5[-12:], h4, revised, asof_utc=asof_utc,
    )
    if (alternate.input_m5_sha256 != canonical.input_m5_sha256
            or tuple(x for x in alternate.frames if x.frame != "D1") !=
               tuple(x for x in canonical.frames if x.frame != "D1")
            or alternate.action != "NO_SIGNAL"
            or alternate.may_publish_verified_buy_sell or alternate.may_trade
            or alternate.historical_asof_replay_proven
            or alternate.provider_requests or alternate.drive_market_cache_writes
            or alternate.broker_orders):
        raise ValueError("P211_INTRADAY_OR_AUTHORITY_DRIFT")
    multi = calculate_private_multibar_from_sealed_rows(
        m5, h4, revised, alternate, asof_utc=asof_utc,
    )
    pivots = scan_private_sealed_pivot_sensitivity(multi, alternate)
    microbreak = compute_private_sealed_m15_microbreak(multi, alternate, pivots)
    readiness = compute_private_option_b2s2_requirements(
        multi, alternate, pivots, microbreak,
        active_d1_source_epoch="P209_PRIVATE_REVISED_D1_RESEARCH_ONLY",
    )
    if (readiness.public_action != "NO_SIGNAL"
            or readiness.stage != "UNVERIFIED"
            or readiness.numeric_policy_approved
            or readiness.d1_calendar_qualified
            or readiness.publisher_first_known_verified
            or readiness.source_data_license_verified
            or readiness.bidask_net_rr_qualified
            or readiness.real_oos_qualified
            or readiness.may_publish_buy_sell or readiness.may_trade
            or readiness.market_price_requests or readiness.drive_gets_added
            or readiness.drive_writes or readiness.broker_orders
            or tuple(g.rule_id for g in readiness.gates) != ("B2", "S2")):
        raise ValueError("P212_PRIVATE_REVISED_READINESS_AUTHORITY_DRIFT")
    return PrivateRevisedSixTF(
        receipt["snapshot_objects_verified"], len(snapshot.rows), alternate,
        snapshot.identity, multi, readiness,
    )

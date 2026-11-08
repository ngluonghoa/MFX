"""M2 source discovery and entitlement evidence contracts, never a permission oracle.

Public API documentation, authenticated API access, and statements of licensing
rights are DISTINCT evidence. All evidence records here are untrusted inputs.
No helper in this module can authorize paid data access, persistence, replay,
broker trading or real historical backtests.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from re import fullmatch

from .market_data import BarSide, Timeframe
from .quotes import ensure_utc


class FeedModel(str, Enum):
    BID_ASK_TICKS = "BID_ASK_TICKS"
    BID_ASK_CANDLES = "BID_ASK_CANDLES"
    GENERIC_OHLC = "GENERIC_OHLC"
    SNAPSHOT_QUOTE = "SNAPSHOT_QUOTE"


class LicensedUse(str, Enum):
    API_ACCESS = "API_ACCESS"
    STORE_RAW = "STORE_RAW"
    DERIVE_BARS = "DERIVE_BARS"
    HISTORICAL_REPLAY = "HISTORICAL_REPLAY"
    INTERNAL_BACKTEST = "INTERNAL_BACKTEST"
    CACHE_INCREMENTAL = "CACHE_INCREMENTAL"
    REDISTRIBUTE = "REDISTRIBUTE"


class RightDecision(str, Enum):
    ALLOW_CLAIMED = "ALLOW_CLAIMED"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"


class DocumentBasis(str, Enum):
    PUBLIC_DOCUMENTATION = "PUBLIC_DOCUMENTATION"
    ACCOUNT_TERMS = "ACCOUNT_TERMS"
    WRITTEN_VENDOR_REPLY = "WRITTEN_VENDOR_REPLY"
    ACCOUNT_CONSOLE = "ACCOUNT_CONSOLE"


def _nonblank(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")


def _https_reference(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.startswith("https://") or any(
        x in value for x in (" ", "\n", "\r", "@")
    ):
        raise ValueError(f"{name} must be a noncredential HTTPS reference")


@dataclass(frozen=True, slots=True)
class PublicCapabilityClaim:
    """A public *claim* of an API feature, not an account entitlement."""
    provider_id: str
    product_id: str
    instrument_version: str
    feed_model: FeedModel
    quote_sides: frozenset[BarSide]
    timeframes: frozenset[Timeframe]
    documentation_url: str
    documentation_first_known_utc: datetime
    timestamp_semantics_documented: bool
    historical_account_price_parity_independently_verified: bool

    def __post_init__(self) -> None:
        for key in ("provider_id", "product_id", "instrument_version"):
            _nonblank(getattr(self, key), key)
        if not isinstance(self.feed_model, FeedModel):
            raise TypeError("Explicit feed model required")
        if not isinstance(self.quote_sides, frozenset) or any(
            not isinstance(x, BarSide) for x in self.quote_sides
        ):
            raise TypeError("Quote sides must be a frozenset of typed BarSide")
        if not isinstance(self.timeframes, frozenset) or any(
            not isinstance(x, Timeframe) for x in self.timeframes
        ):
            raise TypeError("Timeframes must be a frozenset of typed Timeframe")
        _https_reference(self.documentation_url, "documentation_url")
        ensure_utc(self.documentation_first_known_utc, "documentation_first_known_utc")
        if type(self.timestamp_semantics_documented) is not bool or type(
            self.historical_account_price_parity_independently_verified
        ) is not bool:
            raise TypeError("Explicit boolean documentation flags required")


@dataclass(frozen=True, slots=True)
class UseRightsClaim:
    """Evidence descriptor for one use case, NOT proof that it really grants it."""
    purpose: LicensedUse
    decision: RightDecision
    document_basis: DocumentBasis
    evidence_url: str
    evidence_sha256: str
    first_known_utc: datetime
    expires_utc: datetime | None

    def __post_init__(self) -> None:
        if not isinstance(self.purpose, LicensedUse) or not isinstance(
            self.decision, RightDecision
        ) or not isinstance(self.document_basis, DocumentBasis):
            raise TypeError("Typed scope/decision/basis required")
        _https_reference(self.evidence_url, "evidence_url")
        if not isinstance(self.evidence_sha256, str) or not fullmatch(
            r"[0-9a-f]{64}", self.evidence_sha256
        ):
            raise ValueError("Evidence digest must be lowercase SHA256")
        ensure_utc(self.first_known_utc, "rights_first_known_utc")
        if self.expires_utc is not None:
            ensure_utc(self.expires_utc, "rights_expires_utc")
            if self.expires_utc <= self.first_known_utc:
                raise ValueError("Rights expiration must follow first known")


@dataclass(frozen=True, slots=True)
class SourceQualification:
    """An internal review report, NEVER permission to use real market data."""
    public_api_candidate_fit: bool
    stated_rights_complete_for_review: bool
    review_packet_ready: bool
    vendor_entitlement_independently_verified: bool
    may_ingest_real_data: bool
    may_cache_or_store_real_data: bool
    may_run_real_backtest: bool
    reasons: tuple[str, ...]


_BACKTEST_SCOPES: frozenset[LicensedUse] = frozenset({
    LicensedUse.API_ACCESS,
    LicensedUse.STORE_RAW,
    LicensedUse.DERIVE_BARS,
    LicensedUse.HISTORICAL_REPLAY,
    LicensedUse.INTERNAL_BACKTEST,
    LicensedUse.CACHE_INCREMENTAL,
})


def assess_source_for_m2_review(
    candidate: PublicCapabilityClaim | None,
    rights: tuple[UseRightsClaim, ...],
    as_of_utc: datetime,
) -> SourceQualification:
    """Gate untrusted paperwork before real data is accessed.

    Neither caller-supplied ALLOW claims nor API key/quota checks can open an
    entitlement. An independent out-of-band approval and actual data sampling
    require a FUTURE separately designed/approved workflow.
    """
    ensure_utc(as_of_utc, "as_of_utc")
    if not isinstance(rights, tuple) or any(
        not isinstance(x, UseRightsClaim) for x in rights
    ):
        raise TypeError("Use rights records must be a typed immutable tuple")

    reasons: list[str] = []
    fit = False
    if candidate is None:
        reasons.append("NO_PUBLIC_CANDIDATE")
    elif not isinstance(candidate, PublicCapabilityClaim):
        raise TypeError("Typed PublicCapabilityClaim required")
    elif candidate.documentation_first_known_utc > as_of_utc:
        reasons.append("PUBLIC_DOCUMENTATION_FUTURE_KNOWN")
    else:
        if candidate.feed_model not in (
            FeedModel.BID_ASK_TICKS, FeedModel.BID_ASK_CANDLES
        ):
            reasons.append("PRICE_MODEL_NOT_TWO_SIDED_HISTORICAL")
        if not {BarSide.BID, BarSide.ASK}.issubset(candidate.quote_sides):
            reasons.append("BID_ASK_BOTH_REQUIRED")
        if not {Timeframe.M1, Timeframe.M5, Timeframe.M15}.issubset(
            candidate.timeframes
        ):
            reasons.append("M1_M5_M15_HISTORY_NOT_DOCUMENTED")
        if not candidate.timestamp_semantics_documented:
            reasons.append("TIMESTAMP_SEMANTICS_UNDOCUMENTED")
        if not candidate.historical_account_price_parity_independently_verified:
            reasons.append("HISTORICAL_VS_ACCOUNT_PRICE_PARITY_UNVERIFIED")
        fit = not reasons

    scopes = [x.purpose for x in rights]
    if len(set(scopes)) != len(scopes):
        reasons.append("DUPLICATE_RIGHTS_SCOPE")
    available = set(scopes)
    for purpose in sorted(_BACKTEST_SCOPES - available, key=lambda x: x.value):
        reasons.append(f"RIGHT_MISSING:{purpose.value}")

    for record in rights:
        if record.first_known_utc > as_of_utc:
            reasons.append(f"RIGHT_FUTURE_KNOWN:{record.purpose.value}")
        if record.expires_utc is not None and record.expires_utc <= as_of_utc:
            reasons.append(f"RIGHT_EXPIRED:{record.purpose.value}")
        if record.decision is RightDecision.DENY:
            reasons.append(f"RIGHT_DENIED:{record.purpose.value}")
        elif record.decision is RightDecision.UNKNOWN:
            reasons.append(f"RIGHT_UNVERIFIED:{record.purpose.value}")
        # Merely being able to fetch a public URL cannot verify contracted terms.
        elif record.document_basis is DocumentBasis.PUBLIC_DOCUMENTATION:
            reasons.append(f"ACCOUNT_ENTITLEMENT_NOT_PROVEN_BY_PUBLIC_DOC:{record.purpose.value}")

    rights_complete = bool(
        _BACKTEST_SCOPES.issubset(available)
        and len(set(scopes)) == len(scopes)
        and not any(reason.startswith(("RIGHT_", "ACCOUNT_ENTITLEMENT_")) for reason in reasons)
    )
    review_ready = fit and rights_complete
    if review_ready:
        reasons.append("CLAIMED_PERMISSIONS_NEED_INDEPENDENT_CONTRACT_VALIDATION")
        reasons.append("NO_QUALIFIED_NATIVE_BID_ASK_SAMPLE_OR_REPLAY_EVIDENCE")
    if not reasons:
        reasons.append("NO_EXTERNAL_ENTITLEMENT_ATTESTATION")
    # Deliberately no boolean argument by which a caller can self-authorize.
    return SourceQualification(
        public_api_candidate_fit=fit,
        stated_rights_complete_for_review=rights_complete,
        review_packet_ready=review_ready,
        vendor_entitlement_independently_verified=False,
        may_ingest_real_data=False,
        may_cache_or_store_real_data=False,
        may_run_real_backtest=False,
        reasons=tuple(sorted(set(reasons))),
    )

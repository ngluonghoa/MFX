"""Byte-pinned TZif clock evidence. Claims are NOT trusted vendor attestations.

An SHA-256 over supplied TZif bytes prevents unnoticed substitution relative to
a separately approved expected digest. Self-computed test digests prove only
internal equality; source authenticity, tzdb release and licensing stay OPEN.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from re import fullmatch
from zoneinfo import ZoneInfo

from .quotes import ensure_utc
from .source_calendar import SourceCalendarPolicy


@dataclass(frozen=True, slots=True)
class TzifArtifact:
    provider_id: str
    source_revision: str
    iana_timezone_claim: str
    tzdb_revision_claim: str
    first_known_utc: datetime
    expected_sha256: str
    raw_tzif: bytes

    def __post_init__(self) -> None:
        for field in ("provider_id", "source_revision",
                      "iana_timezone_claim", "tzdb_revision_claim"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} is required")
        ensure_utc(self.first_known_utc, "tzif_first_known_utc")
        if not isinstance(self.expected_sha256, str) or not fullmatch(
            r"[0-9a-f]{64}", self.expected_sha256
        ):
            raise ValueError("EXPECTED_TZIF_SHA256_INVALID")
        if not isinstance(self.raw_tzif, bytes) or not (44 <= len(self.raw_tzif) <= 2_000_000):
            raise ValueError("TZIF_BYTES_INVALID")
        if not self.raw_tzif.startswith(b"TZif"):
            raise ValueError("TZIF_MAGIC_INVALID")
        if sha256(self.raw_tzif).hexdigest() != self.expected_sha256:
            raise ValueError("TZIF_DIGEST_MISMATCH")
        self.zone()  # validate TZif parser; never fall back to host local timezone

    def zone(self) -> ZoneInfo:
        """Each use decodes the supplied bytes, rather than host TZPATH contents."""
        try:
            return ZoneInfo.from_file(BytesIO(self.raw_tzif), key=self.iana_timezone_claim)
        except Exception as exc:
            raise ValueError("TZIF_PARSE_INVALID") from exc


@dataclass(frozen=True, slots=True)
class TzifPolicyCheck:
    internally_consistent: bool
    source_independently_attested: bool
    permission_to_trade: bool
    reason: str


def assess_tzif_policy(
    artifact: TzifArtifact | None,
    policy: SourceCalendarPolicy | None,
    decision_utc: datetime,
) -> TzifPolicyCheck:
    """Validate bytes/identity/as-of. No independent right or vendor verification."""
    ensure_utc(decision_utc, "decision_utc")

    def blocked(reason: str) -> TzifPolicyCheck:
        return TzifPolicyCheck(False, False, False, reason)

    if artifact is None or policy is None:
        return blocked("PINNED_TZIF_OR_POLICY_MISSING")
    if not isinstance(artifact, TzifArtifact) or not isinstance(policy, SourceCalendarPolicy):
        raise TypeError("typed TZif artifact and calendar policy required")
    if artifact.first_known_utc > decision_utc or policy.first_known_utc > decision_utc:
        return blocked("TZIF_POLICY_NOT_KNOWN_AS_OF")
    if artifact.provider_id != policy.provider_id:
        return blocked("TZIF_PROVIDER_MISMATCH")
    if artifact.iana_timezone_claim != policy.iana_timezone:
        return blocked("TZIF_ZONE_CLAIM_MISMATCH")
    if artifact.tzdb_revision_claim != policy.tzdb_revision_claim:
        return blocked("TZIF_REVISION_CLAIM_MISMATCH")
    # A matching digest is NOT a trusted authority's digital signature.
    return TzifPolicyCheck(True, False, False, "BYTE_PIN_MATCH_ONLY_NOT_SOURCE_ATTESTED")


def resolve_wall_with_pinned_tzif(
    wall: datetime,
    artifact: TzifArtifact,
    decision_utc: datetime,
    *,
    fold: int | None = None,
) -> datetime:
    """Resolve a naive local wall-clock through fixed TZif bytes (no host tzdb).

    Ambiguous fall-back time needs explicit fold; non-existent spring-gap fails.
    Artifact must already have been known at decision time.
    """
    ensure_utc(decision_utc, "decision_utc")
    if not isinstance(artifact, TzifArtifact):
        raise TypeError("TZif artifact required")
    if artifact.first_known_utc > decision_utc:
        raise ValueError("FUTURE_TZIF_ARTIFACT")
    if not isinstance(wall, datetime) or wall.tzinfo is not None:
        raise ValueError("LOCAL_WALL_MUST_BE_NAIVE")
    if fold is not None and (type(fold) is not int or fold not in (0, 1)):
        raise ValueError("FOLD_MUST_BE_0_OR_1")
    zone = artifact.zone()
    valid: dict[int, datetime] = {}
    for candidate in (0, 1):
        instant = wall.replace(tzinfo=zone, fold=candidate).astimezone(timezone.utc)
        if instant.astimezone(zone).replace(tzinfo=None) == wall:
            valid[candidate] = instant
    if not valid:
        raise ValueError("NONEXISTENT_DST_WALL_TIME")
    if len(set(valid.values())) > 1:
        if fold is None:
            raise ValueError("AMBIGUOUS_DST_WALL_TIME_REQUIRES_FOLD")
        return valid[fold]
    if fold == 1:
        raise ValueError("FOLD_1_NOT_APPLICABLE")
    return valid[0]

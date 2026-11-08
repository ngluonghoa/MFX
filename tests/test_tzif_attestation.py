import struct
import unittest
from dataclasses import replace
from datetime import datetime, time, timedelta, timezone
from hashlib import sha256

from forex_trading.source_calendar import SourceCalendarPolicy
from forex_trading.tzif_attestation import (
    TzifArtifact, assess_tzif_policy, resolve_wall_with_pinned_tzif,
)

UTC = timezone.utc
KNOWN = datetime(2026, 2, 1, tzinfo=UTC)
FALL = datetime(2026, 11, 1, 6, tzinfo=UTC)


def fixture_tzif() -> bytes:
    """Tiny synthetic TZif v1 with 2026 US spring/fall transitions only.

    This is NOT a real or licensed IANA tzdb distribution, and intentionally
    does not assert rules for 2025/2027 or a vendor's calendar.
    """
    spring = int(datetime(2026, 3, 8, 7, tzinfo=UTC).timestamp())
    fall = int(FALL.timestamp())
    header = b"TZif" + b"\x00" * 16 + struct.pack(">6l", 0, 0, 0, 2, 2, 8)
    transitions = struct.pack(">2l", spring, fall)
    types = struct.pack(">lbb", -18000, 0, 0) + struct.pack(">lbb", -14400, 1, 4)
    return header + transitions + bytes([1, 0]) + types + b"EST\x00EDT\x00"


# Freeze the independently calculated fixture digest for regression; tests
# must not silently self-approve a modified fixture by recomputing expected.
EXPECTED = "787dbeac1a6eca77706fd0c52763596ca5805d5e12c7030fe2573904796012d6"


def artifact(**changes):
    values = dict(
        provider_id="synthetic-provider", source_revision="tzif-synthetic-1",
        iana_timezone_claim="America/New_York",
        tzdb_revision_claim="SYNTHETIC-TZIF-2026-NOT-IANA-RELEASE",
        first_known_utc=KNOWN, expected_sha256=EXPECTED,
        raw_tzif=fixture_tzif(),
    )
    values.update(changes)
    return TzifArtifact(**values)


def policy(**changes):
    values = dict(
        provider_id="synthetic-provider", calendar_version="synthetic-ny-session",
        timezone_policy_id="synthetic-tz", iana_timezone="America/New_York",
        tzdb_revision_claim="SYNTHETIC-TZIF-2026-NOT-IANA-RELEASE",
        daily_rollover_local=time(17), first_known_utc=KNOWN,
    )
    values.update(changes)
    return SourceCalendarPolicy(**values)


class TzifAttestationTests(unittest.TestCase):
    def test_pinned_fixture_digest_is_stable(self):
        self.assertEqual(sha256(fixture_tzif()).hexdigest(), EXPECTED)

    def test_bytes_and_clock_are_self_contained(self):
        pinned = artifact()
        self.assertEqual(pinned.zone().key, "America/New_York")
        self.assertEqual(resolve_wall_with_pinned_tzif(
            datetime(2026, 11, 2, 1, 30), pinned, FALL + timedelta(days=2)),
            datetime(2026, 11, 2, 6, 30, tzinfo=UTC))

    def test_dst_overlap_fails_without_fold(self):
        wall = datetime(2026, 11, 1, 1, 30)
        with self.assertRaisesRegex(ValueError, "AMBIGUOUS"):
            resolve_wall_with_pinned_tzif(wall, artifact(), FALL + timedelta(days=1))

    def test_dst_overlap_fold_yields_distinct_instants(self):
        wall = datetime(2026, 11, 1, 1, 30)
        a = resolve_wall_with_pinned_tzif(wall, artifact(), FALL + timedelta(days=1), fold=0)
        b = resolve_wall_with_pinned_tzif(wall, artifact(), FALL + timedelta(days=1), fold=1)
        self.assertEqual(b-a, timedelta(hours=1))

    def test_dst_gap_always_rejected(self):
        wall = datetime(2026, 3, 8, 2, 30)
        for fold in (None, 0, 1):
            with self.subTest(fold=fold), self.assertRaisesRegex(ValueError, "NONEXISTENT"):
                resolve_wall_with_pinned_tzif(wall, artifact(), FALL, fold=fold)

    def test_future_artifact_fails_closed(self):
        a = artifact(first_known_utc=FALL + timedelta(days=2))
        with self.assertRaisesRegex(ValueError, "FUTURE_TZIF"):
            resolve_wall_with_pinned_tzif(datetime(2026, 11, 1, 1, 30), a, FALL)

    def test_tzif_tampering_rejected(self):
        payload = bytearray(fixture_tzif())
        payload[-1] ^= 1
        with self.assertRaisesRegex(ValueError, "DIGEST_MISMATCH"):
            artifact(raw_tzif=bytes(payload))

    def test_tzif_magic_rejected(self):
        with self.assertRaisesRegex(ValueError, "MAGIC"):
            artifact(raw_tzif=b"bad!" + fixture_tzif()[4:])

    def test_bad_tzif_parse_rejected(self):
        malformed = b"TZif" + b"\x00" * 42
        with self.assertRaisesRegex(ValueError, "TZIF_PARSE"):
            artifact(raw_tzif=malformed, expected_sha256=sha256(malformed).hexdigest())

    def test_missing_artifact_fails_closed(self):
        self.assertFalse(assess_tzif_policy(None, policy(), FALL).internally_consistent)

    def test_policy_match_is_not_trusted_attestation(self):
        gate = assess_tzif_policy(artifact(), policy(), FALL)
        self.assertTrue(gate.internally_consistent)
        self.assertFalse(gate.source_independently_attested)
        self.assertFalse(gate.permission_to_trade)

    def test_provider_mismatch_rejected(self):
        self.assertEqual(assess_tzif_policy(
            artifact(provider_id="other"), policy(), FALL).reason, "TZIF_PROVIDER_MISMATCH")

    def test_zone_claim_mismatch_rejected(self):
        self.assertEqual(assess_tzif_policy(
            artifact(iana_timezone_claim="UTC"), policy(), FALL).reason,
            "TZIF_ZONE_CLAIM_MISMATCH")

    def test_tzdb_version_claim_mismatch_rejected(self):
        self.assertEqual(assess_tzif_policy(
            artifact(tzdb_revision_claim="different"), policy(), FALL).reason,
            "TZIF_REVISION_CLAIM_MISMATCH")

    def test_policy_future_first_known_rejected(self):
        self.assertEqual(assess_tzif_policy(
            artifact(), policy(first_known_utc=FALL + timedelta(seconds=1)), FALL).reason,
            "TZIF_POLICY_NOT_KNOWN_AS_OF")

    def test_bad_fold_rejected(self):
        for fold in (-1, 2, True):
            with self.subTest(fold=fold), self.assertRaisesRegex(ValueError, "FOLD_MUST"):
                resolve_wall_with_pinned_tzif(datetime(2026, 11, 2, 1), artifact(), FALL+timedelta(days=2), fold=fold)

    def test_naive_wall_required(self):
        with self.assertRaisesRegex(ValueError, "MUST_BE_NAIVE"):
            resolve_wall_with_pinned_tzif(datetime(2026, 11, 2, tzinfo=UTC),
                                          artifact(), FALL+timedelta(days=2))

    def test_no_permissions_from_exact_byte_match(self):
        self.assertFalse(assess_tzif_policy(artifact(), policy(), FALL).permission_to_trade)

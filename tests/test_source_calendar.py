import unittest
from dataclasses import replace
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from forex_trading.market_data import (BarCoverage, BarLifecycle, BarSide,
    MarketBar, MarketBarKey, Observation, SourceQuality, Timeframe, evaluate_closed_bar)
from forex_trading.source_calendar import (CalendarDisposition, SessionEvidence,
    SourceCalendarPolicy, assess_bar_source_calendar, resolve_local_wall_time,
    validate_session_ledger)

UTC = timezone.utc
S = datetime(2026, 10, 31, 21, 0, tzinfo=UTC)  # NY Oct31 17:00 EDT
E = datetime(2026, 11, 1, 22, 0, tzinfo=UTC)   # NY Nov01 17:00 EST; 25h across DST
KNOWN = datetime(2026, 10, 30, tzinfo=UTC)
ASOF = datetime(2026, 11, 2, tzinfo=UTC)


def policy(**kwargs):
    params = dict(provider_id="test-vendor", calendar_version="test-daily-2026a",
                  timezone_policy_id="test-ny-wall", iana_timezone="America/New_York",
                  tzdb_revision_claim="test-reference-2026a-NOT_ATTESTED",
                  daily_rollover_local=time(17, 0), first_known_utc=KNOWN)
    params.update(kwargs)
    return SourceCalendarPolicy(**params)


def session(**kwargs):
    params = dict(session_id="test-synthetic-ny-dst", provider_id="test-vendor",
                  calendar_version="test-daily-2026a", source_revision="schedule-r1",
                  opens_utc=S, closes_utc=E, first_known_utc=KNOWN)
    params.update(kwargs)
    return SessionEvidence(**params)


def bar(tf=Timeframe.D1, **kwargs):
    key = MarketBarKey("EURUSD-test", tf, S, E, "test-daily-2026a", "test-aggregate-v1", BarSide.BID)
    obs = Observation("test-vendor", "test-stream", "fixture", "rev-1", "a"*64,
                      E, E+timedelta(minutes=1), "test-ny-wall", "TEST-ONLY")
    params = dict(key=key, observation=obs, revision_number=1,
                  first_known_utc=E+timedelta(minutes=1),
                  open=Decimal("1.10"), high=Decimal("1.20"), low=Decimal("1.00"),
                  close=Decimal("1.15"), lifecycle=BarLifecycle.CLOSED,
                  coverage=BarCoverage.COMPLETE, quality=SourceQuality.VERIFIED)
    params.update(kwargs)
    return MarketBar(**params)


class SourceCalendarTests(unittest.TestCase):
    def test_dst_fall_overlap_requires_explicit_fold(self):
        wall = datetime(2026, 11, 1, 1, 30)
        with self.assertRaisesRegex(ValueError, "AMBIGUOUS"):
            resolve_local_wall_time(wall, "America/New_York")
        a = resolve_local_wall_time(wall, "America/New_York", fold=0)
        b = resolve_local_wall_time(wall, "America/New_York", fold=1)
        self.assertEqual(b-a, timedelta(hours=1))

    def test_dst_spring_gap_rejected_even_with_fold(self):
        wall = datetime(2026, 3, 8, 2, 30)
        for selected in (None, 0, 1):
            with self.subTest(fold=selected), self.assertRaisesRegex(ValueError, "NONEXISTENT"):
                resolve_local_wall_time(wall, "America/New_York", fold=selected)

    def test_valid_unambiguous_wall_clock(self):
        a = resolve_local_wall_time(datetime(2026, 11, 2, 1, 30), "America/New_York")
        self.assertEqual(a, datetime(2026, 11, 2, 6, 30, tzinfo=UTC))

    def test_unsupported_fold_rejected(self):
        for f in (-1, 2, True, "1"):
            with self.subTest(f=f), self.assertRaisesRegex(ValueError, "FOLD_MUST"):
                resolve_local_wall_time(datetime(2026, 11, 2, 1, 30),
                                        "America/New_York", fold=f)

    def test_fold_one_nonambiguous_fails(self):
        with self.assertRaisesRegex(ValueError, "NOT_APPLICABLE"):
            resolve_local_wall_time(datetime(2026, 11, 2, 1), "America/New_York", fold=1)

    def test_naive_input_only(self):
        with self.assertRaisesRegex(ValueError, "MUST_BE_NAIVE"):
            resolve_local_wall_time(datetime(2026, 11, 2, tzinfo=UTC), "America/New_York")

    def test_invalid_timezone_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "IANA_TIMEZONE"):
            policy(iana_timezone="Synthetic/Unknown_Zone")
        with self.assertRaisesRegex(ValueError, "IANA_TIMEZONE"):
            resolve_local_wall_time(datetime(2026, 11, 2), "Not/A_Zone")

    def test_dst_25h_daily_bar_consistent_with_ny_rollover(self):
        self.assertEqual(E-S, timedelta(hours=25))
        got = assess_bar_source_calendar(bar(), ASOF, policy(), session())
        self.assertEqual(got.disposition, CalendarDisposition.VERIFIED_CONTRACT_INPUT)
        self.assertTrue(got.use_for_calendar_aware_features)
        self.assertFalse(got.permission_to_trade)

    def test_calendar_version_mismatch_blocks(self):
        other = policy(calendar_version="revised-v2")
        got = assess_bar_source_calendar(bar(), ASOF, other, session())
        self.assertEqual(got.reason, "CALENDAR_VERSION_MISMATCH")

    def test_provider_mismatch_blocks(self):
        got = assess_bar_source_calendar(bar(), ASOF, policy(provider_id="unknown"), session())
        self.assertEqual(got.reason, "PROVIDER_CALENDAR_MISMATCH")

    def test_source_timezone_claim_mismatch_blocks(self):
        got = assess_bar_source_calendar(bar(), ASOF,
                                         policy(timezone_policy_id="other-policy"), session())
        self.assertEqual(got.reason, "SOURCE_TIMEZONE_POLICY_MISMATCH")

    def test_future_calendar_policy_cannot_leak_back(self):
        got = assess_bar_source_calendar(bar(), ASOF,
                                         policy(first_known_utc=ASOF+timedelta(seconds=1)),
                                         session())
        self.assertEqual(got.reason, "CALENDAR_OR_BAR_NOT_KNOWN_AS_OF")

    def test_future_session_revision_cannot_leak_back(self):
        got = assess_bar_source_calendar(bar(), ASOF, policy(),
                                         session(first_known_utc=ASOF+timedelta(seconds=1)))
        self.assertEqual(got.reason, "CALENDAR_OR_BAR_NOT_KNOWN_AS_OF")

    def test_source_bar_first_known_future_blocks(self):
        got = assess_bar_source_calendar(bar(), E, policy(), session())
        self.assertEqual(got.reason, "CALENDAR_OR_BAR_NOT_KNOWN_AS_OF")

    def test_no_session_is_not_closed_market_proof(self):
        got = assess_bar_source_calendar(bar(), ASOF, policy(), None)
        self.assertEqual(got.reason, "MISSING_CALENDAR_OR_SESSION_EVIDENCE")
        self.assertFalse(got.permission_to_trade)

    def test_outside_session_blocked(self):
        got = assess_bar_source_calendar(bar(), ASOF, policy(),
                                         session(opens_utc=S+timedelta(hours=1)))
        self.assertEqual(got.reason, "BAR_OUTSIDE_EXPLICIT_SESSION")

    def test_bad_daily_rollover_local_blocked(self):
        got = assess_bar_source_calendar(bar(), ASOF, policy(daily_rollover_local=time(0)), session())
        self.assertEqual(got.reason, "DAILY_ROLLOVER_BOUNDARY_MISMATCH")

    def test_weekly_needs_explicit_source_policy(self):
        got = assess_bar_source_calendar(bar(tf=Timeframe.W1), ASOF, policy(), session())
        self.assertEqual(got.reason, "WEEKLY_BOUNDARY_POLICY_NOT_SPECIFIED")

    def test_provider_schedule_not_independent_source_attestation(self):
        got = assess_bar_source_calendar(bar(), ASOF, policy(), session())
        self.assertIn("NOT_ATTESTED", got.reason)
        self.assertFalse(got.permission_to_trade)

    def test_session_duplicate_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            validate_session_ledger((session(), session()))

    def test_same_calendar_overlapping_session_rejected(self):
        with self.assertRaisesRegex(ValueError, "OVERLAPPING"):
            validate_session_ledger((session(), session(session_id="second",
                 opens_utc=E-timedelta(hours=1), closes_utc=E+timedelta(hours=1))))

    def test_adjacent_sessions_are_allowed(self):
        validate_session_ledger((session(), session(session_id="next",
            opens_utc=E, closes_utc=E+timedelta(hours=24))))

    def test_different_calendars_do_not_conflict(self):
        validate_session_ledger((session(), session(session_id="other",
            calendar_version="another-calendar")))

    def test_nonpositive_session_duration_rejected(self):
        with self.assertRaisesRegex(ValueError, "positive duration"):
            session(opens_utc=E)

    def test_missing_calendar_revision_rejected(self):
        with self.assertRaises(ValueError):
            policy(calendar_version="")

    def test_naive_session_timestamp_rejected(self):
        with self.assertRaises(ValueError):
            session(opens_utc=datetime(2026, 11, 1))

    def test_bad_rollover_tzaware_time_rejected(self):
        with self.assertRaises(ValueError):
            policy(daily_rollover_local=time(17, tzinfo=UTC))

    def test_read_only_calendar_pass_must_not_override_bad_bar_quality(self):
        bad = bar(coverage=BarCoverage.INVALID)
        self.assertTrue(assess_bar_source_calendar(bad, ASOF, policy(), session()).use_for_calendar_aware_features)
        quality = evaluate_closed_bar(bad, ASOF)
        self.assertFalse(quality.usable_for_technical_features)
        self.assertFalse(quality.permission_to_trade)

    def test_empty_timezone_policy_claim_rejected(self):
        with self.assertRaises(ValueError):
            policy(timezone_policy_id="")

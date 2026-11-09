"""A04/P0.17 real catalog-aware typed classification; no numeric signal claims."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from forex_trading.catalog import ZONES
from forex_trading.model import Direction, SignalStage, ZonePurpose
from mfx_research.zone_catalog_gate import (
    DisplayBucket, UnverifiedZoneClaim, route_unverified_zone_claims,
)

T = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)


def c(label: str, origin: str = "EV1", pair: str = "EUR_USD") -> UnverifiedZoneClaim:
    return UnverifiedZoneClaim(pair, label, origin, T)


class FrozenZoneCatalogRoutingTests(unittest.TestCase):
    def test_all_eighteen_frozen_labels_exactly_classified(self) -> None:
        got = route_unverified_zone_claims(tuple(c(z.label) for z in ZONES), T)
        self.assertEqual(len(got.classified), 18)
        self.assertEqual(len(got.candidate_groups), 2)
        self.assertEqual(got.actual_confirmed_signals, 0)

    def test_all_seven_long_candidates(self) -> None:
        labels = ("B1", "B2", "B3", "B4", "B5", "B6", "B8")
        got = route_unverified_zone_claims(tuple(c(x) for x in labels), T)
        self.assertEqual(tuple(x.label for x in got.classified), labels)
        self.assertTrue(all(
            x.bucket is DisplayBucket.BUY_CANDIDATE_UNVERIFIED
            and x.direction is Direction.LONG
            and x.purpose is ZonePurpose.ENTRY_LONG_CANDIDATE
            for x in got.classified
        ))

    def test_all_eight_short_candidates(self) -> None:
        labels = ("S1", "S2", "S4", "S5", "S6", "S7", "FX-S9", "FX-S10")
        got = route_unverified_zone_claims(tuple(c(x) for x in labels), T)
        self.assertEqual(tuple(x.label for x in got.classified), labels)
        self.assertTrue(all(
            x.bucket is DisplayBucket.SELL_CANDIDATE_UNVERIFIED
            and x.direction is Direction.SHORT
            and x.purpose is ZonePurpose.ENTRY_SHORT_CANDIDATE
            for x in got.classified
        ))

    def test_b7_is_watch_only_never_buy(self) -> None:
        got = route_unverified_zone_claims((c("B7"),), T)
        self.assertIs(got.classified[0].bucket, DisplayBucket.WATCH_ONLY)
        self.assertIsNone(got.classified[0].direction)
        self.assertEqual(got.candidate_groups, ())

    def test_s3_s8_are_long_exit_warnings_not_short(self) -> None:
        got = route_unverified_zone_claims((c("S3"), c("S8")), T)
        self.assertTrue(all(
            x.bucket is DisplayBucket.EXIT_LONG_WARNING_ONLY
            and x.direction is None for x in got.classified
        ))
        self.assertEqual(got.candidate_groups, ())

    def test_fx_b9_unapproved_never_promoted(self) -> None:
        with self.assertRaisesRegex(ValueError, "UNKNOWN_OR_UNAPPROVED"):
            route_unverified_zone_claims((c("FX-B9"),), T)

    def test_unrelated_zone_denied(self) -> None:
        with self.assertRaisesRegex(ValueError, "UNKNOWN_OR_UNAPPROVED"):
            route_unverified_zone_claims((c("B19"),), T)

    def test_earlier_known_claims_can_be_classified(self) -> None:
        got = route_unverified_zone_claims(
            (replace(c("B2"), first_known_utc=T - timedelta(hours=1)),), T
        )
        self.assertEqual(got.classified[0].label, "B2")

    def test_future_claims_cannot_be_backdated(self) -> None:
        with self.assertRaisesRegex(ValueError, "FUTURE_LABEL"):
            route_unverified_zone_claims(
                (replace(c("B2"), first_known_utc=T + timedelta(seconds=1)),), T
            )

    def test_same_origin_b5_b6_b8_yield_one_evidence_group(self) -> None:
        got = route_unverified_zone_claims(tuple(c(x) for x in ("B5", "B6", "B8")), T)
        self.assertEqual(len(got.candidate_groups), 1)
        self.assertEqual(got.candidate_groups[0].matched_rule_ids,
                         ("B5", "B6", "B8"))
        self.assertIsNone(got.candidate_groups[0].primary_rule_id)

    def test_same_origin_s7_s9_s10_yield_one_evidence_group(self) -> None:
        got = route_unverified_zone_claims(
            tuple(c(x) for x in ("S7", "FX-S9", "FX-S10")), T
        )
        self.assertEqual(len(got.candidate_groups), 1)
        self.assertEqual(got.candidate_groups[0].matched_rule_ids,
                         ("S7", "FX-S9", "FX-S10"))

    def test_distinct_origins_remain_distinct_unverified_groups(self) -> None:
        got = route_unverified_zone_claims((c("B5", "EV1"), c("B6", "EV2")), T)
        self.assertEqual(len(got.candidate_groups), 2)

    def test_opposing_directions_not_merged_into_a_single_signal(self) -> None:
        got = route_unverified_zone_claims((c("B2"), c("S2")), T)
        self.assertEqual(len(got.candidate_groups), 2)
        self.assertEqual({x.direction for x in got.candidate_groups},
                         {Direction.LONG, Direction.SHORT})
        self.assertFalse(got.may_send_buy_sell_alert)

    def test_duplicate_origin_rule_is_denied(self) -> None:
        with self.assertRaisesRegex(ValueError, "DUPLICATE_RULE"):
            route_unverified_zone_claims((c("B2"), c("B2")), T)

    def test_different_pairs_are_not_deduplicated(self) -> None:
        got = route_unverified_zone_claims(
            (c("B2", pair="EUR_USD"), c("B2", pair="GBP_USD")), T
        )
        self.assertEqual(len(got.candidate_groups), 2)

    def test_no_numeric_evidence_no_confirmed_signals_or_trades(self) -> None:
        got = route_unverified_zone_claims(tuple(c(z.label) for z in ZONES), T)
        for x in got.classified:
            with self.subTest(label=x.label):
                self.assertIs(x.stage, SignalStage.UNVERIFIED)
                self.assertFalse(x.numerical_predicate_implemented)
                self.assertFalse(x.provider_rights_verified)
                self.assertFalse(x.signal_confirmed)
                self.assertFalse(x.can_trade)
        self.assertFalse(got.may_send_buy_sell_alert)
        self.assertFalse(got.may_trade)
        self.assertEqual(got.provider_requests, 0)
        self.assertEqual(got.drive_market_cache_writes, 0)

    def test_malformed_identity_denied(self) -> None:
        with self.assertRaisesRegex(ValueError, "INVALID_CLAIM"):
            c("B2", origin="../")
        with self.assertRaisesRegex(ValueError, "INVALID_CLAIM"):
            c("", origin="EV1")

    def test_naive_decision_and_known_clock_denied(self) -> None:
        with self.assertRaises(ValueError):
            route_unverified_zone_claims((c("B2"),),
                                         T.replace(tzinfo=None))
        with self.assertRaises(ValueError):
            replace(c("B2"), first_known_utc=T.replace(tzinfo=None))

    def test_mutable_input_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "UNBOUNDED_OR_MUTABLE"):
            route_unverified_zone_claims([c("B2")], T)  # type: ignore[arg-type]

    def test_untyped_claim_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "TYPED_ZONE"):
            route_unverified_zone_claims(("B2",), T)  # type: ignore[arg-type]

    def test_empty_claims_yield_zero_signals(self) -> None:
        r = route_unverified_zone_claims((), T)
        self.assertEqual((r.classified, r.candidate_groups), ((), ()))
        self.assertEqual(r.actual_confirmed_signals, 0)

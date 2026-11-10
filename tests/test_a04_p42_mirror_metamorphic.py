"""A04/P0.42: 11 mirror-pair SIM metadata metamorphic safety regression.

Tests role symmetry and NO_SIGNAL presentation only. Does NOT assert price-pattern
inversion, equivalence of B/S numerical predicates, market quotes or broker fills.
Frozen original Forex strategy/source and all 36 B2/S2 owner rules stay untouched.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha1
import json
from pathlib import Path
import unittest

from forex_trading.catalog import ZONES, validate_catalog
from mfx_research.p030_approved_nonentry_design import (
    read_22_zone_design_manifest,
)
from mfx_research.p031_sim_22_zone_router import (
    SimZoneLabelClaim, route_sim_22_zone_labels,
)

SOURCE_AUDIT = Path("docs/MFX_A04_P29_ELEVEN_PAIR_SYMMETRY_AUDIT.json")
SOURCE_AUDIT_BLOB = "08bc1896c2007f532367750f5f1eeb6be06d1ad6"
ENTRY_PAIRS = (
    ("E01", "B1", "S1"),
    ("E02", "B2", "S2"),
    ("E03", "B3", "S4"),
    ("E04", "B4", "S5"),
    ("E05", "B5", "S7"),
    ("E06", "B6", "FX-S9"),
    ("E07", "B8", "FX-S10"),
    ("E08", "FX-B9", "S6"),
)
NONENTRY_PAIRS = (
    ("B7", "FX-S11", "WATCH_ONLY", "WATCH_ONLY"),
    ("S3", "FX-B10", "EXIT_LONG_WARNING_ONLY", "EXIT_SHORT_WARNING_ONLY"),
    ("S8", "FX-B11", "EXIT_LONG_WARNING_ONLY", "EXIT_SHORT_WARNING_ONLY"),
)
START = datetime(2026, 11, 10, 6, 0, tzinfo=timezone.utc)
DECISION = START + timedelta(seconds=5)


def _sha(raw: bytes) -> str:
    return sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw
    ).hexdigest()


def _audit() -> dict[str, object]:
    raw = SOURCE_AUDIT.read_bytes()
    if _sha(raw) != SOURCE_AUDIT_BLOB:
        raise ValueError("P042_PINNED_P029_AUDIT_DRIFT")
    result = json.loads(raw.decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError("P042_INVALID_AUDIT")
    return result


def _c(
    label: str,
    origin: str = "SIM:ONE_EVENT",
    provider: str = "SIM:OFFLINE_ONLY",
    stream: str = "SIM:M15_CLOSED",
    retrieved: datetime = START + timedelta(seconds=2),
) -> SimZoneLabelClaim:
    return SimZoneLabelClaim(
        instrument_version="SIM:EURUSD",
        calendar_version="SIM:CAUSAL_UTC",
        origin_event_id=origin,
        provider_id=provider,
        stream_id=stream,
        label=label,
        closed_candle_end_utc=START,
        first_known_utc=START + timedelta(seconds=1),
        retrieved_at_utc=retrieved,
    )


class P042ElevenPairMetamorphicSafety(unittest.TestCase):
    def test_01_original_catalog_remains_18_and_not_inflated(self) -> None:
        validate_catalog(ZONES)
        self.assertEqual(len(ZONES), 18)
        self.assertNotIn("FX-B9", {x.label for x in ZONES})
        self.assertNotIn("FX-S11", {x.label for x in ZONES})

    def test_02_source_audit_git_blob_seal_and_schema(self) -> None:
        audit = _audit()
        self.assertEqual(
            audit["schema"], "MFX_A04_P29_ELEVEN_PAIR_SYMMETRY_AUDIT_V1"
        )
        self.assertEqual(audit["frozen_source"]["source_locked_docs_unchanged"], 11)
        self.assertEqual(
            audit["frozen_source"]["commit"],
            "7e1c1c012b1b189be5ad7b9d07756eac012a8309",
        )

    def test_03_all_eight_entry_pairs_match_original_audit(self) -> None:
        raw = _audit()["entry_pairs"]
        self.assertEqual(
            tuple((p["pair_id"], p["buy"]["label"], p["sell"]["label"])
                  for p in raw),
            ENTRY_PAIRS,
        )
        self.assertEqual(len(raw), 8)

    def test_04_entry_mirrors_are_qualitative_not_numeric(self) -> None:
        for p in _audit()["entry_pairs"]:
            with self.subTest(pair=p["pair_id"]):
                self.assertEqual(p["mirror_classification"], "QUALITATIVE_ONLY")
                self.assertIs(p["numeric_mirror_authorized"], False)
                self.assertIs(p["buy"]["source_numeric_approved"], False)
                self.assertIs(p["sell"]["source_numeric_approved"], False)
                self.assertEqual(p["buy"]["current_action"], "NO_SIGNAL")
                self.assertEqual(p["sell"]["current_action"], "NO_SIGNAL")
                self.assertEqual(
                    set(p["buy"]["phases"]), {"R0", "R_C", "R_E", "R_F"}
                )
                self.assertEqual(
                    set(p["sell"]["phases"]), {"R0", "R_C", "R_E", "R_F"}
                )

    def test_05_three_nonentry_pairs_are_exact_p029_origins(self) -> None:
        raw = _audit()["nonentry_missing_mirrors"]
        self.assertEqual(
            tuple((p["existing"], p["proposed"]) for p in raw),
            tuple((p[0], p[1]) for p in NONENTRY_PAIRS),
        )
        self.assertEqual(len(raw), 3)
        self.assertTrue(all(p["numeric_predicates_approved"] is False for p in raw))
        self.assertTrue(all(p["action_eligible"] is False for p in raw))

    def test_06_exact_22_labels_one_to_one_across_all_11_pairs(self) -> None:
        all_labels = tuple(x for _, buy, sell in ENTRY_PAIRS for x in (buy, sell))
        all_labels += tuple(
            x for a, b, _, _ in NONENTRY_PAIRS for x in (a, b)
        )
        m = read_22_zone_design_manifest()
        self.assertEqual(len(all_labels), 22)
        self.assertEqual(len(set(all_labels)), 22)
        self.assertEqual(set(all_labels), {x.label for x in m.zones})
        self.assertEqual(
            (len(m.entry_long_labels), len(m.entry_short_labels),
             len(m.watch_labels), len(m.exit_long_warning_labels),
             len(m.exit_short_warning_labels)),
            (8, 8, 2, 2, 2),
        )

    def test_07_roles_exact_for_eight_source_entry_pairs(self) -> None:
        roles = {z.label: z.purpose for z in read_22_zone_design_manifest().zones}
        for pid, buy, sell in ENTRY_PAIRS:
            with self.subTest(pair=pid):
                self.assertEqual(roles[buy], "ENTRY_LONG_CANDIDATE")
                self.assertEqual(roles[sell], "ENTRY_SHORT_CANDIDATE")

    def test_08_watch_exit_roles_never_become_entry(self) -> None:
        zones = {z.label: z for z in read_22_zone_design_manifest().zones}
        for a, b, a_role, b_role in NONENTRY_PAIRS:
            with self.subTest(pair=(a, b)):
                self.assertEqual(zones[a].purpose, a_role)
                self.assertEqual(zones[b].purpose, b_role)
                self.assertFalse(zones[a].can_open_new_position)
                self.assertFalse(zones[b].can_open_new_position)
                self.assertEqual(zones[b].mirror_of, a)

    def test_09_all_eight_buy_only_and_sell_only_presentations(self) -> None:
        for pid, buy, sell in ENTRY_PAIRS:
            with self.subTest(pair=pid):
                left = route_sim_22_zone_labels((_c(buy),), DECISION)
                right = route_sim_22_zone_labels((_c(sell),), DECISION)
                self.assertEqual(
                    left.events[0].display_outcome,
                    "UNVERIFIED_BUY_RESEARCH_GROUP_ONLY",
                )
                self.assertEqual(
                    right.events[0].display_outcome,
                    "UNVERIFIED_SELL_RESEARCH_GROUP_ONLY",
                )
                self.assertEqual(
                    left.events[0].research_opportunity_id,
                    right.events[0].research_opportunity_id,
                )
                self.assertEqual(left.events[0].action, "NO_SIGNAL")
                self.assertEqual(right.events[0].action, "NO_SIGNAL")

    def test_10_entry_mirror_collisions_are_eight_conflicts_not_trades(self) -> None:
        for pid, buy, sell in ENTRY_PAIRS:
            with self.subTest(pair=pid):
                r = route_sim_22_zone_labels((_c(buy), _c(sell)), DECISION)
                self.assertEqual(len(r.events), 1)
                self.assertEqual(r.events[0].entry_long_labels, (buy,))
                self.assertEqual(r.events[0].entry_short_labels, (sell,))
                self.assertEqual(r.events[0].display_outcome, "CONFLICT_NO_SIGNAL")
                self.assertTrue(r.events[0].conflict)
                self.assertFalse(r.events[0].may_publish_alert)
                self.assertEqual(r.confirmed_buy_sell_signals, 0)

    def test_11_order_permutation_keeps_identical_receipt(self) -> None:
        for pid, buy, sell in ENTRY_PAIRS:
            with self.subTest(pair=pid):
                r1 = route_sim_22_zone_labels((_c(buy), _c(sell)), DECISION)
                r2 = route_sim_22_zone_labels((_c(sell), _c(buy)), DECISION)
                self.assertEqual(r1, r2)

    def test_12_different_origins_do_not_create_false_conflict(self) -> None:
        for pid, buy, sell in ENTRY_PAIRS:
            with self.subTest(pair=pid):
                r = route_sim_22_zone_labels(
                    (_c(buy, origin="SIM:BUY_" + pid),
                     _c(sell, origin="SIM:SELL_" + pid)), DECISION,
                )
                self.assertEqual(len(r.events), 2)
                self.assertTrue(all(not e.conflict for e in r.events))
                self.assertEqual(
                    {e.display_outcome for e in r.events},
                    {"UNVERIFIED_BUY_RESEARCH_GROUP_ONLY",
                     "UNVERIFIED_SELL_RESEARCH_GROUP_ONLY"},
                )

    def test_13_all_three_nonentry_pairs_cannot_create_entry_or_exit(self) -> None:
        for a, b, a_role, b_role in NONENTRY_PAIRS:
            with self.subTest(pair=(a, b)):
                r = route_sim_22_zone_labels((_c(a), _c(b)), DECISION)
                self.assertEqual(len(r.events), 1)
                e = r.events[0]
                self.assertEqual(e.entry_long_labels, ())
                self.assertEqual(e.entry_short_labels, ())
                self.assertEqual(e.display_outcome,
                                 "WATCH_OR_PROTECTION_RESEARCH_ONLY")
                self.assertEqual(
                    {row.role for row in r.classified}, {a_role, b_role}
                )
                self.assertTrue(all(not x.position_verified for x in r.classified))
                self.assertTrue(all(not x.may_auto_exit for x in r.classified))
                self.assertFalse(r.may_trade)
                self.assertFalse(r.may_send_live_alerts)

    def test_14_all_22_independent_sim_labels_do_not_publish(self) -> None:
        ordered = [x for _, a, b in ENTRY_PAIRS for x in (a, b)]
        ordered += [x for a, b, _, _ in NONENTRY_PAIRS for x in (a, b)]
        r = route_sim_22_zone_labels(
            tuple(_c(label, origin="SIM:PAIR_" + str(i // 2))
                  for i, label in enumerate(ordered)), DECISION,
        )
        self.assertEqual(len(r.classified), 22)
        self.assertEqual(len(r.events), 11)
        self.assertEqual(
            sum(e.display_outcome == "CONFLICT_NO_SIGNAL" for e in r.events), 8
        )
        self.assertEqual(
            sum(e.display_outcome == "WATCH_OR_PROTECTION_RESEARCH_ONLY"
                for e in r.events), 3
        )
        self.assertTrue(all(row.action == "NO_SIGNAL" and
                            row.stage == "UNVERIFIED" and
                            not row.may_publish for row in r.classified))
        self.assertTrue(all(e.action == "NO_SIGNAL" and
                            not e.may_publish_alert for e in r.events))

    def test_15_provenance_future_and_duplicate_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "P031_DUPLICATE_RULE"):
            route_sim_22_zone_labels((_c("B1"), _c("B1")), DECISION)
        with self.assertRaisesRegex(ValueError, "P031_MIXED_PROVIDER"):
            route_sim_22_zone_labels(
                (_c("B1"), _c("S1", provider="SIM:DIFFERENT")), DECISION,
            )
        with self.assertRaisesRegex(ValueError, "P031_MIXED_PROVIDER"):
            route_sim_22_zone_labels(
                (_c("B1"), _c("S1", stream="SIM:DIFFERENT")), DECISION,
            )
        with self.assertRaisesRegex(ValueError, "P031_FUTURE_KNOWN"):
            route_sim_22_zone_labels(
                (_c("B1", retrieved=DECISION + timedelta(seconds=1)),),
                DECISION,
            )
        with self.assertRaisesRegex(ValueError, "P031_UNAPPROVED_OR_FORGED"):
            route_sim_22_zone_labels((_c("FX-S12"),), DECISION)

    def test_16_zero_numeric_owner_rights_live_cache_and_broker(self) -> None:
        m = read_22_zone_design_manifest()
        self.assertEqual(m.b2_s2_source_obligations_pending, 36)
        self.assertEqual(m.numerical_rules_approved, 0)
        r = route_sim_22_zone_labels(
            tuple(_c(x) for x in ("B2", "S2", "B7", "FX-S11",
                                   "S3", "FX-B10", "S8", "FX-B11")),
            DECISION,
        )
        self.assertEqual(r.numeric_entry_predicates_approved, 0)
        self.assertEqual(r.original_b2_s2_source_numeric_obligations_pending, 36)
        self.assertEqual(r.confirmed_buy_sell_signals, 0)
        self.assertEqual(r.confirmed_exit_warnings, 0)
        self.assertEqual(r.live_provider_calls, 0)
        self.assertEqual(r.real_drive_quote_cache_writes, 0)
        self.assertEqual(r.broker_orders, 0)
        self.assertFalse(r.may_send_live_alerts)
        self.assertFalse(r.may_auto_exit)
        self.assertFalse(r.may_trade)
        self.assertFalse(r.release_ready)


if __name__ == "__main__":
    unittest.main()

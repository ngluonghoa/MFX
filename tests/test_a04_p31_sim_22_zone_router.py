"""P0.31: 24 pre-registered functional research router tests (synthetic only)."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from forex_trading.catalog import ZONES, validate_catalog
from mfx_research.p030_approved_nonentry_design import (
    read_22_zone_design_manifest,
)
from mfx_research.p031_sim_22_zone_router import (
    MAX_CLAIMS, VERSION, SimZoneLabelClaim, route_sim_22_zone_labels,
)
from mfx_research.zone_catalog_gate import (
    UnverifiedZoneClaim, route_unverified_zone_claims,
)

T = datetime(2026, 11, 10, 4, tzinfo=timezone.utc)
DECISION = T + timedelta(minutes=5)


def c(label: str, **kw: object) -> SimZoneLabelClaim:
    props = dict(
        instrument_version="SIM:EURUSD",
        calendar_version="SIM:UTC_NY",
        origin_event_id="SIM:EVENT_A",
        provider_id="SIM:OFFLINE",
        stream_id="SIM:M15_CLOSED",
        label=label,
        closed_candle_end_utc=T - timedelta(minutes=15),
        first_known_utc=T,
        retrieved_at_utc=T + timedelta(seconds=1),
    )
    props.update(kw)
    return SimZoneLabelClaim(**props)  # type: ignore[arg-type]


class P031SimZoneResearchRouterTests(unittest.TestCase):
    def test_01_original_18_catalog_is_unchanged(self) -> None:
        validate_catalog(ZONES)
        self.assertEqual(len(ZONES), 18)
        self.assertFalse(any(z.label == "FX-B9" for z in ZONES))

    def test_02_approved_p030_22_source_is_sha_sealed(self) -> None:
        receipt = read_22_zone_design_manifest()
        self.assertEqual(len(receipt.zones), 22)
        self.assertEqual(receipt.numerical_rules_approved, 0)
        self.assertEqual(receipt.b2_s2_source_obligations_pending, 36)

    def test_03_exact_8_8_2_4_roles(self) -> None:
        m = read_22_zone_design_manifest()
        r = route_sim_22_zone_labels((), DECISION)
        self.assertEqual(len(m.entry_long_labels), r.mfx_entry_long_design_candidates)
        self.assertEqual(len(m.entry_short_labels), r.mfx_entry_short_design_candidates)
        self.assertEqual(len(m.watch_labels), r.mfx_watch_only_labels)
        self.assertEqual(
            len(m.exit_long_warning_labels) + len(m.exit_short_warning_labels),
            r.mfx_exit_warning_labels,
        )

    def test_04_all_22_labels_classify_one_research_opportunity(self) -> None:
        m = read_22_zone_design_manifest()
        claims = tuple(c(z.label) for z in m.zones)
        r = route_sim_22_zone_labels(claims, DECISION)
        self.assertEqual(len(r.classified), 22)
        self.assertEqual(len(r.events), 1)
        g = r.events[0]
        self.assertEqual((len(g.entry_long_labels), len(g.entry_short_labels),
                          len(g.watch_only_labels),
                          len(g.exit_long_labels), len(g.exit_short_labels)),
                         (8, 8, 2, 2, 2))

    def test_05_every_row_and_group_actions_no_signal(self) -> None:
        m = read_22_zone_design_manifest()
        r = route_sim_22_zone_labels(tuple(c(z.label) for z in m.zones),
                                     DECISION)
        self.assertTrue(all(x.action == "NO_SIGNAL" and
                            x.stage == "UNVERIFIED" and
                            not x.may_publish and
                            not x.may_open_new_position and
                            not x.may_auto_exit for x in r.classified))
        self.assertTrue(all(x.action == "NO_SIGNAL" and
                            not x.may_publish_alert for x in r.events))

    def test_06_frozen_original_p017_router_stays_valid(self) -> None:
        claims = tuple(
            UnverifiedZoneClaim("EUR_USD", z.label, "ORIGINAL", T)
            for z in ZONES
        )
        old = route_unverified_zone_claims(claims, DECISION)
        self.assertEqual(len(old.classified), 18)
        self.assertEqual(old.actual_confirmed_signals, 0)

    def test_07_fx_s11_is_not_a_sell_entry(self) -> None:
        r = route_sim_22_zone_labels((c("FX-S11"),), DECISION)
        self.assertEqual(r.classified[0].role, "WATCH_ONLY")
        self.assertEqual(r.events[0].entry_short_labels, ())
        self.assertEqual(r.events[0].watch_only_labels, ("FX-S11",))

    def test_08_fx_b10_is_not_a_buy_entry(self) -> None:
        r = route_sim_22_zone_labels((c("FX-B10"),), DECISION)
        self.assertEqual(r.classified[0].role, "EXIT_SHORT_WARNING_ONLY")
        self.assertEqual(r.events[0].entry_long_labels, ())
        self.assertEqual(r.events[0].exit_short_labels, ("FX-B10",))
        self.assertFalse(r.classified[0].position_verified)

    def test_09_fx_b11_is_not_a_buy_entry(self) -> None:
        r = route_sim_22_zone_labels((c("FX-B11"),), DECISION)
        self.assertEqual(r.classified[0].role, "EXIT_SHORT_WARNING_ONLY")
        self.assertEqual(r.events[0].entry_long_labels, ())
        self.assertEqual(r.events[0].exit_short_labels, ("FX-B11",))

    def test_10_s3_s8_exit_long_only(self) -> None:
        r = route_sim_22_zone_labels((c("S8"), c("S3")), DECISION)
        self.assertEqual(r.events[0].exit_long_labels, ("S3", "S8"))
        self.assertFalse(r.events[0].entry_short_labels)

    def test_11_b7_fx_s11_watch_only(self) -> None:
        r = route_sim_22_zone_labels((c("FX-S11"), c("B7")), DECISION)
        self.assertEqual(r.events[0].watch_only_labels, ("B7", "FX-S11"))
        self.assertEqual(r.events[0].display_outcome,
                         "WATCH_OR_PROTECTION_RESEARCH_ONLY")

    def test_12_b5_b6_b8_one_buy_group_no_priority(self) -> None:
        r = route_sim_22_zone_labels((c("B8"), c("B6"), c("B5")), DECISION)
        self.assertEqual(len(r.events), 1)
        self.assertEqual(r.events[0].entry_long_labels, ("B5", "B6", "B8"))
        self.assertEqual(r.events[0].display_outcome,
                         "UNVERIFIED_BUY_RESEARCH_GROUP_ONLY")
        self.assertEqual(r.events[0].actual_numeric_signal_count, 0)

    def test_13_s7_fx_s9_fx_s10_one_sell_group(self) -> None:
        r = route_sim_22_zone_labels((c("FX-S10"), c("S7"), c("FX-S9")),
                                     DECISION)
        self.assertEqual(len(r.events), 1)
        self.assertEqual(r.events[0].entry_short_labels,
                         ("FX-S10", "FX-S9", "S7"))
        self.assertEqual(r.events[0].display_outcome,
                         "UNVERIFIED_SELL_RESEARCH_GROUP_ONLY")

    def test_14_mixed_long_short_one_conflict_group(self) -> None:
        r = route_sim_22_zone_labels((c("B2"), c("S2")), DECISION)
        self.assertEqual(len(r.events), 1)
        self.assertTrue(r.events[0].conflict)
        self.assertEqual(r.events[0].display_outcome, "CONFLICT_NO_SIGNAL")
        self.assertEqual(r.events[0].action, "NO_SIGNAL")

    def test_15_mixed_roles_one_event_not_entry_or_exit_promotion(self) -> None:
        r = route_sim_22_zone_labels(
            (c("B2"), c("B7"), c("S3"), c("FX-B10")), DECISION,
        )
        self.assertEqual(len(r.events), 1)
        g = r.events[0]
        self.assertEqual(g.entry_long_labels, ("B2",))
        self.assertEqual(g.entry_short_labels, ())
        self.assertEqual(g.watch_only_labels, ("B7",))
        self.assertEqual(g.exit_long_labels, ("S3",))
        self.assertEqual(g.exit_short_labels, ("FX-B10",))
        self.assertFalse(r.may_auto_exit)
        self.assertFalse(r.may_send_live_alerts)

    def test_16_duplicate_label_per_event_denied(self) -> None:
        with self.assertRaisesRegex(ValueError, "P031_DUPLICATE_RULE"):
            route_sim_22_zone_labels((c("B2"), c("B2")), DECISION)

    def test_17_unknown_typo_or_forged_zone_denied(self) -> None:
        for name in ("B9", "FX-S12", "FX-B12", "B999", "S11"):
            with self.subTest(name=name), self.assertRaisesRegex(
                ValueError, "P031_UNAPPROVED_OR_FORGED_ZONE"
            ):
                route_sim_22_zone_labels((c(name),), DECISION)

    def test_18_future_or_reversed_first_known_retrieved_denied(self) -> None:
        with self.assertRaisesRegex(ValueError, "P031_CLOSED_FIRST_KNOWN"):
            c("B2", first_known_utc=T - timedelta(minutes=16))
        with self.assertRaisesRegex(ValueError, "P031_CLOSED_FIRST_KNOWN"):
            c("B2", retrieved_at_utc=T - timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError, "P031_FUTURE_KNOWN"):
            route_sim_22_zone_labels(
                (c("B2", retrieved_at_utc=DECISION+timedelta(seconds=1)),),
                DECISION,
            )

    def test_19_naive_and_nonutc_datetimes_denied(self) -> None:
        with self.assertRaisesRegex(ValueError, "P031_EXACT_UTC"):
            c("B2", first_known_utc=datetime(2026, 11, 10, 4))
        with self.assertRaisesRegex(ValueError, "P031_EXACT_UTC"):
            c("B2", retrieved_at_utc=T.astimezone(
                timezone(timedelta(hours=7))))
        with self.assertRaisesRegex(ValueError, "P031_EXACT_UTC"):
            route_sim_22_zone_labels(
                (c("B2"),), datetime(2026, 11, 10, 4),
            )

    def test_20_reject_real_non_sim_identifiers_and_mixed_stream(self) -> None:
        for field in ("instrument_version", "calendar_version",
                      "origin_event_id", "provider_id", "stream_id"):
            with self.subTest(field=field), self.assertRaisesRegex(
                    ValueError, "P031_SIM_PROVENANCE_REQUIRED"):
                c("B2", **{field: "REAL:EURUSD"})
        with self.assertRaisesRegex(ValueError, "P031_MIXED_PROVIDER"):
            route_sim_22_zone_labels(
                (c("B2"), c("S2", provider_id="SIM:OTHER")), DECISION,
            )
        with self.assertRaisesRegex(ValueError, "P031_MIXED_PROVIDER"):
            route_sim_22_zone_labels(
                (c("B2"), c("S2", stream_id="SIM:SECOND")), DECISION,
            )

    def test_21_typed_bounded_immutable_input_denied_on_bad(self) -> None:
        with self.assertRaisesRegex(ValueError, "P031_BOUNDED_IMMUTABLE"):
            route_sim_22_zone_labels([c("B2")], DECISION)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "P031_BOUNDED_IMMUTABLE"):
            route_sim_22_zone_labels(
                tuple(c("B2", origin_event_id="SIM:" + str(i))
                      for i in range(MAX_CLAIMS+1)),
                DECISION,
            )
        with self.assertRaisesRegex(TypeError, "P031_TYPED_SIM_ZONE"):
            route_sim_22_zone_labels((object(),), DECISION)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "P031_INVALID_ZONE_LABEL"):
            c("FX-B10\n")

    def test_22_event_hash_order_and_zone_independent(self) -> None:
        a = route_sim_22_zone_labels((c("B2"), c("B7")), DECISION)
        b = route_sim_22_zone_labels((c("B7"), c("B2")), DECISION)
        one = route_sim_22_zone_labels((c("B2"),), DECISION)
        self.assertEqual(a.events, b.events)
        self.assertEqual(a.events[0].research_opportunity_id,
                         one.events[0].research_opportunity_id)
        self.assertNotEqual(a.events[0].research_opportunity_id,
                            route_sim_22_zone_labels(
                                (c("B2", calendar_version="SIM:UTC_OTHER"),),
                                DECISION).events[0].research_opportunity_id)

    def test_23_all_rights_and_numeric_approvals_closed(self) -> None:
        r = route_sim_22_zone_labels((c("B2"), c("FX-B10")), DECISION)
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

    def test_24_old_source_and_version_remain_separate(self) -> None:
        self.assertEqual(VERSION, "MFX_A04_P31_22_ZONE_SIM_RESEARCH_PRESENTATION_V1")
        self.assertEqual(read_22_zone_design_manifest().original_labels,
                         tuple(x.label for x in ZONES))
        self.assertEqual(
            route_sim_22_zone_labels((), DECISION).events, (),
        )
        self.assertEqual(
            route_sim_22_zone_labels(
                (c("B2", origin_event_id="SIM:EVENT_A"),
                 c("S2", origin_event_id="SIM:EVENT_B")),
                DECISION,
            ).events[1].display_outcome,
            "UNVERIFIED_SELL_RESEARCH_GROUP_ONLY",
        )


if __name__ == "__main__":
    unittest.main()

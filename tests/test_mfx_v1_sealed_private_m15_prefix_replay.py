"""P0.159: purely private time-sliced closed M15 replay on sealed data.

All tests use hermetic synthetic raw archive stores. No source-owner numeric
approval, licensed vendor source, true historical OOS or public BUY/SELL.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta
from decimal import Decimal
import json
from unittest import TestCase

from mfx_research.sealed_private_m15_prefix_replay import (
    VERSION, PrivateM15PrefixReplay, replay_private_m15_closed_prefixes,
)
from mfx_research.sealed_private_m15_microbreak import (
    compute_private_sealed_m15_microbreak,
)
from test_mfx_v1_sealed_private_m15_microbreak import manufactured
from test_mfx_v1_six_tf_sealed_archive_consumer import ASOF, consume
from test_mfx_v1_manual_signal_only_drive_output import mocked
from tools.run_mfx_v1_manual_drive_six_tf import safe_summary


def research(*, direction="FLAT", prev_already_crossed=False):
    multi, technical, pivots = manufactured(
        direction=direction, prev_already_crossed=prev_already_crossed,
    )
    latest = compute_private_sealed_m15_microbreak(
        multi, technical, pivots,
    )
    return replay_private_m15_closed_prefixes(
        multi, technical, pivots, latest,
    )


class MfxP159PrivateM15PrefixReplayTests(TestCase):
    def test_01_archived_consumer_attaches_private_asof_replay(self):
        receipt = consume()
        replay = receipt.private_m15_prefix_replay
        self.assertIsInstance(replay, PrivateM15PrefixReplay)
        self.assertEqual(replay.version, VERSION)
        self.assertEqual(replay.asof_utc, receipt.technical.asof_utc)
        self.assertEqual(replay.source_private_multibar_digest_sha256,
                         receipt.private_multibar.private_input_digest_sha256)

    def test_02_8_m15_candles_yield_exact_prefix_count(self):
        replay = research()
        self.assertEqual(replay.replayed_closed_m15_inputs, 8)
        self.assertEqual(replay.studied_windows, ((1,1), (2,2)))
        self.assertEqual(len(replay.private_observations), 6)
        self.assertEqual(
            [(x.profile_left_bars, x.prefix_closed_count)
             for x in replay.private_observations],
            [(1,5),(1,6),(1,7),(1,8),(2,7),(2,8)],
        )

    def test_03_asof_prefixes_sorted_and_all_closed_before_decision(self):
        replay = research()
        for left,right in replay.studied_windows:
            points=[x for x in replay.private_observations
                    if (x.profile_left_bars,x.profile_right_bars)==(left,right)]
            self.assertEqual([x.prefix_closed_count for x in points],
                             sorted(x.prefix_closed_count for x in points))
            for row in points:
                self.assertLessEqual(
                    datetime.fromisoformat(row.latest_m15_close_utc), ASOF,
                )

    def test_04_flat_cached_candles_have_no_break(self):
        replay=research()
        self.assertTrue(all(x.private_experimental_cross ==
                            "NO_RESEARCH_EVENT"
                            for x in replay.private_observations))
        self.assertEqual((replay.action, replay.stage),
                         ("NO_SIGNAL", "UNVERIFIED"))

    def test_05_actual_up_cross_only_when_latest_m15_closes(self):
        replay=research(direction="UP")
        for left,right in replay.studied_windows:
            rows=[x for x in replay.private_observations
                  if (x.profile_left_bars,x.profile_right_bars)==(left,right)]
            self.assertEqual(rows[-1].private_experimental_cross,
                             "EXPERIMENTAL_UP_CROSS")
            self.assertTrue(all(x.private_experimental_cross !=
                                "EXPERIMENTAL_UP_CROSS" for x in rows[:-1]))
            self.assertEqual(rows[-1].private_prior_pivot_level,
                             Decimal("1.1050"))
            self.assertEqual(rows[-1].private_latest_mid_close,
                             Decimal("1.1070"))

    def test_06_actual_down_cross_only_when_latest_m15_closes(self):
        replay=research(direction="DOWN")
        self.assertEqual(
            [x.private_experimental_cross for x
             in replay.private_observations if x.prefix_closed_count==8],
            ["EXPERIMENTAL_DOWN_CROSS", "EXPERIMENTAL_DOWN_CROSS"],
        )

    def test_07_previous_close_already_crossed_is_not_new_event(self):
        replay=research(direction="UP",prev_already_crossed=True)
        self.assertTrue(all(x.private_experimental_cross !=
                            "EXPERIMENTAL_UP_CROSS"
                            for x in replay.private_observations
                            if x.prefix_closed_count==8))

    def test_08_each_event_uses_only_right_confirmed_prior_level(self):
        replay=research(direction="UP")
        self.assertTrue(all(x.private_experimental_cross ==
                            "NO_RESEARCH_EVENT"
                            for x in replay.private_observations
                            if x.prefix_closed_count<8))
        self.assertFalse(any(x.publisher_first_known_proven
                             for x in replay.private_observations))

    def test_09_latest_and_replay_full_prefix_agree(self):
        r=consume()
        replay=r.private_m15_prefix_replay
        latest=r.private_m15_microbreak
        for (left,right),profile in zip(replay.studied_windows,
                                         latest.profiles):
            matched=[x for x in replay.private_observations if
                     (x.profile_left_bars,x.profile_right_bars)==(left,right)]
            self.assertEqual(matched[-1].private_experimental_cross,
                             profile.experimental_cross)
            self.assertEqual(matched[-1].research_state,profile.status)

    def test_10_stale_m15_prefix_replay_is_empty_not_backfilled(self):
        r=consume(asof=ASOF+timedelta(minutes=18))
        replay=r.private_m15_prefix_replay
        self.assertEqual(replay.replayed_closed_m15_inputs,0)
        self.assertEqual(replay.private_observations,())
        self.assertIn("M15",replay.frames_missing_or_stale)
        self.assertEqual(replay.action,"NO_SIGNAL")

    def test_11_forged_latest_microbreak_rejected(self):
        r=consume()
        forged=replace(r.private_m15_microbreak,profiles=())
        with self.assertRaisesRegex(ValueError,"LATEST_RECEIPT"):
            replay_private_m15_closed_prefixes(
                r.private_multibar,r.technical,
                r.private_pivot_sensitivity,forged,
            )

    def test_12_forged_data_rights_rejected(self):
        r=consume()
        forged=replace(r.private_multibar,
                       vendor_source_license_verified=True)
        with self.assertRaisesRegex(ValueError,"RIGHTS_OR_EXECUTION"):
            replay_private_m15_closed_prefixes(
                forged,r.technical,r.private_pivot_sensitivity,
                r.private_m15_microbreak,
            )

    def test_13_modified_sealed_source_cannot_rewrite_history(self):
        r=consume()
        data=r.private_multibar
        histories=list(data.private_closed_histories)
        frame,rows=histories[0]
        histories[0]=(frame,(replace(rows[0],close="1.1001"),)+rows[1:])
        with self.assertRaisesRegex(ValueError,"PRIVATE_INPUT_SHA"):
            replay_private_m15_closed_prefixes(
                replace(data,private_closed_histories=tuple(histories)),
                r.technical,r.private_pivot_sensitivity,
                r.private_m15_microbreak,
            )

    def test_14_requires_exact_typed_source_not_dict_claim(self):
        r=consume()
        for bad in (None,{},[],False):
            with self.subTest(bad=bad), self.assertRaisesRegex(
                    TypeError,"EXACT_TYPED"):
                replay_private_m15_closed_prefixes(
                    bad,r.technical,r.private_pivot_sensitivity,
                    r.private_m15_microbreak,
                )

    def test_15_no_replay_proves_real_oos_or_source_first_known(self):
        a=research(direction="UP")
        self.assertFalse(a.true_historical_oos_accepted)
        self.assertFalse(a.source_publisher_first_known_attested)
        self.assertFalse(a.native_d1_revision_hold_cleared)
        self.assertFalse(a.original_b2s2_source_owner_numeric_approved)
        self.assertFalse(a.broker_bidask_risk_model_approved)
        self.assertFalse(a.may_publish_prices_or_signals)
        self.assertFalse(a.may_trade)

    def test_16_replay_is_deterministic_with_same_immutable_sha_source(self):
        self.assertEqual(research(direction="UP"),research(direction="UP"))

    def test_17_no_new_source_calls_cache_writes_or_broker(self):
        a=research(direction="UP")
        self.assertEqual(
            (a.provider_requests,a.drive_gets_added,
             a.drive_writes,a.broker_orders),(0,0,0,0),
        )

    def test_18_repr_and_public_summary_never_show_derived_events(self):
        a=research(direction="UP")
        self.assertNotIn("EXPERIMENTAL_UP_CROSS",repr(a))
        self.assertNotIn("1.1050",repr(a))
        public=json.dumps(safe_summary(mocked(),drive_gets=3))
        self.assertNotIn("private_observations",public)
        self.assertNotIn("EXPERIMENTAL_UP_CROSS",public)
        self.assertNotIn("private_prior_pivot_level",public)
        self.assertNotIn("1.1050",public)

    def test_19_frozen_receipts_cannot_self_approve(self):
        a=research()
        with self.assertRaises(FrozenInstanceError):
            a.action="BUY"
        with self.assertRaises(FrozenInstanceError):
            a.private_observations[0].actionable_buy_sell=True

    def test_20_current_snapshot_replay_is_not_provider_first_known_oos(self):
        a=research()
        self.assertEqual(a.replay_type,
                         "CURRENT_ARCHIVE_PREFIX_RESEARCH_NOT_HISTORICAL_FIRST_KNOWN")
        self.assertEqual(a.source_price_side,"MID")
        self.assertTrue(all(not x.owner_original_numeric_rule_approved
                            and not x.historical_oos_validated
                            and not x.actionable_buy_sell
                            for x in a.private_observations))

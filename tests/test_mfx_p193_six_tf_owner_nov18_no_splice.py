"""P0.193: six-TF only consumes independently-rooted 18-Nov D1, no P171 seam."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch

from mfx_cache.native_d1_epoch_20261118 import (
    PrivateD1FreshEpochStore as PrivateD1Nov18Store,
)
from mfx_research.six_tf_sealed_archive_consumer import (
    consume_sealed_archives_for_six_tf,
)
from mfx_research.signal_only_six_tf_response import (
    build_signal_only_research_response,
)
from tools.run_mfx_v1_manual_drive_six_tf import (
    ALLOWED_PREFIXES, safe_summary,
)
from test_mfx_p193_owner_nov18_source_readonly import (
    ASOF as D1_ROOT_ASOF, seeded, root_sha,
)
from test_mfx_v1_six_tf_sealed_archive_consumer import (
    ReadOnlyStore, _seed_m5, _seed_native,
)
from mfx_cache.td_m5_codec import digest

ASOF=D1_ROOT_ASOF+timedelta(minutes=3)
SOURCE_HOUR=datetime(2026,11,18,12,0,tzinfo=timezone.utc)


def make_inputs():
    m5,h4,legacy=ReadOnlyStore(),ReadOnlyStore(),ReadOnlyStore()
    with patch("test_mfx_v1_six_tf_sealed_archive_consumer.SOURCE",
               SOURCE_HOUR),patch(
               "test_mfx_v1_six_tf_sealed_archive_consumer.ASOF",ASOF):
        pins=_seed_m5(m5)
    _seed_native(h4,"4h",("2026-11-18 08:00:00",))
    _seed_native(legacy,"1day",("2026-11-10","2026-11-11"))
    return m5,h4,legacy,pins


def consume_nov18(*,old_active=None,p192=None,clock=ASOF):
    m5,h4,legacy,pins=make_inputs()
    v1_tip=digest(legacy.read(
        "manifest",legacy.list_names("manifest")[-1]))
    # The synthetic P192 chunk MUST reference the exact independently
    # SHA-audited synthetic V1 parent from this same six-TF fixture.
    nov18=p192 or seeded(old_sha=v1_tip)
    root=nov18.list_names("manifest")[0]
    with patch.multiple(
        "mfx_research.six_tf_sealed_archive_consumer",
        ROOT_UTC=pins.root_hour_utc,
        ROOT_MANIFEST_SHA256=pins.root_sha256,
        REVIEWED_CHECKPOINT_UTC=pins.checkpoint_hour_utc,
        REVIEWED_CHECKPOINT_SHA256=pins.checkpoint_sha256,
        REVIEWED_CHECKPOINT_PAIRS=pins.checkpoint_pairs,
    ),patch.multiple(
        "mfx_research.p193_owner_nov18_active_d1_reader",
        PINNED_ORIGINAL_D1_V1_HEAD_SHA256=v1_tip,
        PINNED_P192_20261118_ROOT_SHA256=digest(nov18.read("manifest",root)),
    ):
        return consume_sealed_archives_for_six_tf(
            m5,h4,legacy,asof_utc=clock,
            active_d1_epoch_store=old_active,
            owner_nov18_d1_epoch_store=nov18,
        )


class P193NoSpliceSixTimeframeTests(TestCase):
    def test_01_new_source_only_one_bar_and_no_old_preincident_seam(self):
        r=consume_nov18()
        self.assertEqual(r.active_d1_source_epoch,"P192_D1_FRESH_20261118")
        self.assertEqual(r.d1_manifest_pairs_full_sha,1)
        self.assertEqual(r.new_epoch_d1_rows_in_context,1)
        self.assertEqual(r.original_preincident_d1_rows_verified,0)
        self.assertEqual(r.active_d1_composed_history_sha256,"")
        self.assertNotEqual(r.d1_manifest_tip_sha256,
                            r.archived_v1_d1_manifest_tip_sha256)
        self.assertEqual(r.technical.action,"NO_SIGNAL")
        self.assertEqual(r.technical.stage,"UNVERIFIED")
        self.assertFalse(r.may_publish_buy_sell)
        self.assertFalse(r.may_trade)
        self.assertEqual(r.broker_orders,0)

    def test_02_signal_only_response_still_unverified_and_no_price_levels(self):
        response=build_signal_only_research_response(consume_nov18())
        self.assertEqual((response.action,response.stage),
                         ("NO_SIGNAL","UNVERIFIED"))
        self.assertIsNone(response.entry_price)
        self.assertIsNone(response.stop_loss)
        self.assertIsNone(response.take_profit)
        self.assertIsNone(response.net_risk_reward)
        self.assertFalse(response.account_data_rights_verified)

    def test_03_manual_public_summary_rejects_legacy_seam_on_new_source(self):
        r=consume_nov18()
        public=safe_summary(r,drive_gets=12)
        self.assertEqual((public["action"],public["stage"]),
                         ("NO_SIGNAL","UNVERIFIED"))
        self.assertEqual(public["active_d1_source_epoch"],
                         "P192_D1_FRESH_20261118")
        self.assertEqual(public["original_preincident_d1_rows_verified"],0)
        self.assertEqual(public["new_epoch_d1_rows_in_context"],1)
        self.assertEqual(public["drive_writes"],0)
        self.assertEqual(public["broker_orders"],0)

    def test_04_old_epoch_plus_owner_nov18_simultaneously_denied_before_read(self):
        with self.assertRaisesRegex(ValueError,"REJECTS_HISTORICAL"):
            consume_nov18(old_active=seeded())

    def test_05_malformed_or_wrong_v1_parent_fails_before_read(self):
        s=seeded()
        with self.assertRaises(ValueError):
            consume_nov18(p192=s,clock=datetime(2026,11,18,13,0,
                                                tzinfo=timezone.utc))

    def test_06_old_stored_source_not_modified(self):
        self.assertIn("MFX_P192_EURUSD_D1_20261118_FRESH_EPOCH_V1_",
                      ALLOWED_PREFIXES)
        self.assertIn("MFX_P171_EURUSD_D1_20261111_FRESH_EPOCH_V1_",
                      ALLOWED_PREFIXES)
        self.assertIn("MFX_P192",PrivateD1Nov18Store(
            session="offline")._bucket("chunk")[1])

    def test_07_public_summary_does_not_log_raw_ohlc(self):
        import json
        r=consume_nov18()
        public=json.dumps(safe_summary(r,drive_gets=12),sort_keys=True)
        self.assertNotIn("1.1000",public)
        self.assertNotIn("1.1020",public)
        self.assertEqual(r.provider_price_calls,0)
        self.assertEqual(r.drive_cache_writes,0)
        self.assertEqual(r.broker_orders,0)

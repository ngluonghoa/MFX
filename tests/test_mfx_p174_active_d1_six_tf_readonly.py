"""P0.174 hermetic research-only P171 D1 fresh-epoch six-TF source integration.

Never access actual OAuth/Drive/vendor, mutate existing cache, or promote BUY/SELL.
Synthetic source pins are patched ONLY inside hermetic tests; the production
consumer rejects caller fixture pins for the real fresh-D1 source path.
"""
from __future__ import annotations

from copy import deepcopy
from contextlib import nullcontext
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from mfx_cache.td_m5_codec import digest
from mfx_cache.native_d1_fresh_epoch import (
    PrivateD1FreshEpochStore, audit_fresh_epoch, commit_fresh_epoch,
)
from mfx_research.p174_active_d1_epoch_reader import read_active_d1_epoch
from mfx_research.six_tf_sealed_archive_consumer import (
    D1_HOLD_PUBLIC_STATUS, D1_KNOWN_SOURCE_REVISION_HOLD,
    consume_sealed_archives_for_six_tf,
)
from mfx_research.six_tf_readonly_context import FRAMES
from tools.run_mfx_v1_manual_drive_six_tf import (
    ALLOWED_PREFIXES, GetOnlyDriveSession,
)
from test_mfx_p171_d1_fresh_epoch import (
    MemoryEpochStore, fresh, original_sha,
)
from test_mfx_v1_six_tf_sealed_archive_consumer import (
    ReadOnlyStore, _seed_m5, _seed_native,
)

UTC=timezone.utc
ROOT_OBSERVED=datetime(2026,11,15,13,35,tzinfo=UTC)
RESEARCH_ASOF=datetime(2026,11,15,14,10,tzinfo=UTC)
SOURCE_HOUR=datetime(2026,11,15,12,0,tzinfo=UTC)


def make_epoch(*, clock=ROOT_OBSERVED, origin=None):
    store=MemoryEpochStore()
    sha=original_sha() if origin is None else origin
    commit_fresh_epoch(
        store,batch=fresh(),origin_v1_sha=sha,now_utc=clock)
    return store


def archived_tip(store):
    names=store.list_names("manifest")
    return digest(store.read("manifest",names[-1]))


def reviewed_inputs():
    """Fake, explicitly offline source anchors, NOT valid production anchors."""
    m5,h4,d1=ReadOnlyStore(),ReadOnlyStore(),ReadOnlyStore()
    with patch("test_mfx_v1_six_tf_sealed_archive_consumer.SOURCE",SOURCE_HOUR),patch(
            "test_mfx_v1_six_tf_sealed_archive_consumer.ASOF",RESEARCH_ASOF):
        pins=_seed_m5(m5)
    _seed_native(h4,"4h",("2026-11-15 08:00:00",))
    _seed_native(d1,"1day",("2026-11-11",))
    return m5,h4,d1,pins


def consume_offline(m5,h4,d1,pins,*,active=None,asof=RESEARCH_ASOF):
    fresh_pin = (patch.multiple(
        "mfx_research.p174_active_d1_epoch_reader",
        PINNED_ORIGINAL_D1_V1_HEAD_SHA256=archived_tip(d1),
        PINNED_FRESH_D1_20261111_ROOT_SHA256=digest(
            active.read("manifest",active.list_names("manifest")[0])),
    ) if active is not None else nullcontext())
    with fresh_pin,patch.multiple(
        "mfx_research.six_tf_sealed_archive_consumer",
        ROOT_UTC=pins.root_hour_utc,ROOT_MANIFEST_SHA256=pins.root_sha256,
        REVIEWED_CHECKPOINT_UTC=pins.checkpoint_hour_utc,
        REVIEWED_CHECKPOINT_SHA256=pins.checkpoint_sha256,
        REVIEWED_CHECKPOINT_PAIRS=pins.checkpoint_pairs,
    ):
        return consume_sealed_archives_for_six_tf(
            m5,h4,d1,asof_utc=asof,active_d1_epoch_store=active)


class FreshD1SixTFBridgeTests(TestCase):
    def setUp(self):
        # Hermetic in-memory fixtures never masquerade as the actual
        # pinned real GitHub Actions source roots in production code.
        synthetic=make_epoch()
        root=synthetic.list_names("manifest")[0]
        pin=patch.multiple(
            "mfx_research.p174_active_d1_epoch_reader",
            PINNED_ORIGINAL_D1_V1_HEAD_SHA256=original_sha(),
            PINNED_FRESH_D1_20261111_ROOT_SHA256=digest(
                synthetic.read("manifest",root)),
        )
        pin.start()
        self.addCleanup(pin.stop)

    def test_01_fresh_epoch_private_batch_exact_new_label_prefix(self):
        store=make_epoch()
        r=read_active_d1_epoch(
            store,old_v1_manifest_sha256=original_sha(),
            asof_utc=RESEARCH_ASOF)
        self.assertEqual(r.active_source_epoch,"P171_D1_FRESH_20261111")
        self.assertEqual(r.epoch_manifest_pairs_full_sha,1)
        self.assertEqual(len(r.batch.closed_bars),3)
        self.assertEqual(tuple(b.native_open_label for b in r.batch.closed_bars),
                         ("2026-11-11","2026-11-12","2026-11-13"))
        self.assertEqual(r.provider_price_requests,0)
        self.assertEqual(r.drive_writes,0)
        self.assertFalse(r.may_publish_buy_sell)

    def test_02_no_record_or_data_logged_in_repr(self):
        r=read_active_d1_epoch(
            make_epoch(),old_v1_manifest_sha256=original_sha(),
            asof_utc=RESEARCH_ASOF)
        output=repr(r)
        self.assertNotIn("1.10",output)
        self.assertNotIn("closed_bars",output)
        self.assertNotIn("NativeFXBar",output)
        self.assertIn("P171_D1_FRESH_20261111",output)

    def test_03_unseeded_fresh_epoch_never_falls_back_to_legacy(self):
        with self.assertRaisesRegex(ValueError,"UNSEEDED_OR_UNCOMMITTED"):
            read_active_d1_epoch(
                MemoryEpochStore(),old_v1_manifest_sha256=original_sha(),
                asof_utc=RESEARCH_ASOF)

    def test_04_wrong_legacy_original_sha_denied(self):
        with self.assertRaises(ValueError):
            read_active_d1_epoch(make_epoch(),
                old_v1_manifest_sha256="a"*64,asof_utc=RESEARCH_ASOF)

    def test_05_not_observed_at_historical_decision_denied(self):
        with self.assertRaisesRegex(ValueError,"NOT_FIRST_OBSERVED"):
            read_active_d1_epoch(make_epoch(),
                old_v1_manifest_sha256=original_sha(),
                asof_utc=ROOT_OBSERVED-timedelta(seconds=1))

    def test_06_mutated_new_source_ohlc_denied(self):
        store=make_epoch()
        key=next(iter(store.files["chunk"]))
        store.files["chunk"][key]["bars"][0]["close"]="1.00001"
        with self.assertRaises(ValueError):
            read_active_d1_epoch(
                store,old_v1_manifest_sha256=original_sha(),
                asof_utc=RESEARCH_ASOF)

    def test_07_original_sha_read_only_root_not_mutated_by_research(self):
        s=make_epoch()
        before=deepcopy(s.files)
        read_active_d1_epoch(s,old_v1_manifest_sha256=original_sha(),
                             asof_utc=RESEARCH_ASOF)
        self.assertEqual(s.files,before)
        self.assertEqual(s.puts,2)

    def test_08_readonly_get_proxy_only_exact_new_namespace(self):
        self.assertIn("MFX_P171_EURUSD_D1_20261111_FRESH_EPOCH_V1_",
                      ALLOWED_PREFIXES)
        q=PrivateD1FreshEpochStore(session="offline")._bucket("chunk")[1]
        self.assertIn("MFX_P171",q)
        self.assertNotIn("P169",q)

    def test_09_actual_consumer_keeps_original_v1_hold_when_no_fresh(self):
        m,h,d,p=reviewed_inputs()
        r=consume_offline(m,h,d,p)
        self.assertEqual(r.status,D1_HOLD_PUBLIC_STATUS)
        self.assertTrue(r.private_signal_research_suppressed_by_d1_hold)
        self.assertEqual(r.active_d1_source_epoch,"LEGACY_D1_V1")
        self.assertTrue(D1_KNOWN_SOURCE_REVISION_HOLD)

    def test_10_explicit_new_epoch_unblocks_private_technical_only(self):
        m,h,d,p=reviewed_inputs()
        active=make_epoch(origin=archived_tip(d))
        before=[deepcopy(x.objects) for x in (m,h,d)]
        old=deepcopy(active.files)
        r=consume_offline(m,h,d,p,active=active)
        self.assertEqual(
            r.status,"SEALED_READONLY_CACHE_TECHNICAL_RESEARCH_ONLY_NO_SIGNAL")
        self.assertEqual(r.active_d1_source_epoch,"P171_D1_FRESH_20261111")
        self.assertNotEqual(r.d1_manifest_tip_sha256,
                            r.archived_v1_d1_manifest_tip_sha256)
        self.assertEqual(r.d1_manifest_pairs_full_sha,1)
        self.assertEqual(r.technical.action,"NO_SIGNAL")
        self.assertEqual(r.technical.stage,"UNVERIFIED")
        self.assertIsNotNone(r.private_multibar)
        self.assertFalse(r.may_publish_buy_sell)
        self.assertFalse(r.may_trade)
        self.assertEqual(r.broker_orders,0)
        self.assertEqual([x.objects for x in (m,h,d)],before)
        self.assertEqual(active.files,old)

    def test_11_active_new_epoch_must_match_archived_real_v1_parent(self):
        m,h,d,p=reviewed_inputs()
        with self.assertRaises(ValueError):
            consume_offline(m,h,d,p,active=make_epoch())

    def test_12_never_accept_fixture_pins_on_fresh_source(self):
        m,h,d,p=reviewed_inputs()
        with self.assertRaisesRegex(ValueError,"REJECTS_SYNTHETIC_M5_PINS"):
            consume_sealed_archives_for_six_tf(
                m,h,d,asof_utc=RESEARCH_ASOF,
                fixture_pins=p,active_d1_epoch_store=make_epoch())

    def test_13_unverified_new_source_never_promotes_licence_or_economics(self):
        m,h,d,p=reviewed_inputs()
        r=consume_offline(
            m,h,d,p,active=make_epoch(origin=archived_tip(d)))
        self.assertTrue(D1_KNOWN_SOURCE_REVISION_HOLD)
        self.assertFalse(r.source_numeric_entry_rules_approved)
        self.assertFalse(r.provider_account_data_rights_verified)
        self.assertFalse(r.source_first_known_time_proven)
        self.assertFalse(r.bidask_costs_and_sl_tp_net_rr_approved)
        self.assertFalse(r.historical_asof_replay_proven)
        self.assertFalse(r.may_publish_buy_sell)
        self.assertEqual((r.provider_price_calls,r.drive_cache_writes,
                          r.broker_orders),(0,0,0))

    def test_14_malformed_source_epoch_asof_denied(self):
        with self.assertRaisesRegex(ValueError,"EXACT_UTC"):
            read_active_d1_epoch(
                make_epoch(),old_v1_manifest_sha256=original_sha(),
                asof_utc=datetime(2026,11,15,14,10))

    def test_15_no_vendor_trading_or_original_source_modification(self):
        py=Path("tools/run_mfx_v1_manual_drive_six_tf.py").read_text()
        self.assertIn("active_d1_epoch_store=active_d1",py)
        self.assertIn("PrivateD1FreshEpochStore(session)",py)
        self.assertIn("GetOnlyDriveSession",py)
        self.assertIn('"SEALED_READONLY_CACHE_TECHNICAL_RESEARCH_ONLY_NO_SIGNAL"',
                      Path("mfx_research/six_tf_sealed_archive_consumer.py").read_text())

    def test_16_new_epoch_root_trust_anchor_cannot_be_changed(self):
        store=make_epoch()
        with patch(
            "mfx_research.p174_active_d1_epoch_reader."
            "PINNED_FRESH_D1_20261111_ROOT_SHA256",
            "a"*64),self.assertRaisesRegex(ValueError,
                                           "ROOT_TRUST_ANCHOR_CHANGED"):
            read_active_d1_epoch(
                store,old_v1_manifest_sha256=original_sha(),
                asof_utc=RESEARCH_ASOF)

    def test_17_legacy_original_archive_head_pin_cannot_be_changed(self):
        store=make_epoch()
        with patch(
            "mfx_research.p174_active_d1_epoch_reader."
            "PINNED_ORIGINAL_D1_V1_HEAD_SHA256",
            "b"*64),self.assertRaisesRegex(ValueError,
                                           "ORIGINAL_TRUST_ANCHOR_CHANGED"):
            read_active_d1_epoch(
                store,old_v1_manifest_sha256=original_sha(),
                asof_utc=RESEARCH_ASOF)

    def test_18_sha_consistent_rewritten_new_root_still_denied(self):
        # This is stronger than ordinary content-SHA detection: every
        # file/parent/name SHA is internally valid, but the independent
        # reviewed GitHub Actions root trust anchor differs.
        alternate=make_epoch(clock=ROOT_OBSERVED+timedelta(minutes=1))
        self.assertEqual(
            audit_fresh_epoch(
                alternate,origin_v1_sha=original_sha()).manifests,1)
        with self.assertRaisesRegex(ValueError,
                                    "ROOT_TRUST_ANCHOR_CHANGED"):
            read_active_d1_epoch(
                alternate,old_v1_manifest_sha256=original_sha(),
                asof_utc=RESEARCH_ASOF)

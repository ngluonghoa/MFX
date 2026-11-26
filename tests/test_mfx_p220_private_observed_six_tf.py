"""P220: private six-frame replay at different archive-observation cutoffs."""
from dataclasses import replace
from datetime import timedelta
from unittest import TestCase
from unittest.mock import patch

from mfx_cache.td_m5_codec import digest
from mfx_cache.native_d1_epoch_20261118 import audit_fresh_epoch
from mfx_research import p193_owner_nov18_active_d1_reader as p193
from mfx_research.p219_m5_archive_time_prefixes import ObservedObjectTime
from mfx_research.p220_private_observed_six_tf import replay_private_observed_six_tf
import test_mfx_v1_six_tf_sealed_archive_consumer as fixture
from test_mfx_p219_m5_archive_time_prefixes import metadata
from test_mfx_p171_d1_fresh_epoch import MemoryEpochStore, original_sha
from test_mfx_p192_d1_nov18_cutoff import NEXT
from test_mfx_p209_d1_revision_snapshot_cache import stage


class P220ObservedSixTFTests(TestCase):
    def setUp(self):
        self.now = NEXT+timedelta(hours=2)
        self.m5, self.h4 = fixture.ReadOnlyStore(), fixture.ReadOnlyStore()
        with patch.object(fixture, "SOURCE", NEXT-timedelta(hours=2)), patch.object(
                fixture, "ASOF", self.now):
            self.pins = fixture._seed_m5(self.m5)
        self.mm,self.mc = metadata(self.m5)
        fixture._seed_native(self.h4, "4h", ("2026-11-19 08:00:00",))
        name = self.h4.list_names("manifest")[0]
        ref = self.h4.read("manifest",name)["chunk_name"]
        clock = NEXT-timedelta(hours=1, minutes=10)
        self.hm = (ObservedObjectTime(name, clock, clock),)
        ctime = clock-timedelta(seconds=1)
        self.hc = (ObservedObjectTime(ref, ctime, ctime),)
        self.revised = MemoryEpochStore()
        self.original,_ = stage(self.revised)
        original = audit_fresh_epoch(self.original,origin_v1_sha=original_sha())
        self.root = digest(original.last_manifest)
        t = NEXT+timedelta(minutes=5)
        self.dt = (ObservedObjectTime(self.revised.list_names("chunk")[0],t,t),)

    def replay(self, decisions=None, **overrides):
        args = dict(m5_manifests=self.mm,m5_chunks=self.mc,
                    h4_manifests=self.hm,h4_chunks=self.hc,
                    revised_d1_times=self.dt,
                    decisions_utc=decisions or (
                        NEXT-timedelta(hours=1), NEXT-timedelta(minutes=30),
                        NEXT+timedelta(minutes=4), NEXT+timedelta(minutes=5),
                        NEXT+timedelta(minutes=7)),
                    audited_at_utc=self.now,fixture_pins=self.pins)
        args.update(overrides)
        with patch.multiple(p193,PINNED_ORIGINAL_D1_V1_HEAD_SHA256=original_sha(),
                            PINNED_P192_20261118_ROOT_SHA256=self.root):
            return replay_private_observed_six_tf(
                self.m5,self.h4,self.original,self.revised,**args)

    def test_historical_cutoffs_do_not_use_future_batch_or_d1(self):
        r = self.replay()
        self.assertEqual([x.m5_verified_hours for x in r.private_contexts],
                         [0,1,1,1,2])
        self.assertEqual([x.d1_visible_rows for x in r.private_contexts],
                         [0,0,0,2,2])
        self.assertIsNone(r.private_contexts[0].context)
        self.assertEqual(r.public_summary()["cutoffs_with_private_b2s2_requirements"],4)
        for row in r.private_contexts[1:]:
            self.assertEqual(row.readiness.public_action,"NO_SIGNAL")
            self.assertEqual(tuple(g.rule_id for g in row.readiness.gates),("B2","S2"))

    def test_h4_closed_but_not_yet_archived_excluded(self):
        t = NEXT+timedelta(minutes=10)
        hm = (replace(self.hm[0],created_utc=t,modified_utc=t),)
        hc = (replace(self.hc[0],created_utc=t-timedelta(seconds=1),
                      modified_utc=t-timedelta(seconds=1)),)
        r = self.replay(h4_manifests=hm,h4_chunks=hc)
        self.assertTrue(all(x.h4_visible_rows==0 for x in r.private_contexts))
        self.assertIn("H4",r.private_contexts[-1].context.missing_or_stale_frames)

    def test_no_legacy_d1_splice_before_private_observation(self):
        r = self.replay((NEXT+timedelta(minutes=4),))
        x = r.private_contexts[0]
        self.assertEqual(x.d1_visible_rows,0)
        self.assertIn("D1",x.context.missing_or_stale_frames)
        self.assertFalse(x.readiness.d1_calendar_qualified)

    def test_d1_metadata_cannot_predate_runner_observation(self):
        t = NEXT-timedelta(seconds=1)
        with self.assertRaisesRegex(ValueError,"BEFORE_OBSERVATION"):
            self.replay(revised_d1_times=(replace(self.dt[0],created_utc=t,
                                                  modified_utc=t),))

    def test_h4_sha_tamper_rejected(self):
        k = self.h4.list_names("chunk")[0]
        self.h4.objects["chunk"][k]["bars"][0]["close"]="1.1001"
        with self.assertRaises(ValueError):
            self.replay()

    def test_d1_sha_tamper_rejected(self):
        self.revised.files["chunk"][self.dt[0].name]["rows"][0]["close"]="1.1001"
        with self.assertRaises(ValueError):
            self.replay()

    def test_empty_revised_store_is_missing_not_canonical_fallback(self):
        self.revised = MemoryEpochStore()
        r = self.replay(revised_d1_times=())
        self.assertEqual(r.d1_snapshots_verified,0)
        self.assertTrue(all(x.d1_visible_rows==0 for x in r.private_contexts))

    def test_scope_remains_private_no_real_oos(self):
        import json
        r = self.replay()
        d = r.public_summary()
        self.assertFalse(d["historical_oos_qualified"])
        self.assertFalse(d["canonical_source_selected"])
        self.assertFalse(d["publisher_first_known_verified"])
        self.assertFalse(d["may_publish_buy_sell"])
        self.assertEqual(d["action"],"NO_SIGNAL")
        self.assertNotIn("experimental_cross",json.dumps(d))
        self.assertNotIn("1.1000",json.dumps(d))
        self.assertEqual(self.revised.puts,1)

"""P220: private six-frame replay at different archive-observation cutoffs."""
from dataclasses import replace
from datetime import timedelta
from unittest import TestCase
from unittest.mock import patch

from mfx_cache.td_m5_codec import digest
from mfx_cache.native_d1_epoch_20261118 import audit_fresh_epoch
from mfx_research import p193_owner_nov18_active_d1_reader as p193
from mfx_research.p219_m5_archive_time_prefixes import ObservedObjectTime
from mfx_research.p220_private_observed_six_tf import (
    replay_private_observed_six_tf, _archive_freshness_census,
)
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

    def test_p222_core_four_distinct_from_all_six(self):
        r = self.replay()
        d = r.public_summary()["archive_freshness_census"]
        self.assertEqual(d["sampled_commit_instants"], 2)
        self.assertEqual(d["fresh_by_frame"],
                         {"M5":0,"M15":2,"M30":2,"H1":2,"H4":2,"D1":1})
        self.assertEqual(d["four_structural_frames_fresh"],1)
        self.assertEqual(d["all_six_frames_fresh"],0)
        self.assertEqual(d["four_structural_fresh_m5_stale"],1)
        self.assertFalse(d["signal_eligibility_assessed"])
        self.assertFalse(d["d1_calendar_qualified"])
        self.assertFalse(r.public_summary()["may_publish_buy_sell"])

    def test_p222_no_future_commit_in_census(self):
        r = self.replay((NEXT+timedelta(minutes=4),))
        d = r.archive_freshness_census
        self.assertEqual(d.sampled_commit_instants,1)
        self.assertEqual(d.four_structural_frames_fresh,0)

    def test_p222_same_commit_clock_counted_once_newest_hour(self):
        t = NEXT+timedelta(minutes=7)
        d = _archive_freshness_census(
            ((t,NEXT-timedelta(hours=1)),(t,NEXT),
             (t+timedelta(hours=1),NEXT+timedelta(hours=1))), (), (), cutoff=t)
        self.assertEqual(d.sampled_commit_instants,1)
        self.assertEqual(dict(d.fresh_by_frame),
                         {"M5":0,"M15":1,"M30":1,"H1":1,"H4":0,"D1":0})
        self.assertEqual(d.four_structural_frames_fresh,0)

    def test_p222_no_visible_d1_no_structural_freshness(self):
        self.revised = MemoryEpochStore()
        d = self.replay(revised_d1_times=()).archive_freshness_census
        self.assertEqual(d.sampled_commit_instants,2)
        self.assertEqual(d.four_structural_frames_fresh,0)
        self.assertEqual(dict(d.fresh_by_frame)["D1"],0)

    def test_p223_replays_core_cutoff_not_in_requested_sample(self):
        r = self.replay((self.now,))
        self.assertEqual(len(r.private_contexts), 1)
        self.assertEqual(len(r.private_core_contexts), 1)
        row = r.private_core_contexts[0]
        self.assertEqual(row.decision_utc, NEXT+timedelta(minutes=7))
        self.assertEqual(row.m5_verified_hours, 2)
        self.assertEqual(row.d1_visible_rows, 2)
        self.assertNotIn("M5", {f.frame for f in row.context.frames})
        self.assertEqual(row.readiness.public_action, "NO_SIGNAL")
        d = r.public_summary()["core_structural_replay"]
        self.assertEqual(d["core_cutoffs_replayed"], 1)
        self.assertEqual(d["core_technical_receipts_complete"], 1)
        self.assertEqual(d["pretrigger_h1_draft_contexts_computed"], 0)
        self.assertIsNotNone(row.pretrigger_h1)
        self.assertIsNotNone(row.pretrigger_native)
        self.assertIsNotNone(row.pretrigger_m15)
        self.assertIsNotNone(row.boundary)
        self.assertEqual(d['boundary_h1_paths_inspected'], 0)
        self.assertEqual(d['boundary_h4_paths_inspected'], 0)
        self.assertFalse(d['boundary_invalidation_buffer_selected'])
        self.assertEqual(d['pretrigger_m15_draft_geometry_computed'], 0)
        self.assertEqual(d['pretrigger_m15_history_to_settled_setup_boundary'], 0)
        self.assertEqual(d['pretrigger_h4_draft_structures_computed'], 0)
        self.assertEqual(d['pretrigger_d1_fresh_vintages_with_five_rows'], 0)
        self.assertEqual(d['pretrigger_h1_h4_and_unqualified_d1_inputs_present'], 0)
        self.assertEqual(d["cutoffs_with_basic_structural_ingredients_one_or_both_sides"],0)
        self.assertFalse(d["market_signal_eligibility_assessed"])

    def test_p223_duplicate_sample_reuses_receipt(self):
        r = self.replay()
        self.assertIs(r.private_core_contexts[0],r.private_contexts[-1])
        identity = r.public_summary()["private_trigger_slot_accounting"]
        self.assertGreaterEqual(identity["repeated_paired_slot_observations"],1)
        self.assertFalse(identity["persistent_idempotence_verified"])
        self.assertEqual(r.public_summary()["core_structural_replay"][
            "core_cutoffs_not_replayed_due_to_limit"],0)

    def test_p223_future_and_missing_d1_never_backfilled(self):
        r = self.replay((NEXT+timedelta(minutes=4),))
        self.assertEqual(r.private_core_contexts,())
        self.assertEqual(r.public_summary()["core_structural_replay"][
            "core_cutoffs_replayed"],0)
        self.revised = MemoryEpochStore()
        r = self.replay(revised_d1_times=())
        self.assertEqual(r.private_core_contexts,())

    def test_p223_core_clock_not_published(self):
        import json
        r = self.replay((self.now,))
        public = json.dumps(r.public_summary())
        self.assertNotIn("private_core_cutoffs", public)
        self.assertNotIn("private_core_contexts", public)
        self.assertNotIn(r.private_core_contexts[0].decision_utc.isoformat(),public)
        self.assertNotIn("experimental_cross",public)
        self.assertEqual(r.public_summary()["action"],"NO_SIGNAL")

"""P219 current archive-time proxy prevents closed-but-not-yet-sealed use."""
from dataclasses import replace
from datetime import timedelta
from unittest import TestCase
from unittest.mock import patch

from mfx_cache.td_m5_codec import digest
from mfx_research.p219_m5_archive_time_prefixes import (
    ObservedObjectTime, replay_m5_current_metadata_prefixes,
)
import test_mfx_v1_six_tf_sealed_archive_consumer as fixture


def metadata(store, *, delay=timedelta(minutes=7)):
    manifests, chunks = [], []
    for name in store.list_names("manifest"):
        m = store.read("manifest", name)
        from datetime import datetime
        t = datetime.fromisoformat(m["hour_utc"])+timedelta(hours=1)+delay
        manifests.append(ObservedObjectTime(name, t, t))
        c = t-timedelta(seconds=1)
        chunks.append(ObservedObjectTime(m["chunk_name"], c, c))
    return tuple(manifests), tuple(chunks)


class P219ArchiveTimeTests(TestCase):
    def setUp(self):
        self.store = fixture.ReadOnlyStore()
        self.pins = fixture._seed_m5(self.store)
        self.m, self.c = metadata(self.store)
        self.now = fixture.ASOF+timedelta(hours=3)

    def replay(self, decisions, **kw):
        args = dict(manifests=self.m, chunks=self.c,
                    decisions_utc=decisions, audited_at_utc=self.now,
                    fixture_pins=self.pins)
        args.update(kw)
        return replay_m5_current_metadata_prefixes(self.store, **args)

    def test_delayed_close_is_not_available_until_manifest(self):
        t = self.m[0].created_utc
        r = self.replay((t-timedelta(seconds=1), t, self.m[1].created_utc))
        self.assertEqual(tuple(p.verified_raw_hours for p in r.private_prefixes),
                         (0, 1, 2))
        self.assertEqual(tuple(len(p.private_m5) for p in r.private_prefixes),
                         (0, 12, 24))
        self.assertEqual([len(x) for _, x in r.private_prefixes[1].private_derived],
                         [4, 2, 1])
        self.assertEqual([len(x) for _, x in r.private_prefixes[2].private_derived],
                         [8, 4, 2])

    def test_catchup_old_and_new_hours_are_not_backdated(self):
        same = self.m[1].created_utc
        first = replace(self.m[0], created_utc=same-timedelta(seconds=10),
                        modified_utc=same-timedelta(seconds=10))
        first_chunk = replace(self.c[0], created_utc=same-timedelta(seconds=11),
                              modified_utc=same-timedelta(seconds=11))
        r = self.replay((same-timedelta(seconds=12), same),
                        manifests=(first,self.m[1]), chunks=(first_chunk,self.c[1]))
        self.assertEqual(tuple(p.verified_raw_hours for p in r.private_prefixes),
                         (0, 2))

    def test_missing_duplicate_or_foreign_metadata_denied(self):
        for m in (self.m[:1], (self.m[0], self.m[0]),
                  (self.m[0], replace(self.m[1], name="foreign.json"))):
            with self.assertRaises(ValueError):
                self.replay((self.now,), manifests=m)

    def test_modified_and_future_metadata_denied(self):
        with self.assertRaises(ValueError):
            replace(self.m[0], modified_utc=self.m[0].created_utc+timedelta(seconds=1))
        t = self.now+timedelta(seconds=1)
        with self.assertRaisesRegex(ValueError, "CLOCK_DRIFT"):
            self.replay((self.now,), manifests=(
                self.m[0], replace(self.m[1], created_utc=t, modified_utc=t)))

    def test_chunk_created_before_close_or_after_manifest_denied(self):
        for t in (fixture.SOURCE, self.m[0].created_utc+timedelta(seconds=1)):
            with self.assertRaisesRegex(ValueError, "COMMIT_CLOCK_DRIFT"):
                self.replay((self.now,), chunks=(
                    replace(self.c[0], created_utc=t, modified_utc=t), self.c[1]))

    def test_current_content_tamper_still_fails_sha(self):
        k = self.store.list_names("chunk")[0]
        self.store.objects["chunk"][k]["bars"][0]["close"] = "1.1001"
        with self.assertRaises(ValueError):
            self.replay((self.now,))

    def test_nonmonotone_or_future_decision_denied(self):
        for t in ((self.now,self.now), (self.now+timedelta(seconds=1),),
                  (self.now.replace(tzinfo=None),)):
            with self.assertRaises(ValueError):
                self.replay(t)

    def test_rolling_older_raw_never_backfilled_into_prefix(self):
        self.store = fixture.ReadOnlyStore()
        self.now = fixture.SOURCE+timedelta(hours=260)
        with patch.object(fixture, "ASOF", self.now):
            pins = fixture._seed_m5(self.store, count=257)
        names = self.store.list_names("manifest")
        checkpoint = self.store.read("manifest", names[1])
        self.pins = replace(pins, checkpoint_pairs=2,
                            checkpoint_hour_utc=checkpoint["hour_utc"],
                            checkpoint_sha256=digest(checkpoint))
        self.m,self.c = metadata(self.store)
        r = self.replay((self.m[0].created_utc, self.m[1].created_utc, self.now))
        self.assertEqual(r.current_raw_sha_hours, 256)
        self.assertEqual(tuple(p.eligible_but_raw_not_reread_hours
                               for p in r.private_prefixes), (1,1,1))
        self.assertEqual(tuple(p.verified_raw_hours for p in r.private_prefixes),
                         (0,1,256))

    def test_current_metadata_is_not_first_known_or_oos(self):
        import json
        r = self.replay((self.now,))
        public = r.public_summary()
        self.assertFalse(public["metadata_historically_authenticated"])
        self.assertFalse(public["publisher_first_known_verified"])
        self.assertFalse(public["historical_oos_qualified"])
        self.assertEqual(public["action"], "NO_SIGNAL")
        self.assertNotIn("private_m5", json.dumps(public))
        self.assertNotIn(self.pins.root_sha256, json.dumps(public))

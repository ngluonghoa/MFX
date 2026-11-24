"""P211 revised D1 research stays separate from canonical technical context."""
from dataclasses import replace
from datetime import timedelta
from unittest import TestCase

from mfx_cache.native_d1_epoch_20261118 import audit_fresh_epoch
from mfx_cache.td_m5_codec import digest
from mfx_research.p211_private_revised_six_tf import compose_private_revised_six_tf
from mfx_research.six_tf_readonly_context import build_six_timeframe_readonly_context
from test_mfx_p171_d1_fresh_epoch import MemoryEpochStore, original_sha
from test_mfx_p192_d1_nov18_cutoff import NEXT, source
from test_mfx_p209_d1_revision_snapshot_cache import stage
from test_mfx_v1_six_tf_readonly_context import m5, h4


class P211PrivateSixTFTests(TestCase):
    def setUp(self):
        self.sidecar = MemoryEpochStore()
        original, _ = stage(self.sidecar)
        self.original = audit_fresh_epoch(original, origin_v1_sha=original_sha())
        self.root = digest(self.original.last_manifest)
        self.now = NEXT + timedelta(minutes=1)
        self.m5 = m5(start=self.now.replace(minute=0, second=0) - timedelta(hours=1))
        self.h4 = h4(now=self.now, labels=("2026-11-19 08:00:00",))
        old = source()
        self.canonical = build_six_timeframe_readonly_context(
            self.m5, self.h4, replace(old, closed_bars=tuple(
                b for b in old.closed_bars if b.native_open_label == "2026-11-18")),
            asof_utc=self.now,
        )

    def compose(self, **overrides):
        args = dict(original=self.original, expected_original_sha=self.root,
                    m5=self.m5, h4=self.h4, canonical=self.canonical,
                    asof_utc=self.now)
        args.update(overrides)
        return compose_private_revised_six_tf(self.sidecar, **args)

    def test_01_same_intraday_only_d1_changes(self):
        r = self.compose()
        self.assertEqual(r.revised_rows, 2)
        self.assertEqual(r.context.total_frames, 6)
        self.assertEqual(r.context.frames[:-1], self.canonical.frames[:-1])
        self.assertEqual(r.context.frames[-1].source_label, "2026-11-19")
        self.assertEqual(self.canonical.frames[-1].source_label, "2026-11-18")
        self.assertEqual(r.public_summary()["action"], "NO_SIGNAL")
        self.assertFalse(r.public_summary()["canonical_source_selected"])
        self.assertEqual(self.sidecar.puts, 1)

    def test_02_root_mismatch_denied(self):
        with self.assertRaisesRegex(ValueError, "CONTEXT_OR_ROOT_DRIFT"):
            self.compose(expected_original_sha="0" * 64)

    def test_03_forged_signal_denied(self):
        with self.assertRaisesRegex(ValueError, "CONTEXT_OR_ROOT_DRIFT"):
            self.compose(canonical=replace(
                self.canonical, may_publish_verified_buy_sell=True))

    def test_04_absent_snapshot_no_fake_context(self):
        self.sidecar = MemoryEpochStore()
        r = self.compose()
        self.assertIsNone(r.context)
        self.assertEqual(r.public_summary()["status"], "P211_NO_VISIBLE_SNAPSHOT")

    def test_05_intraday_input_drift_denied(self):
        changed = (replace(self.m5[0], close="1.1006"),) + self.m5[1:]
        with self.assertRaisesRegex(ValueError, "INTRADAY_OR_AUTHORITY_DRIFT"):
            self.compose(m5=changed)

    def test_06_public_summary_contains_no_private_values(self):
        import json
        r = self.compose()
        public = json.dumps(r.public_summary())
        self.assertNotIn(r.private_identity, public)
        self.assertNotIn("2026-11-19", public)
        self.assertNotIn("1.1000", public)
        self.assertNotIn('"frames"', public)

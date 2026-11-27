"""P266 private EMA seed and first-probe source identity."""
from dataclasses import replace
from unittest import TestCase

from mfx_cache.v2_engine import derive_intraday
from mfx_research.p232_delayed_middle_pairs import replay_delayed_middle_pairs
from mfx_research.p263_private_ema_watch import (
    _observe_archive_ema, bind_private_ema_to_trigger,
)
from test_mfx_p263_private_ema_watch import fixture, observe


class P266Tests(TestCase):
    def test_earlier_seed_change_binds_different_digest(self):
        raw, clocks = fixture(101)
        a = observe(raw, clocks)
        b = observe((replace(raw[0], high="1.3"),)+raw[1:], clocks)
        self.assertEqual(a.short_context_sha256, b.short_context_sha256)
        self.assertNotEqual(a.comparison.context_sha256, b.comparison.context_sha256)
        c = observe(raw[:600]+(replace(raw[600], high="1.3"),)+raw[601:], clocks)
        self.assertNotEqual(a.short_context_sha256, c.short_context_sha256)

    def test_probe_must_be_exact_source_not_caller_price(self):
        raw, clocks = fixture()
        known, end = clocks[-1]
        probe = derive_intraday(raw[-9:-6], "M15", asof_utc=known).candles[0]
        with self.assertRaisesRegex(ValueError, "P266_EXACT_PROBE_SOURCE_DRIFT"):
            _observe_archive_ema(raw, clocks, replace(probe, high="1.9"),
                                 cutoff=observe(raw, clocks).cutoff_utc, decision=known)

    def test_same_clock_different_probe_receipt_rejected(self):
        raw, clocks = fixture()
        r = replay_delayed_middle_pairs(raw, clocks, (), ())
        row = r.samples[-1]
        changed = raw[:-9]+(replace(raw[-9], high="1.3"),)+raw[-8:]
        bad = replace(row, ema_watch=observe(changed, clocks))
        with self.assertRaisesRegex(ValueError, "P266_EMA_TRIGGER_SOURCE_DRIFT"):
            replace(r, samples=r.samples[:-1]+(bad,)).public_summary()

    def test_no_second_probe_or_later_price_leak(self):
        raw, clocks = fixture(101)
        a = observe(raw, clocks)
        changed = raw[:-6]+tuple(replace(x, high="1.9") for x in raw[-6:])
        self.assertEqual(a, observe(changed, clocks))

    def test_digest_shapes_and_public_redaction(self):
        raw, clocks = fixture(101)
        r = replay_delayed_middle_pairs(raw, clocks, (), ())
        row = r.samples[-1]
        ema = row.ema_watch
        self.assertTrue(bind_private_ema_to_trigger(ema, row.trigger_identity, row.h1.cutoff_utc))
        with self.assertRaisesRegex(ValueError, "P266_SHORT_SEED_CONTEXT_DRIFT"):
            bind_private_ema_to_trigger(replace(ema, short_context_sha256="invalid"),
                                       row.trigger_identity, row.h1.cutoff_utc)
        bad = replace(ema, comparison=replace(ema.comparison,
                                              context_sha256=ema.short_context_sha256))
        with self.assertRaisesRegex(ValueError, "P266_LONG_SEED_CONTEXT_DRIFT"):
            bind_private_ema_to_trigger(bad, row.trigger_identity, row.h1.cutoff_utc)
        s = str(r.public_summary())
        for value in (ema.short_context_sha256, ema.comparison.context_sha256,
                      ema.probe_source_sha256):
            self.assertNotIn(value, s)
        self.assertIn("NO_SIGNAL", s)

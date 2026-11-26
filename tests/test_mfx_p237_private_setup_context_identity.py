"""P237 source context identity is private, causal, bounded and NO_SIGNAL."""
from dataclasses import replace
from datetime import timedelta
import json
from unittest import TestCase

from mfx_research.p232_delayed_middle_pairs import replay_delayed_middle_pairs
from test_mfx_p232_delayed_middle_pairs import shaped, START
from test_mfx_p228_pretrigger_native import h4_fixture, vintage

CUTOFF = START+timedelta(hours=4, minutes=15)


def run(raw=None, clocks=None, h4=None, snapshots=None):
    fixture_raw, fixture_clocks = shaped()
    raw = fixture_raw if raw is None else raw
    clocks = fixture_clocks if clocks is None else clocks
    h4 = h4_fixture() if h4 is None else h4
    old = vintage(CUTOFF-timedelta(hours=1))
    snapshots = ((old.observed,old),) if snapshots is None else snapshots
    return replay_delayed_middle_pairs(raw, clocks, h4, snapshots)


class P237SetupContextTests(TestCase):
    def test_joint_private_binding_and_coverage(self):
        r=run()
        row=r.samples[-1]
        self.assertIsNotNone(row.setup_context_identity)
        self.assertEqual(len(row.setup_context_identity.bounded_context_sha256),64)
        self.assertEqual(r.public_summary()["bounded_setup_context_identity_coverage"],1)
        self.assertFalse(r.public_summary()["full_setup_revision_identity_verified"])

    def test_posttrigger_changes_do_not_rewrite_source_context(self):
        raw,clocks=shaped()
        a=run(raw,clocks).samples[-1]
        changed=raw[:-1]+(replace(raw[-1],low="0.99",close="1.00"),)
        b=run(changed,clocks).samples[-1]
        self.assertEqual(a.setup_context_identity,b.setup_context_identity)
        self.assertNotEqual(a.delayed_decision,b.delayed_decision)

    def test_same_trigger_different_pretrigger_source_changes_binding(self):
        raw,clocks=shaped()
        a=run(raw,clocks).samples[-1]
        changed=(replace(raw[0],open="1.101"),)+raw[1:]
        b=run(changed,clocks).samples[-1]
        self.assertEqual(a.trigger_identity,b.trigger_identity)
        self.assertNotEqual(a.setup_context_identity,b.setup_context_identity)

    def test_later_d1_vintage_cannot_rewrite_frozen_context(self):
        old=vintage(CUTOFF-timedelta(hours=1))
        later=replace(vintage(CUTOFF+timedelta(minutes=1)),identity="later",
                      rows=old.rows[:-1]+(replace(old.rows[-1],close="1.15"),))
        a=run(snapshots=((old.observed,old),)).samples[-1]
        b=run(snapshots=((old.observed,old),(later.observed,later))).samples[-1]
        self.assertEqual(a.setup_context_identity,b.setup_context_identity)
        prior=replace(later,observed=CUTOFF-timedelta(minutes=1))
        c=run(snapshots=((old.observed,old),(prior.observed,prior))).samples[-1]
        self.assertNotEqual(a.setup_context_identity,c.setup_context_identity)

    def test_missing_native_context_does_not_fabricate_identity(self):
        row=run(h4=(),snapshots=()).samples[-1]
        self.assertIsNone(row.setup_context_identity)

    def test_private_digest_and_forged_binding_are_not_published(self):
        r=run()
        row=r.samples[-1]
        summary=json.dumps(r.public_summary())
        self.assertNotIn(row.setup_context_identity.bounded_context_sha256,summary)
        self.assertNotIn(row.h1.source_context_sha256,summary)
        bad=replace(row,setup_context_identity=replace(row.setup_context_identity,
                                                       persistent_idempotence_verified=True))
        with self.assertRaisesRegex(ValueError,"SETUP_CONTEXT_BINDING_DRIFT"):
            replace(r,samples=r.samples[:-1]+(bad,)).public_summary()

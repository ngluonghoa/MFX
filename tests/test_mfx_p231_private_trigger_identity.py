"""P231 in-memory slot identity does not authorize signals or expiry."""
from dataclasses import replace
from datetime import timedelta
from unittest import TestCase

from mfx_research.p231_private_trigger_identity import (
    identify_private_trigger_pair, summarize_private_trigger_slots,
)
from test_mfx_p227_pretrigger_h1 import fixture, START

OPEN = START+timedelta(hours=4,minutes=45)
DECISION = START+timedelta(hours=5,minutes=7)


def run(raw, decision=DECISION):
    return identify_private_trigger_pair(raw,latest_m15_open=OPEN,decision=decision)


class P231PrivateTriggerIdentityTests(TestCase):
    def test_same_source_pair_different_decisions_deduplicate(self):
        raw,_ = fixture()
        a,b = run(raw),run(raw,DECISION+timedelta(minutes=3))
        self.assertEqual(a,b)
        r = summarize_private_trigger_slots((a,b))
        self.assertEqual(r["distinct_paired_trigger_slots"],1)
        self.assertEqual(r["repeated_paired_slot_observations"],1)
        self.assertFalse(r["persistent_idempotence_verified"])
        self.assertFalse(r["expiry_policy_selected"])

    def test_changed_trigger_payload_same_logical_slot_fails_closed(self):
        raw,_ = fixture()
        a,b = run(raw),run(raw[:-1]+(replace(raw[-1],close="1.15"),))
        self.assertEqual(a.private_slots[0].slot_sha256,b.private_slots[0].slot_sha256)
        with self.assertRaisesRegex(ValueError,"PAYLOAD_CONFLICT"):
            summarize_private_trigger_slots((a,b))

    def test_earlier_history_not_a_trigger_revision(self):
        raw,_ = fixture()
        a,b = run(raw),run((replace(raw[0],close="1.15"),)+raw[1:])
        self.assertEqual(a,b)
        self.assertFalse(a.full_setup_revision_identity_verified)

    def test_partial_or_reordered_pair_conflict(self):
        raw,_ = fixture()
        a = run(raw)
        reverse = replace(a,private_slots=a.private_slots[::-1])
        with self.assertRaisesRegex(ValueError,"PAIR_CONFLICT"):
            summarize_private_trigger_slots((a,reverse))

    def test_noncontiguous_trigger_rejected(self):
        raw,_ = fixture()
        with self.assertRaises(ValueError):
            run(raw[:-4]+raw[-3:])

    def test_no_price_or_identity_public(self):
        import json
        raw,_ = fixture()
        a = run(raw)
        r = json.dumps(summarize_private_trigger_slots((a,)))
        self.assertNotIn(a.private_slots[0].slot_sha256,r)
        self.assertNotIn(a.private_slots[0].trigger_payload_sha256,r)
        self.assertEqual(a.action,"NO_SIGNAL")

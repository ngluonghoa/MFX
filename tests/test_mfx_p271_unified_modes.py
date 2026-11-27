"""P271 one P161 engine, explicit validation callers, no activation."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from mfx_research.mfx_b2s2_confirmed_policy_v2 import compute_mfx_b2s2_v2_closed_candidate
from mfx_research.option_b_v2_chronological_replay import replay_option_b_v2
from mfx_research.unified_modes import MfxMode
from test_mfx_v1_p161_option_b_confirmed_b2s2_v2 import inputs
from test_mfx_p165_option_b_v2_chronological_replay import snapshot


class P271Tests(TestCase):
    def test_same_candidate_in_both_modes_and_legacy(self):
        for rule in ("B2", "S2"):
            x = inputs(rule)
            r = compute_mfx_b2s2_v2_closed_candidate(**x, mode=MfxMode.RESEARCH)
            v = compute_mfx_b2s2_v2_closed_candidate(**x, mode=MfxMode.VALIDATION)
            self.assertEqual(r, v)
            self.assertEqual(r, compute_mfx_b2s2_v2_closed_candidate(**x))
            self.assertEqual(v.public_action, "NO_SIGNAL")
            self.assertFalse(v.true_historical_oos_qualified)

    def test_production_denied_before_policy_read(self):
        x = inputs()
        with patch("mfx_research.mfx_b2s2_confirmed_policy_v2.read_mfx_confirmed_b2s2_v2") as read:
            with self.assertRaisesRegex(ValueError, "P271_PRODUCTION"):
                compute_mfx_b2s2_v2_closed_candidate(**x, mode=MfxMode.PRODUCTION)
            read.assert_not_called()

    def test_no_string_or_bool_mode(self):
        for bad in ("RESEARCH", "VALIDATION", True, None):
            with self.assertRaisesRegex(TypeError, "P271_EXACT"):
                compute_mfx_b2s2_v2_closed_candidate(**inputs(), mode=bad)

    def test_validation_cannot_approve_fake_policy(self):
        x = inputs()
        x["policy"] = replace(x["policy"], live_signals_allowed=True)
        with self.assertRaisesRegex(ValueError, "P161_DRAFT"):
            compute_mfx_b2s2_v2_closed_candidate(**x, mode=MfxMode.VALIDATION)

    def test_replay_actually_calls_validation_mode(self):
        s = snapshot()
        with patch("mfx_research.option_b_v2_chronological_replay.compute_mfx_b2s2_v2_closed_candidate",
                   wraps=compute_mfx_b2s2_v2_closed_candidate) as run:
            r = replay_option_b_v2((s,), inputs()["policy"])
            self.assertIs(run.call_args.kwargs["mode"], MfxMode.VALIDATION)
            self.assertEqual(r.action, "NO_SIGNAL")

    def test_validation_not_allowed_to_relabel_real_data(self):
        x = inputs()
        b = x["bars"]
        first = replace(b.daily[0], observation=replace(b.daily[0].observation,
                                                       provider_id="REAL:SOURCE"))
        x["bars"] = replace(b, daily=(first,)+b.daily[1:])
        for mode in (MfxMode.RESEARCH, MfxMode.VALIDATION):
            with self.assertRaises(ValueError):
                compute_mfx_b2s2_v2_closed_candidate(**x, mode=mode)

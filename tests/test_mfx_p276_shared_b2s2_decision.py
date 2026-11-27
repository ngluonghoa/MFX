"""P276 shared decision core and existing observed setup integration."""
from unittest import TestCase
from unittest.mock import Mock

from mfx_research.shared_b2s2_decision import decide_b2s2
from test_mfx_p237_private_setup_context_identity import run


class P276Tests(TestCase):
    def test_complete_mirrored_candidates(self):
        self.assertEqual(decide_b2s2("B2", "UP", "UP", False, lambda: (True, True, True)).action, "BUY")
        self.assertEqual(decide_b2s2("S2", "DOWN", "DOWN", False, lambda: (True, True, True)).action, "SELL")

    def test_unknown_trend_short_circuits_geometry(self):
        geometry = Mock(side_effect=AssertionError("not eligible"))
        for rule, trend in (("B2", "UP"), ("S2", "DOWN")):
            self.assertEqual(decide_b2s2(rule, "UNKNOWN", trend, None, geometry).reason,
                             "P018_TREND_NOT_SUPPORTED")
        geometry.assert_not_called()

    def test_invalidation_gate_and_unknown(self):
        geometry = Mock(side_effect=AssertionError("not eligible"))
        self.assertEqual(decide_b2s2("B2", "UP", "UP", True, geometry).reason,
                         "P018_STRUCTURE_INVALIDATED")
        self.assertEqual(decide_b2s2("B2", "UP", "UP", None, geometry).reason,
                         "P276_STRUCTURE_UNVERIFIED")
        geometry.assert_not_called()

    def test_geometry_reason_order_and_missing(self):
        cases = ((None, "P276_GEOMETRY_UNAVAILABLE"),
                 ((False, False, False), "P018_PRIOR_M15_NOT_NEAR_H1_ZONE"),
                 ((True, False, False), "P018_NO_LATEST_MICRO_BREAK"),
                 ((True, True, False), "P018_SYNTHETIC_ANTI_CHASE_LIMIT"))
        for values, reason in cases:
            result = decide_b2s2("S2", "DOWN", "DOWN", False, lambda: values)
            self.assertEqual((result.action, result.reason), ("NO_SIGNAL", reason))

    def test_reject_forged_types(self):
        with self.assertRaises(TypeError):
            decide_b2s2("B2", "UP", "UP", 0, lambda: (True, True, True))
        with self.assertRaises(TypeError):
            decide_b2s2("B2", "UP", "UP", False, lambda: (1, True, True))

    def test_bound_observed_setup_uses_core_without_signals(self):
        replay = run()
        receipt = replay.samples[-1].setup_context_identity
        self.assertIsNotNone(receipt)
        decisions = receipt.private_candidate_decisions
        self.assertEqual(tuple(x.rule_id for x in decisions), ("B2", "S2"))
        self.assertTrue(all(x.action == "NO_SIGNAL" and x.reason == "P018_TREND_NOT_SUPPORTED"
                            for x in decisions))
        summary = str(replay.public_summary())
        self.assertNotIn("P018_TREND_NOT_SUPPORTED", summary)
        self.assertNotIn("private_candidate_decisions", summary)

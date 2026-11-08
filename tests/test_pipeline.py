import unittest
from forex_trading.pipeline import PipelineSnapshot, STEPS, StepStatus, can_publish_full_analysis


class PipelineTests(unittest.TestCase):
    def test_all_stages_named_and_ordered(self):
        self.assertEqual(len(STEPS), 8)
        self.assertEqual(len(set(STEPS)), 8)

    def test_missing_step_rejected(self):
        with self.assertRaises(ValueError):
            PipelineSnapshot(tuple((s, StepStatus.COMPLETE) for s in STEPS[:-1]))

    def test_reordered_step_rejected(self):
        with self.assertRaises(ValueError):
            PipelineSnapshot(tuple((s, StepStatus.COMPLETE) for s in STEPS[::-1]))

    def test_untyped_status_rejected(self):
        with self.assertRaises(TypeError):
            PipelineSnapshot(tuple((s, "COMPLETE") for s in STEPS))

    def test_seven_of_eight_never_full(self):
        values = tuple((s, StepStatus.COMPLETE if i < 7 else StepStatus.BLOCKED)
                       for i, s in enumerate(STEPS))
        self.assertFalse(can_publish_full_analysis(PipelineSnapshot(values)))

    def test_all_complete_only_necessary_not_trade_permission(self):
        values = tuple((s, StepStatus.COMPLETE) for s in STEPS)
        self.assertTrue(can_publish_full_analysis(PipelineSnapshot(values)))

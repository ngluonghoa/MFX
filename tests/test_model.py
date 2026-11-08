import unittest
from forex_trading.model import Direction, Horizon, SignalDisplay, SignalStage, ZonePurpose


class SignalDisplayTests(unittest.TestCase):
    def test_four_display_states(self):
        self.assertEqual(
            [SignalStage.WAIT_EARLY.value, SignalStage.WAIT.value,
             SignalStage.EARLY_SIGNAL.value, SignalStage.CONFIRMED_SIGNAL.value],
            ["WAIT_EARLY", "WAIT", "EARLY_SIGNAL", "CONFIRMED_SIGNAL"],
        )

    def test_early_requires_verified_source(self):
        with self.assertRaises(ValueError):
            SignalDisplay(Direction.LONG, Horizon.FAST, SignalStage.EARLY_SIGNAL,
                          "B2", False, "synthetic")

    def test_confirmed_requires_zone(self):
        with self.assertRaises(ValueError):
            SignalDisplay(Direction.SHORT, Horizon.SWING, SignalStage.CONFIRMED_SIGNAL,
                          None, True, "synthetic")

    def test_unsupported_stage_type(self):
        with self.assertRaises(TypeError):
            SignalDisplay(Direction.LONG, Horizon.FAST, "CONFIRMED_SIGNAL",
                          "B2", True, "synthetic")

    def test_no_trade_reports_reason(self):
        report = SignalDisplay(Direction.LONG, Horizon.SWING, SignalStage.NO_TRADE,
                               None, False, "Missing source entitlement")
        self.assertEqual(report.stage, SignalStage.NO_TRADE)

    def test_missing_reason_rejected(self):
        with self.assertRaises(ValueError):
            SignalDisplay(Direction.LONG, Horizon.SWING, SignalStage.NO_TRADE,
                          None, False, "")

    def test_s3_s8_not_actionable_purpose(self):
        self.assertNotEqual(ZonePurpose.EXIT_LONG_WARNING_ONLY,
                            ZonePurpose.ENTRY_SHORT_CANDIDATE)

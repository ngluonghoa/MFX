"""P249 shared research assumptions and exact profile integrity."""
from datetime import timedelta
from decimal import Decimal as D
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from forex_trading.market_data import Timeframe
from mfx_research.p249_b2s2_sim_profile import CONFIG, read_shared_sim_profile


class P249Tests(TestCase):
    def test_shared_policies_use_exact_price_units(self):
        p = read_shared_sim_profile()
        self.assertEqual(p.structural.stop_frame, Timeframe.H1)
        self.assertEqual(p.structural.stop_buffer, D("0.0001"))
        self.assertEqual(p.structural.target_buffer, D("0.00005"))
        self.assertEqual(p.structural.mid_exit_offset, D("0.00005"))
        self.assertEqual(p.structural.min_net_r, D("1.5"))
        self.assertEqual(p.monitoring.invalidation.frames, (Timeframe.H1, Timeframe.H4))
        self.assertEqual(p.monitoring.invalidation.buffer, D("0.00005"))
        self.assertEqual(p.monitoring.expiry_m15_slots, 4)
        self.assertEqual(p.max_quote_age, timedelta(seconds=30))

    def test_fingerprint_deterministic(self):
        a, b = read_shared_sim_profile(), read_shared_sim_profile()
        self.assertEqual(a, b)
        self.assertRegex(a.fingerprint, r"^[a-f0-9]{64}$")

    def test_exact_schema_rejects_scope_or_numeric_mutation(self):
        for key, value in (("may_publish_buy_sell", True),
                           ("real_market_data_allowed", True),
                           ("source_numeric_approved", 0),
                           ("rules", ["B2"]), ("expiry_m15_slots", True),
                           ("minimum_net_r", "0.1"), ("stop_buffer_pips", 1)):
            with self.subTest(key=key), TemporaryDirectory() as d:
                data = json.loads(CONFIG.read_text())
                data[key] = value
                path = Path(d) / "profile.json"
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    read_shared_sim_profile(path)

    def test_duplicate_keys_rejected(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "profile.json"
            path.write_text('{"schema":"x","schema":"x"}')
            with self.assertRaisesRegex(ValueError, "DUPLICATE"):
                read_shared_sim_profile(path)

    def test_unknown_key_rejected(self):
        with TemporaryDirectory() as d:
            data = json.loads(CONFIG.read_text())
            data["approval"] = True
            path = Path(d) / "profile.json"
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                read_shared_sim_profile(path)

    def test_no_source_promotion(self):
        s = read_shared_sim_profile().public_summary()
        self.assertEqual(s["action"], "NO_SIGNAL")
        self.assertEqual(s["original_numeric_approvals"], 0)
        self.assertEqual(s["existing_entry_pairs"] + s["additional_sim_policy_pairs"]
                         + s["remaining_external_or_method_pairs"], 18)
        for key in ("calibrated", "real_market_data_allowed", "may_trade",
                    "may_publish_buy_sell", "historical_oos_qualified"):
            self.assertIs(s[key], False)

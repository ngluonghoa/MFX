"""P0.21 mutation and approval-forgery resistance for B2/S2 review contract."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from forex_trading.model import SignalStage
from mfx_research.source_parameter_review import (
    BLOCKING_COUNT, DOCUMENT_ID, REQUIREMENTS, SCHEMA, VERSION,
    read_review_register, verify_parameter_review_register,
)


SOURCE = Path("docs/MFX_A04_P21_SOURCE_PARAMETER_REGISTER.json")


def fixture() -> dict[str, object]:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("P021_TEST_EXPECTS_OBJECT")
    return data


def rule(data: dict[str, object], index: int = 0) -> dict[str, object]:
    rules = data["rules"]
    assert isinstance(rules, list)
    item = rules[index]
    assert isinstance(item, dict)
    return item


def field(data: dict[str, object], rule_index: int, field_index: int) -> dict[str, object]:
    rows = rule(data, rule_index)["requirements"]
    assert isinstance(rows, list)
    row = rows[field_index]
    assert isinstance(row, dict)
    return row


class SourceParameterRegistryTests(unittest.TestCase):
    def test_complete_source_review_registry_but_none_approved(self) -> None:
        r = verify_parameter_review_register(fixture())
        self.assertEqual(r.rule_ids, ("B2", "S2"))
        self.assertEqual(r.expected_requirement_count, BLOCKING_COUNT)
        self.assertEqual(r.pending_source_numerical_approvals, 36)
        self.assertEqual(r.simulated_research_examples, 14)
        self.assertTrue(r.register_complete_for_review)
        self.assertIs(r.stage, SignalStage.UNVERIFIED)
        self.assertEqual(r.source_numeric_rules_approved, 0)
        self.assertFalse(r.original_forex_1to1_numerical_parity)
        self.assertFalse(r.may_send_confirmed_buy_sell_signal)

    def test_deterministic_sha_only_integrity_not_signature(self) -> None:
        a, h1 = read_review_register(SOURCE)
        b, h2 = read_review_register(SOURCE)
        self.assertEqual(a, b)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)
        self.assertFalse(a.authenticated_approval_evidence)

    def test_missing_rule_denied(self) -> None:
        x=fixture()
        rows=x["rules"]
        assert isinstance(rows,list)
        rows.pop()
        with self.assertRaisesRegex(ValueError, "EXACT_B2_S2"):
            verify_parameter_review_register(x)

    def test_reversed_b2_s2_denied(self) -> None:
        x=fixture()
        rows=x["rules"]
        assert isinstance(rows,list)
        rows.reverse()
        with self.assertRaisesRegex(ValueError, "VALUE_NOT_APPROVED"):
            verify_parameter_review_register(x)

    def test_scope_short_cannot_be_long(self) -> None:
        x=fixture()
        rule(x,1)["direction"]="LONG"
        with self.assertRaisesRegex(ValueError, "VALUE_NOT_APPROVED"):
            verify_parameter_review_register(x)

    def test_source_id_not_replaceable(self) -> None:
        x=fixture()
        source=x["source"]
        assert isinstance(source,dict)
        source["document_id"]="FORGED"
        with self.assertRaisesRegex(ValueError, "source.document_id"):
            verify_parameter_review_register(x)

    def test_source_status_cannot_change_to_approved(self) -> None:
        x=fixture()
        src=x["source"]
        assert isinstance(src,dict)
        src["approved_numerical_strategy"]=True
        with self.assertRaisesRegex(ValueError, "approved_numerical"):
            verify_parameter_review_register(x)

    def test_numeric_parameter_without_source_evidence_denied(self) -> None:
        x=fixture()
        field(x,0,1)["approved_value"]="1"
        with self.assertRaisesRegex(ValueError, "approved_value"):
            verify_parameter_review_register(x)

    def test_sim_example_does_not_accept_forged_approval_prefix(self) -> None:
        x=fixture()
        field(x,0,2)["research_sim_example"]="APPROVED:1"
        with self.assertRaisesRegex(ValueError, "RESEARCH_NUMBER"):
            verify_parameter_review_register(x)

    def test_sim_example_cannot_be_injected_as_float(self) -> None:
        x=fixture()
        field(x,0,2)["research_sim_example"]=1.0
        with self.assertRaisesRegex(ValueError, "RESEARCH_NUMBER"):
            verify_parameter_review_register(x)

    def test_fake_independent_evidence_is_not_self_signed(self) -> None:
        x=fixture()
        field(x,0,1)["independently_verified_evidence"]="https://example.test/fake"
        with self.assertRaisesRegex(ValueError, "independently_verified"):
            verify_parameter_review_register(x)

    def test_fake_per_rule_status_denied(self) -> None:
        x=fixture()
        rule(x)["approval_status"]="APPROVED"
        with self.assertRaisesRegex(ValueError, "approval_status"):
            verify_parameter_review_register(x)

    def test_fake_field_calibration_status_denied(self) -> None:
        x=fixture()
        field(x,1,3)["source_numeric_status"]="CALIBRATION_PASS"
        with self.assertRaisesRegex(ValueError, "source_numeric_status"):
            verify_parameter_review_register(x)

    def test_catalog_not_extended_with_unapproved_fx_b9(self) -> None:
        x=fixture()
        rule(x,1)["rule_id"]="FX-B9"
        with self.assertRaisesRegex(ValueError, "rule_id"):
            verify_parameter_review_register(x)

    def test_missing_requirement_denied(self) -> None:
        x=fixture()
        rows=rule(x)["requirements"]
        assert isinstance(rows,list)
        rows.pop()
        with self.assertRaisesRegex(ValueError, "MISSING_OR_DUPLICATE"):
            verify_parameter_review_register(x)

    def test_duplicate_requirement_denied(self) -> None:
        x=fixture()
        rows=rule(x)["requirements"]
        assert isinstance(rows,list)
        rows[3]=deepcopy(rows[2])
        with self.assertRaisesRegex(ValueError, "VALUE_NOT_APPROVED"):
            verify_parameter_review_register(x)

    def test_source_lineage_off_by_one_denied(self) -> None:
        x=fixture()
        field(x,0,1)["source_paragraph_index"]=30
        with self.assertRaisesRegex(ValueError, "source_paragraph_index"):
            verify_parameter_review_register(x)

    def test_wrong_phase_denied(self) -> None:
        x=fixture()
        field(x,1,5)["phase"]="R_F"
        with self.assertRaisesRegex(ValueError, "phase"):
            verify_parameter_review_register(x)

    def test_unauthorized_trade_permission_flag_denied(self) -> None:
        x=fixture()
        p=x["permissions"]
        assert isinstance(p,dict)
        p["broker_order_execution"]=True
        with self.assertRaisesRegex(ValueError, "broker_order_execution"):
            verify_parameter_review_register(x)

    def test_unauthorized_alert_permission_flag_denied(self) -> None:
        x=fixture()
        p=x["permissions"]
        assert isinstance(p,dict)
        p["confirmed_buy_sell_alerts"]=True
        with self.assertRaisesRegex(ValueError, "confirmed_buy_sell_alerts"):
            verify_parameter_review_register(x)

    def test_unauthorized_drive_price_cache_denied(self) -> None:
        x=fixture()
        p=x["permissions"]
        assert isinstance(p,dict)
        p["drive_price_cache"]=True
        with self.assertRaisesRegex(ValueError, "drive_price_cache"):
            verify_parameter_review_register(x)

    def test_unauthorized_real_provider_denied(self) -> None:
        x=fixture()
        p=x["permissions"]
        assert isinstance(p,dict)
        p["real_market_data"]=True
        with self.assertRaisesRegex(ValueError, "real_market_data"):
            verify_parameter_review_register(x)

    def test_unauthorized_release_denied(self) -> None:
        x=fixture()
        p=x["permissions"]
        assert isinstance(p,dict)
        p["release_ready"]=True
        with self.assertRaisesRegex(ValueError, "release_ready"):
            verify_parameter_review_register(x)

    def test_unknown_extension_fields_denied(self) -> None:
        x=fixture()
        x["extra"]="silent_production_switch"
        with self.assertRaisesRegex(ValueError, "EXACT_SCHEMA_KEYS"):
            verify_parameter_review_register(x)

    def test_boolean_source_paragraph_not_int(self) -> None:
        x=fixture()
        field(x,0,3)["source_paragraph_index"]=True
        with self.assertRaisesRegex(ValueError, "source_paragraph_index"):
            verify_parameter_review_register(x)

    def test_empty_input_denied(self) -> None:
        with self.assertRaisesRegex(ValueError, "EXPECTED_MAPPING"):
            verify_parameter_review_register(None)

    def test_duplicate_json_object_keys_denied(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            f=Path(folder)/"duplicate.json"
            f.write_text('{"schema":"A","schema":"B"}',encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_KEY"):
                read_review_register(f)

    def test_unbounded_registry_denied(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            f=Path(folder)/"oversize.json"
            f.write_bytes(b"x"*131073)
            with self.assertRaisesRegex(ValueError, "OVERSIZED"):
                read_review_register(f)

    def test_exact_expected_qualitative_field_count(self) -> None:
        self.assertEqual(len(REQUIREMENTS),18)
        self.assertEqual(BLOCKING_COUNT,36)
        self.assertEqual(len({row[0] for row in REQUIREMENTS}),18)

    def test_version_and_reference_are_pinned(self) -> None:
        self.assertEqual(SCHEMA,"MFX_A04_P21_SOURCE_PARAMETER_REVIEW_V1")
        self.assertEqual(VERSION,"SIM:P021-RESEARCH-REVIEW-001")
        self.assertEqual(DOCUMENT_ID,"10-XQxdssBTanOyTX7tSqAymRfS8XRO9YRKtjk_BsXmA")

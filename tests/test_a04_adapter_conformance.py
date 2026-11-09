"""A04/P0.2 synthetic ABI port graph and frozen-golden differential guards."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import unittest

from tools.a04_adapter_conformance import (
    AdapterPort, PortSchema, PORT_SIGNATURE, synthetic_reference_graph,
    validate_declared_adapter_graph,
)
from tools.a04_plugin_contracts import PluginKind, PluginManifest, PluginRegistry
from tools.check_a04_adapter_golden import (
    assess_adapter_golden, verify_pinned_adapter_golden,
)
from test_golden_contracts import sample


def golden50() -> dict:
    """Extend a comparator-only synthetic fixture to the frozen 50-case count."""
    data = sample()
    for index in range(10):
        data["scenarios"].append({
            "id": f"catalog.additional_contract_{index}",
            "outcome": {"value": {"read_only": True, "index": index}},
        })
    data["scenario_count"] = 50
    return data


class A04AdapterP02ContractTests(unittest.TestCase):
    def test_exact_four_roles_are_declared_without_invocation(self) -> None:
        registry, ports = synthetic_reference_graph()
        report = validate_declared_adapter_graph(registry, ports)
        self.assertTrue(report.declared_schema_compatible)
        self.assertEqual(report.port_count, 4)
        self.assertEqual(len(report.graph_sha256), 64)
        self.assertFalse(report.any_plugin_executed)
        self.assertFalse(report.implementation_sha_verified)
        self.assertFalse(report.may_ingest_real_data)
        self.assertFalse(report.may_deploy_or_trade)

    def test_registry_and_port_order_do_not_change_graph_identity(self) -> None:
        registry, ports = synthetic_reference_graph()
        reverse = PluginRegistry(tuple(reversed(registry.manifests)))
        a = validate_declared_adapter_graph(registry, ports)
        b = validate_declared_adapter_graph(reverse, tuple(reversed(ports)))
        self.assertEqual(a.graph_sha256, b.graph_sha256)

    def test_port_schema_names_are_closed_and_no_executable_output(self) -> None:
        self.assertEqual(len(PortSchema), 5)
        self.assertEqual(set(PORT_SIGNATURE), set(PluginKind))
        self.assertFalse(any("ORDER" in s.value or "FILL" in s.value for s in PortSchema))

    def test_wrong_input_schema_is_rejected_at_declaration(self) -> None:
        registry, ports = synthetic_reference_graph()
        p = next(p for p in ports if p.manifest.kind is PluginKind.INDICATOR)
        with self.assertRaisesRegex(ValueError, "A04P2_PORT_SCHEMA_KIND_MISMATCH"):
            replace(p, input_schema=PortSchema.FEATURES_UNVERIFIED_V1)

    def test_malformed_port_cannot_claim_runtime_invocation(self) -> None:
        _, ports = synthetic_reference_graph()
        with self.assertRaisesRegex(ValueError, "A04P2_NO_RUNTIME_INVOCATION"):
            replace(ports[0], may_invoke=True)

    def test_missing_port_and_extra_port_fail_closed(self) -> None:
        registry, ports = synthetic_reference_graph()
        with self.assertRaisesRegex(ValueError, "A04P2_REGISTRY_PORT_SET_MISMATCH"):
            validate_declared_adapter_graph(registry, ports[:-1])
        with self.assertRaisesRegex(ValueError, "A04P2_DUPLICATE_PORT_ID"):
            validate_declared_adapter_graph(registry, ports + (ports[0],))

    def test_abi_major_mismatch_fails_even_when_plugin_registry_valid(self) -> None:
        registry, ports = synthetic_reference_graph()
        changed = tuple(
            replace(p.manifest, abi_major=2) if p.manifest.kind is PluginKind.PROVIDER
            else p.manifest for p in ports
        )
        updated = PluginRegistry(changed)
        newports = tuple(AdapterPort(m, *PORT_SIGNATURE[m.kind]) for m in changed)
        with self.assertRaisesRegex(ValueError, "A04P2_ABI_MAJOR_UNSUPPORTED"):
            validate_declared_adapter_graph(updated, newports)

    def test_wrong_dependency_kind_cannot_be_silently_accepted(self) -> None:
        registry, ports = synthetic_reference_graph()
        by_kind = {p.manifest.kind: p.manifest for p in ports}
        modified = tuple(
            replace(m, dependency_ids=(by_kind[PluginKind.PROVIDER].plugin_id,))
            if m.kind is PluginKind.DETECTOR else m
            for m in registry.manifests
        )
        changed_reg = PluginRegistry(modified)
        changed_ports = tuple(AdapterPort(m, *PORT_SIGNATURE[m.kind]) for m in modified)
        with self.assertRaisesRegex(ValueError, "A04P2_UPSTREAM_PLUGIN_KIND_MISMATCH"):
            validate_declared_adapter_graph(changed_reg, changed_ports)

    def test_provider_must_not_consume_other_plugins(self) -> None:
        _, ports = synthetic_reference_graph()
        m = next(p.manifest for p in ports if p.manifest.kind is PluginKind.PROVIDER)
        other = PluginManifest("synthetic.another", PluginKind.DETECTOR, 1, "0.1.0", "f"*64)
        wrong = replace(m, dependency_ids=(other.plugin_id,))
        # The registry is valid, but a provider must be the graph root.
        reg = PluginRegistry((wrong, other))
        p = tuple(AdapterPort(x, *PORT_SIGNATURE[x.kind]) for x in (wrong, other))
        with self.assertRaisesRegex(ValueError, "A04P2_EXPECT_EXACT_FOUR_DECLARATIONS"):
            validate_declared_adapter_graph(reg, p)

    def test_untyped_port_set_rejected(self) -> None:
        registry, _ = synthetic_reference_graph()
        with self.assertRaisesRegex(TypeError, "A04P2_IMMUTABLE_TYPED_PORTS_REQUIRED"):
            validate_declared_adapter_graph(registry, [])  # type: ignore[arg-type]

    def test_golden_bridge_preserves_group_count_and_readonly_result(self) -> None:
        reference = golden50()
        got = assess_adapter_golden(reference, deepcopy(reference))
        self.assertEqual(got["synthetic_scenario_count"], 50)
        self.assertEqual(got["contract_group_count"], 8)
        self.assertTrue(got["frozen_synthetic_contracts_exact"])
        self.assertEqual(got["adapter_declared_port_count"], 4)
        self.assertFalse(got["adapter_implementation_executed"])
        self.assertFalse(got["may_deploy_or_trade"])

    def test_golden_rejects_synthetic_source_output_drift(self) -> None:
        source = sample()
        candidate = deepcopy(source)
        candidate["scenarios"][0]["outcome"]["value"]["index"] = 999
        with self.assertRaisesRegex(ValueError, "GOLDEN_OUTPUT_OR_ERROR_REASON_MISMATCH"):
            assess_adapter_golden(source, candidate)

    def test_golden_rejects_error_reason_drift(self) -> None:
        source = sample()
        source["scenarios"][0]["outcome"] = {
            "error_type": "ValueError", "reason": "REFERENCE_BAD_SIDE",
        }
        candidate = deepcopy(source)
        candidate["scenarios"][0]["outcome"]["reason"] = "NOW_ACCEPTED"
        with self.assertRaisesRegex(ValueError, "GOLDEN_OUTPUT_OR_ERROR_REASON_MISMATCH"):
            assess_adapter_golden(source, candidate)

    def test_golden_rejects_unsafe_authority_claim(self) -> None:
        source = sample()
        source["may_trade"] = True
        with self.assertRaisesRegex(ValueError, "GOLDEN_SNAPSHOT_UNSAFE_AUTHORITY_FLAG"):
            assess_adapter_golden(source, deepcopy(source))

    def test_golden_rejects_less_than_original_50_scenarios(self) -> None:
        source = sample()
        with self.assertRaisesRegex(ValueError, "A04P2_EXPECT_FROZEN_50"):
            assess_adapter_golden(source, deepcopy(source))

    def test_golden_group_pin_rejects_tampered_group_sha(self) -> None:
        source = golden50()
        report = assess_adapter_golden(source, deepcopy(source))
        measured_keys = (
            "synthetic_scenario_count", "contract_group_count",
            "contract_groups", "adapter_graph_sha256",
            "adapter_declared_port_count", "frozen_golden_sha256",
        )
        base = {
            "schema_version": 1,
            "kind": "MFX_A04_P02_PINNED_SYNTHETIC_GOLDEN_GROUP_BASELINE",
            "frozen_forex_source_commit": report["source_commit"],
            "measured": {k: deepcopy(report[k]) for k in measured_keys},
            "expected_false_flags": [
                "adapter_implementation_executed",
                "detector_or_tp_execution_tested", "licensed_real_data_used",
                "may_cache_real_data", "may_deploy_or_trade",
            ],
        }
        verify_pinned_adapter_golden(report, base)
        base["measured"]["contract_groups"]["quote"]["source_and_candidate_sha256"] = "f"*64
        with self.assertRaisesRegex(ValueError, "A04P2_PINNED_GOLDEN_DRIFT"):
            verify_pinned_adapter_golden(report, base)

    def test_pinned_golden_scope_cannot_promote_execution(self) -> None:
        source = golden50()
        report = assess_adapter_golden(source, deepcopy(source))
        base = {
            "schema_version": 1,
            "kind": "MFX_A04_P02_PINNED_SYNTHETIC_GOLDEN_GROUP_BASELINE",
            "frozen_forex_source_commit": report["source_commit"],
            "measured": {
                k: deepcopy(report[k]) for k in (
                    "synthetic_scenario_count", "contract_group_count",
                    "contract_groups", "adapter_graph_sha256",
                    "adapter_declared_port_count", "frozen_golden_sha256",
                )
            },
            "expected_false_flags": [
                "adapter_implementation_executed",
                "detector_or_tp_execution_tested", "licensed_real_data_used",
                "may_cache_real_data", "may_deploy_or_trade",
            ],
        }
        altered = dict(report, adapter_implementation_executed=True)
        with self.assertRaisesRegex(ValueError, "A04P2_UNAUTHORIZED_SCOPE"):
            verify_pinned_adapter_golden(altered, base)

    def test_claimed_implementation_hash_does_not_verify_code(self) -> None:
        registry, ports = synthetic_reference_graph()
        variant = tuple(
            replace(p.manifest, implementation_sha256_claim="f"*64)
            if p.manifest.kind is PluginKind.PROVIDER else p.manifest
            for p in ports
        )
        reg2 = PluginRegistry(variant)
        ports2 = tuple(AdapterPort(m, *PORT_SIGNATURE[m.kind]) for m in variant)
        first = validate_declared_adapter_graph(registry, ports)
        other = validate_declared_adapter_graph(reg2, ports2)
        self.assertNotEqual(first.graph_sha256, other.graph_sha256)
        self.assertFalse(other.implementation_sha_verified)


if __name__ == "__main__":
    unittest.main()

"""A04/P0.1 fail-closed plugin registry and provider declaration contracts."""
from __future__ import annotations

from dataclasses import replace
import unittest

from forex_trading.market_data import BarSide, Timeframe
from tools.a04_plugin_contracts import (
    DeclaredPluginResolution, PluginKind, PluginManifest, PluginRegistry,
    PriceBasis, ProbePurpose, ProviderCapability, ProviderProbe,
    assess_declared_provider, resolve_declared_plugin,
)


def plugin(
    name: str, kind: PluginKind = PluginKind.PROVIDER,
    deps: tuple[str, ...] = (),
    abi: int = 1,
) -> PluginManifest:
    return PluginManifest(
        name, kind, abi, "0.1.0", "a" * 64, dependency_ids=deps,
    )


def capability(
    manifest: PluginManifest | None = None,
    **overrides: object,
) -> ProviderCapability:
    values: dict[str, object] = dict(
        manifest=manifest or plugin("synthetic.provider"),
        provider_id="synthetic.source", product_ref="synthetic.product",
        instrument_version="synthetic.EURUSD.v1",
        supported_timeframes=frozenset((Timeframe.M5, Timeframe.M15)),
        basis=PriceBasis.REFERENCE_OHLC,
        native_sides=frozenset(),
        calendar_version="synthetic.calendar.v1",
        timezone_policy="synthetic.UTC",
        rights_policy_ref="rights.unverified",
        lineage_policy_ref="lineage.synthetic.v1",
    )
    values.update(overrides)
    return ProviderCapability(**values)  # type: ignore[arg-type]


def probe(**overrides: object) -> ProviderProbe:
    values: dict[str, object] = dict(
        provider_id="synthetic.source", product_ref="synthetic.product",
        instrument_version="synthetic.EURUSD.v1",
        timeframe=Timeframe.M5, basis=PriceBasis.REFERENCE_OHLC,
        quote_side=None, calendar_version="synthetic.calendar.v1",
        timezone_policy="synthetic.UTC",
        rights_policy_ref="rights.unverified",
    )
    values.update(overrides)
    return ProviderProbe(**values)  # type: ignore[arg-type]


class A04PluginDeclarationTests(unittest.TestCase):
    def test_all_four_plugin_kinds_have_stable_inert_manifests(self) -> None:
        kinds = tuple(PluginKind)
        self.assertEqual(
            set(kinds), {PluginKind.PROVIDER, PluginKind.DETECTOR,
                         PluginKind.INDICATOR, PluginKind.TP_POLICY},
        )
        items = tuple(
            plugin("synthetic." + k.value.lower(), k) for k in kinds
        )
        registry = PluginRegistry(items)
        reversed_registry = PluginRegistry(tuple(reversed(items)))
        self.assertEqual(registry.identity_sha256, reversed_registry.identity_sha256)
        self.assertEqual(len(registry.identity_sha256), 64)
        for item in items:
            self.assertFalse(item.may_activate)

    def test_exact_plugin_resolve_cannot_load_or_activate_code(self) -> None:
        p = plugin("synthetic.provider")
        got = resolve_declared_plugin(
            PluginRegistry((p,)), p.plugin_id, PluginKind.PROVIDER, 1,
        )
        self.assertEqual(got, DeclaredPluginResolution(
            True, "synthetic.provider", "A04_METADATA_ONLY_NO_ACTIVATION",
        ))
        self.assertFalse(got.may_load_code)
        self.assertFalse(got.may_activate)

    def test_unknown_plugin_not_silently_replaced_with_fallback(self) -> None:
        reg = PluginRegistry((plugin("synthetic.provider"),))
        got = resolve_declared_plugin(
            reg, "synthetic.other", PluginKind.PROVIDER, 1,
        )
        self.assertFalse(got.declared_abi_compatible)
        self.assertEqual(got.reason, "A04_PLUGIN_NOT_DECLARED_NO_FALLBACK")
        self.assertIsNone(got.plugin_id)

    def test_plugin_kind_and_abi_must_match_exactly(self) -> None:
        reg = PluginRegistry((plugin("synthetic.provider"),))
        a = resolve_declared_plugin(
            reg, "synthetic.provider", PluginKind.DETECTOR, 1,
        )
        b = resolve_declared_plugin(
            reg, "synthetic.provider", PluginKind.PROVIDER, 2,
        )
        self.assertEqual(a.reason, "A04_PLUGIN_KIND_MISMATCH")
        self.assertEqual(b.reason, "A04_PLUGIN_ABI_MISMATCH")

    def test_registry_dependency_graph_is_valid_independent_of_input_order(self) -> None:
        p = plugin("synthetic.provider")
        i = plugin("synthetic.indicator", PluginKind.INDICATOR,
                   (p.plugin_id,))
        d = plugin("synthetic.detector", PluginKind.DETECTOR,
                   (i.plugin_id,))
        t = plugin("synthetic.tp_policy", PluginKind.TP_POLICY,
                   (d.plugin_id,))
        a = PluginRegistry((t, p, d, i))
        b = PluginRegistry((p, i, d, t))
        self.assertEqual(a.identity_sha256, b.identity_sha256)

    def test_registry_rejects_unknown_duplicate_and_cycle(self) -> None:
        p = plugin("synthetic.provider")
        with self.assertRaisesRegex(ValueError, "A04_DUPLICATE_PLUGIN_ID"):
            PluginRegistry((p, p))
        with self.assertRaisesRegex(ValueError, "A04_UNKNOWN_PLUGIN_DEPENDENCY"):
            PluginRegistry((plugin("synthetic.x", deps=("synthetic.missing",)),))
        with self.assertRaisesRegex(ValueError, "A04_PLUGIN_DEPENDENCY_CYCLE"):
            PluginRegistry((
                plugin("synthetic.one", deps=("synthetic.two",)),
                plugin("synthetic.two", deps=("synthetic.one",)),
            ))
        with self.assertRaisesRegex(ValueError, "A04_SELF_OR_DUPLICATE_DEPENDENCY"):
            plugin("synthetic.self", deps=("synthetic.self",))

    def test_wrong_project_identifier_and_activation_claim_rejected(self) -> None:
        p = plugin("synthetic.provider")
        with self.assertRaisesRegex(ValueError, "A04_CROSS_PROJECT"):
            replace(p, project_id="FOREX_TRADING")
        with self.assertRaisesRegex(ValueError, "A04_NO_RUNTIME_ACTIVATION"):
            replace(p, may_activate=True)
        with self.assertRaisesRegex(ValueError, "A04_INVALID_DECLARED_SHA256"):
            replace(p, implementation_sha256_claim="not-a-hash")

    def test_typed_immutable_registry_required(self) -> None:
        with self.assertRaisesRegex(TypeError, "A04_TYPED_IMMUTABLE"):
            PluginRegistry([])  # type: ignore[arg-type]
        with self.assertRaisesRegex(TypeError, "A04_TYPED_IMMUTABLE"):
            PluginRegistry(("synthetic",))  # type: ignore[arg-type]
        with self.assertRaisesRegex(TypeError, "A04_TYPED_REGISTRY_REQUIRED"):
            resolve_declared_plugin(
                "bad", "synthetic.provider", PluginKind.PROVIDER, 1,
            )  # type: ignore[arg-type]

    def test_reference_ohlc_is_not_a_native_bid_ask_or_mid_quote(self) -> None:
        cap = capability()
        self.assertEqual(cap.native_sides, frozenset())
        with self.assertRaisesRegex(ValueError, "A04_REFERENCE_OHLC_NOT_BROKER_SIDE"):
            capability(native_sides=frozenset((BarSide.MID,)))
        with self.assertRaisesRegex(ValueError, "A04_REFERENCE_PROBE_MUST_HAVE_NO_BROKER_SIDE"):
            probe(quote_side=BarSide.MID)

    def test_native_bid_ask_claim_requires_two_sides_not_mid(self) -> None:
        with self.assertRaisesRegex(ValueError, "A04_NATIVE_PAIR_REQUIRES_BOTH"):
            capability(basis=PriceBasis.NATIVE_BID_ASK,
                       native_sides=frozenset((BarSide.BID,)))
        with self.assertRaisesRegex(ValueError, "A04_NATIVE_PROBE_NEEDS_BID_OR_ASK"):
            probe(basis=PriceBasis.NATIVE_BID_ASK, quote_side=None)

    def test_structurally_matching_provider_has_zero_real_data_authority(self) -> None:
        cap = capability()
        reg = PluginRegistry((cap.manifest,))
        found = assess_declared_provider(reg, (cap,), cap.manifest.plugin_id, probe())
        self.assertTrue(found.declared_structure_compatible)
        self.assertEqual(found.selected_plugin_id, cap.manifest.plugin_id)
        self.assertFalse(found.rights_independently_verified)
        self.assertFalse(found.may_fetch_real_data)
        self.assertFalse(found.may_cache_real_data)
        self.assertFalse(found.may_run_real_backtest)
        self.assertFalse(found.may_trade)
        self.assertEqual(found.reason, "A04_DECLARED_SHAPE_ONLY_EXTERNAL_RIGHTS_UNVERIFIED")

    def test_unapproved_capability_can_never_self_grant_real_network_or_cache(self) -> None:
        with self.assertRaisesRegex(ValueError, "A04_NO_REAL_IO_OR_STORAGE_AUTHORITY"):
            capability(may_fetch_real_data=True)
        with self.assertRaisesRegex(ValueError, "A04_NO_REAL_IO_OR_STORAGE_AUTHORITY"):
            capability(may_store_real_data=True)

    def test_unsupported_timeframe_and_cross_provider_fail_closed(self) -> None:
        cap = capability()
        reg = PluginRegistry((cap.manifest,))
        wrong_tf = assess_declared_provider(
            reg, (cap,), cap.manifest.plugin_id, probe(timeframe=Timeframe.H4),
        )
        wrong_source = assess_declared_provider(
            reg, (cap,), cap.manifest.plugin_id,
            probe(provider_id="another.vendor"),
        )
        self.assertEqual(wrong_tf.reason, "A04_UNSUPPORTED_TIMEFRAME")
        self.assertEqual(wrong_source.reason, "A04_PROVIDER_PRODUCT_OR_SYMBOL_MISMATCH")
        self.assertIsNone(wrong_source.selected_plugin_id)

    def test_calendar_timezone_rights_and_price_basis_never_silently_coerce(self) -> None:
        cap = capability()
        reg = PluginRegistry((cap.manifest,))
        for field in ("calendar_version", "timezone_policy", "rights_policy_ref"):
            with self.subTest(field=field):
                p = probe(**{field:"another.policy"})
                r = assess_declared_provider(
                    reg, (cap,), cap.manifest.plugin_id, p,
                )
                self.assertEqual(r.reason, "A04_CALENDAR_TIMEZONE_OR_RIGHTS_DRIFT")
        with self.assertRaisesRegex(ValueError, "A04_NATIVE_PROBE_NEEDS_BID_OR_ASK"):
            probe(basis=PriceBasis.NATIVE_BID_ASK)

    def test_execution_replay_is_never_promoted_by_reference_ohlc(self) -> None:
        cap = capability()
        reg = PluginRegistry((cap.manifest,))
        r = assess_declared_provider(
            reg, (cap,), cap.manifest.plugin_id,
            probe(purpose=ProbePurpose.EXECUTION_REPLAY),
        )
        self.assertEqual(r.reason, "A04_EXECUTION_BASIS_UNVERIFIED")
        self.assertFalse(r.declared_structure_compatible)
        self.assertFalse(r.may_trade)

    def test_duplicate_capability_or_wrong_registry_selection_fails_closed(self) -> None:
        cap = capability()
        reg = PluginRegistry((cap.manifest,))
        a = assess_declared_provider(
            reg, (cap, cap), cap.manifest.plugin_id, probe(),
        )
        b = assess_declared_provider(
            reg, (), cap.manifest.plugin_id, probe(),
        )
        self.assertEqual(a.reason, "A04_PROVIDER_CAPABILITY_AMBIGUOUS")
        self.assertEqual(b.reason, "A04_PROVIDER_CAPABILITY_MISSING")
        self.assertFalse(a.may_fetch_real_data)
        self.assertFalse(b.may_trade)

    def test_registry_digests_change_for_declared_abi_or_implementation_sha(self) -> None:
        p = plugin("synthetic.provider")
        newer = replace(p, abi_major=2)
        revised = replace(p, implementation_sha256_claim="b"*64)
        self.assertNotEqual(
            PluginRegistry((p,)).identity_sha256,
            PluginRegistry((newer,)).identity_sha256,
        )
        self.assertNotEqual(
            PluginRegistry((p,)).identity_sha256,
            PluginRegistry((revised,)).identity_sha256,
        )


if __name__ == "__main__":
    unittest.main()

"""A04/P0.8 exact source reference seam gates: documentation only."""
from __future__ import annotations

from dataclasses import replace
import unittest

from tools.a04_adapter_conformance import PortSchema
from tools.a04_p08_seam_review import (
    ReferenceFunction, SOURCE_TO_ROLE, proposal_for, review_source_seam,
)
from tools.a04_plugin_contracts import PluginKind
from tools.check_a04_p08_seams import measure_matrix, source_pins


class A04P08AdapterSeamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pins = source_pins()

    def test_seven_readonly_existing_references_documentable_only(self) -> None:
        self.assertEqual(len(ReferenceFunction), 7)
        for ref in ReferenceFunction:
            with self.subTest(ref=ref):
                result = review_source_seam(proposal_for(ref, self.pins), self.pins)
                self.assertTrue(result.source_reference_documentable)
                self.assertFalse(result.may_construct_runtime_adapter)
                self.assertFalse(result.may_load_plugin)
                self.assertFalse(result.p02_ports_callable_compatible)
                self.assertFalse(result.may_release_or_trade)

    def test_catalog_taxonomy_is_not_numeric_detector(self) -> None:
        p = proposal_for(ReferenceFunction.CATALOG_COUNT, self.pins)
        self.assertEqual(SOURCE_TO_ROLE[p.reference], PluginKind.DETECTOR)
        r = review_source_seam(p, self.pins)
        self.assertTrue(r.source_reference_documentable)
        self.assertFalse(r.numeric_detector_verified)

    def test_unimplemented_tp_policy_reference_never_claimed(self) -> None:
        self.assertNotIn(PluginKind.TP_POLICY, set(SOURCE_TO_ROLE.values()))
        p = proposal_for(ReferenceFunction.QUOTE_INDICATIVE, self.pins)
        r = review_source_seam(replace(p, kind=PluginKind.TP_POLICY), self.pins)
        self.assertFalse(r.source_reference_documentable)

    def test_wrong_source_digest_or_ast_signature_blocks(self) -> None:
        p = proposal_for(ReferenceFunction.EMA_FULL, self.pins)
        for bad in (replace(p, source_file_sha256="0"*64),
                    replace(p, ast_signature_sha256="0"*64),
                    replace(p, p07_wrapper_case_sha256="0"*64)):
            with self.subTest(bad=bad):
                self.assertFalse(
                    review_source_seam(bad, self.pins).source_reference_documentable,
                )

    def test_future_port_output_does_not_prove_callable_compatibility(self) -> None:
        p = proposal_for(ReferenceFunction.EMA_DIRTY, self.pins)
        r = review_source_seam(p, self.pins)
        self.assertFalse(r.p02_ports_callable_compatible)
        other = replace(p, target_output_schema=PortSchema.CANDIDATES_UNVERIFIED_V1)
        self.assertFalse(review_source_seam(other, self.pins).source_reference_documentable)

    def test_live_feed_cache_release_broker_requests_are_refused(self) -> None:
        p = proposal_for(ReferenceFunction.QUOTE_INDICATIVE, self.pins)
        for change in ("request_runtime_bind", "request_real_feed",
                       "request_write_cache", "request_trade",
                       "request_schema_fallback", "request_release"):
            with self.subTest(change=change):
                r = review_source_seam(replace(p, **{change: True}), self.pins)
                self.assertFalse(r.source_reference_documentable)

    def test_unverified_rights_detector_tp_or_runtime_claims_block(self) -> None:
        p = proposal_for(ReferenceFunction.CATALOG_VALIDATE, self.pins)
        for change in ("licensed_data_claim", "numeric_detector_claim",
                       "tp_sl_engine_claim", "complete_1to1_runtime_claim"):
            with self.subTest(change=change):
                r = review_source_seam(replace(p, **{change: True}), self.pins)
                self.assertFalse(r.source_reference_documentable)

    def test_28_case_matrix_has_only_seven_pure_reference_reviews(self) -> None:
        m = measure_matrix()
        self.assertEqual((m["total_cases"],
                          m["source_reference_documentable_only"],
                          m["blocked"]), (28, 7, 21))
        self.assertEqual(m["working_runtime_adapter_count"], 0)
        self.assertTrue(m["no_actual_port_callable_equivalence_proven"])


if __name__ == "__main__":
    unittest.main()

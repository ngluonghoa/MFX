import unittest
from dataclasses import replace
from decimal import Decimal

from forex_trading.cache_dependency import (
    CacheArtifactFingerprint, CacheLayer, CacheNode,
    assess_artifact_reuse, dirty_dependency_closure, validate_cache_dag,
)
from forex_trading.cache_indicators import ema_full, ema_recompute


def node(name, layer, parents=(), part="EURUSD_BID_M15", alg="v1", params="v1"):
    return CacheNode(name, layer, part, alg, params, parents)


def graph():
    return (
        node("eur:l1",CacheLayer.L1_MARKET),
        node("eur:ema",CacheLayer.L2_INDICATORS,("eur:l1",)),
        node("eur:structure",CacheLayer.L3_STRUCTURE,("eur:l1","eur:ema")),
        node("eur:zones",CacheLayer.L4_SIGNALS,("eur:ema","eur:structure")),
        node("eur:audit",CacheLayer.L5_REPORT,("eur:zones",)),
        node("gbp:l1",CacheLayer.L1_MARKET,part="GBPUSD_ASK_H1"),
        node("gbp:ema",CacheLayer.L2_INDICATORS,("gbp:l1",),part="GBPUSD_ASK_H1"),
        node("gbp:zones",CacheLayer.L4_SIGNALS,("gbp:ema",),part="GBPUSD_ASK_H1"),
        node("gbp:audit",CacheLayer.L5_REPORT,("gbp:zones",),part="GBPUSD_ASK_H1"),
    )


class CacheDependencyTests(unittest.TestCase):
    def test_graph_is_valid(self):
        validate_cache_dag(graph())

    def test_eurusd_revision_never_dirties_gbpusd(self):
        dirty=dirty_dependency_closure(graph(),("eur:l1",))
        self.assertEqual(dirty,("eur:l1","eur:ema","eur:structure","eur:zones","eur:audit"))
        self.assertTrue(all(not x.startswith("gbp") for x in dirty))

    def test_rule_parameter_change_only_zone_and_report(self):
        dirty=dirty_dependency_closure(graph(),("eur:zones",))
        self.assertEqual(dirty,("eur:zones","eur:audit"))

    def test_indicator_revision_hits_downstream_not_raw_candles(self):
        dirty=dirty_dependency_closure(graph(),("eur:ema",))
        self.assertEqual(dirty,("eur:ema","eur:structure","eur:zones","eur:audit"))

    def test_report_only_change_does_not_dirty_signals(self):
        self.assertEqual(dirty_dependency_closure(graph(),("eur:audit",)),("eur:audit",))

    def test_unknown_dirty_key_rejected(self):
        with self.assertRaisesRegex(ValueError,"UNKNOWN_CHANGED_NODE"):
            dirty_dependency_closure(graph(),("eur:unknown",))

    def test_missing_dependency_rejected(self):
        with self.assertRaisesRegex(ValueError,"MISSING_DEPENDENCY"):
            validate_cache_dag((node("r",CacheLayer.L5_REPORT,("none",)),))

    def test_downward_or_same_layer_dependency_rejected(self):
        with self.assertRaisesRegex(ValueError,"INVALID_LAYER"):
            validate_cache_dag((
                node("a",CacheLayer.L4_SIGNALS,("b",)),
                node("b",CacheLayer.L4_SIGNALS),
            ))

    def test_cycle_cannot_be_hidden(self):
        with self.assertRaises(ValueError):
            validate_cache_dag((
                node("a",CacheLayer.L2_INDICATORS,("b",)),
                node("b",CacheLayer.L3_STRUCTURE,("a",)),
            ))

    def test_duplicate_node_rejected(self):
        with self.assertRaisesRegex(ValueError,"DUPLICATE_NODE_ID"):
            validate_cache_dag((node("a",CacheLayer.L1_MARKET),node("a",CacheLayer.L1_MARKET)))

    def test_cache_digest_changes_with_rule_or_indicator_version(self):
        base=node("eur:ema",CacheLayer.L2_INDICATORS,("eur:l1",))
        original=CacheArtifactFingerprint(base,"source-r1",("l1-digest",))
        changed=CacheArtifactFingerprint(replace(base,algorithm_version="ema-v2"),
                                         "source-r1",("l1-digest",))
        self.assertNotEqual(original.digest,changed.digest)

    def test_cache_digest_changes_with_source_revision(self):
        n=node("eur:ema",CacheLayer.L2_INDICATORS,("eur:l1",))
        a=CacheArtifactFingerprint(n,"source-r1",("old",))
        b=CacheArtifactFingerprint(n,"source-r1",("new",))
        self.assertNotEqual(a.digest,b.digest)

    def test_dependency_count_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError,"COUNT_MISMATCH"):
            CacheArtifactFingerprint(node("eur:ema",CacheLayer.L2_INDICATORS,("eur:l1",)),
                                     "source-r1",())

    def test_same_digest_cannot_bypass_source_revalidation(self):
        n=node("eur:l1",CacheLayer.L1_MARKET)
        a=CacheArtifactFingerprint(n,"synthetic-input",())
        g=assess_artifact_reuse(a,a,previous_complete=True,
                                source_unchanged_independently_verified=False)
        self.assertFalse(g.value_reusable)
        self.assertTrue(g.audit_stage_revalidation_required)
        self.assertFalse(g.production_authorized)

    def test_identical_verified_digest_still_needs_audit(self):
        n=node("eur:l1",CacheLayer.L1_MARKET)
        a=CacheArtifactFingerprint(n,"synthetic-input",())
        g=assess_artifact_reuse(a,a,previous_complete=True,
                                source_unchanged_independently_verified=True)
        self.assertTrue(g.value_reusable)
        self.assertTrue(g.audit_stage_revalidation_required)
        self.assertFalse(g.production_authorized)

    def test_incomplete_previous_artifact_cannot_be_reused(self):
        n=node("eur:l1",CacheLayer.L1_MARKET)
        a=CacheArtifactFingerprint(n,"synthetic-input",())
        self.assertFalse(assess_artifact_reuse(a,a,previous_complete=False,
             source_unchanged_independently_verified=True).value_reusable)


class IndicatorParityTests(unittest.TestCase):
    def test_ema_append_matches_full(self):
        prior=(Decimal("1.10"),Decimal("1.15"),Decimal("1.11"),Decimal("1.18"))
        values=prior+(Decimal("1.20"),Decimal("1.17"))
        old=ema_full(prior,period=3)
        resumed=ema_recompute(values,3,old,len(prior))
        self.assertEqual(resumed,ema_full(values,3))
        self.assertEqual(resumed[:len(prior)],old)

    def test_ema_old_revision_rewinds_recursive_tail(self):
        before=(Decimal("1.10"),Decimal("1.15"),Decimal("1.11"),Decimal("1.18"))
        after=(Decimal("1.10"),Decimal("1.16"),Decimal("1.11"),Decimal("1.18"))
        old=ema_full(before,period=3)
        replayed=ema_recompute(after,3,old,1)
        self.assertEqual(replayed,ema_full(after,3))
        self.assertNotEqual(replayed[-1],old[-1])

    def test_ema_recompute_from_beginning_when_no_checkpoint(self):
        values=(Decimal("1.1"),Decimal("1.2"),Decimal("1.3"))
        self.assertEqual(ema_recompute(values,5,(),0),ema_full(values,5))

    def test_ema_no_dirty_tail_keeps_values(self):
        values=(Decimal("1.1"),Decimal("1.2"),Decimal("1.3"))
        old=ema_full(values,3)
        self.assertEqual(ema_recompute(values,3,old,len(values)),old)

    def test_ema_invalid_checkpoint_or_period_rejected(self):
        v=(Decimal("1.1"),)
        with self.assertRaises(ValueError):
            ema_recompute(v,0,(),0)
        with self.assertRaises(ValueError):
            ema_recompute(v,3,(),1)
        with self.assertRaises(TypeError):
            ema_recompute(v,3,[],0)

    def test_ema_nan_float_and_negative_rejected(self):
        for val in (Decimal("NaN"),Decimal("-1"),1.2):
            with self.subTest(val=val),self.assertRaises(ValueError):
                ema_full((val,),3)

    def test_ema_empty_history_supported(self):
        self.assertEqual(ema_full((),3),())

    def test_no_trading_signal_is_returned_by_ema(self):
        result=ema_full((Decimal("1.1"),Decimal("1.2")),3)
        self.assertTrue(all(isinstance(x,Decimal) for x in result))

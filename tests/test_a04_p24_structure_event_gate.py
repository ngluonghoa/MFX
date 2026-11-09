"""A04/P0.24: independent synthetic structure + ephemeral event replay oracles."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import unittest

from forex_trading.market_data import (
    BarCoverage, BarLifecycle, BarSide, SourceQuality,
)
from mfx_research.confirmed_swings import (
    PivotKind, derive_swing_b2_s2_research,
)
from mfx_research.offline_ema_signals import CandidateAction
from mfx_research.p024_structure_event_gate import (
    ResearchEventStatus, SimEventKey, SimEventLedger, SimEventRecord,
    SimStructurePolicy, StructureReceipt, StructureStatus,
    buffer_sim_event, derive_sim_structure,
)
from tools.run_a04_p19_causal_context_demo import case_from_closed_bars
from tools.run_a04_p20_confirmed_swing_demo import case_confirmed, evaluate_case

EPS = Decimal("0.000000001")


def structure(rule: str, *, bars=None):
    data, pivot = case_confirmed(rule)
    data = data if bars is None else bars
    deadline = data.trigger_m15[-1].first_known_utc + timedelta(seconds=1)
    return derive_sim_structure(
        rule, data, pivot, SimStructurePolicy("SIM:P024-TEST-STRUCTURE"),
        deadline,
    )


def research(rule: str, *, event_id: str = "SIM:P024-RESEARCH-001"):
    data, pivot = case_confirmed(rule)
    _, zone, trigger = case_from_closed_bars(rule)
    result = derive_swing_b2_s2_research(
        rule, data, pivot, zone, trigger,
        data.trigger_m15[-1].first_known_utc + timedelta(seconds=1),
        origin_event_id=event_id,
    )
    key = SimEventKey(
        instrument_version=result.signal.instrument_version,
        rule_id=rule, origin_event_id=result.signal.origin_event_id,
        policy_version=result.signal.parameter_version,
    )
    return result.signal, key


def gate(rule: str, *, struct=None, signal=None, key=None, ledger=None,
         age_seconds=1, ttl_seconds=600):
    sig, default_key = research(rule)
    sig = sig if signal is None else signal
    key = default_key if key is None else key
    st = structure(rule) if struct is None else struct
    led = SimEventLedger("SIM:P024-RESEARCH-LEDGER") if ledger is None else ledger
    now = sig.first_known_utc + timedelta(seconds=age_seconds)
    return buffer_sim_event(
        st, sig, key, led, now, ttl_seconds=ttl_seconds,
    )


class P024CausalStructureAndLedgerTests(unittest.TestCase):
    def test_01_latest_confirmed_pivots_determine_anchor_independently(self):
        for rule in ("B2", "S2"):
            st = structure(rule)
            old = evaluate_case(rule)
            kind = PivotKind.LOW if rule == "B2" else PivotKind.HIGH
            independent = []
            for scan in (old.daily, old.four_hour):
                pivots = [p.price for p in scan.pivots if p.kind is kind]
                self.assertTrue(pivots)
                independent.append(pivots[-1])
            expected = max(independent) if rule == "B2" else min(independent)
            self.assertEqual(st.anchor, expected)
            self.assertIs(st.status, StructureStatus.INTACT)
            self.assertFalse(st.source_verified)

    def test_02_strict_close_breach_is_invalidated(self):
        for rule in ("B2", "S2"):
            data, _ = case_confirmed(rule)
            anchor = structure(rule).anchor
            self.assertIsNotNone(anchor)
            assert anchor is not None
            price = anchor - EPS if rule == "B2" else anchor + EPS
            last = data.trigger_m15[-1]
            changed = replace(
                last, open=price, close=price,
                high=price + Decimal("0.01"),
                low=price - Decimal("0.01"),
            )
            actual = structure(
                rule, bars=replace(data, trigger_m15=(
                    data.trigger_m15[0], changed,
                )),
            )
            self.assertEqual(actual.anchor, anchor)
            self.assertIs(actual.status, StructureStatus.INVALIDATED)
            self.assertEqual(actual.reason, "P024_SIM_STRUCTURAL_BREACH")

    def test_03_exact_support_resistance_equality_is_not_breach(self):
        for rule in ("B2", "S2"):
            data, _ = case_confirmed(rule)
            anchor = structure(rule).anchor
            assert anchor is not None
            candle = replace(
                data.trigger_m15[-1],
                open=anchor, close=anchor,
                high=anchor + Decimal("0.01"),
                low=anchor - Decimal("0.01"),
            )
            actual = structure(
                rule, bars=replace(data, trigger_m15=(
                    data.trigger_m15[0], candle,
                )),
            )
            self.assertIs(actual.status, StructureStatus.INTACT)

    def test_04_later_candle_cannot_be_replayed_before_close(self):
        for rule in ("B2", "S2"):
            data, policy = case_confirmed(rule)
            asof = data.trigger_m15[-1].key.bar_end_utc-timedelta(microseconds=1)
            with self.assertRaisesRegex(ValueError, "FUTURE_PRICE_BAR"):
                derive_sim_structure(
                    rule, data, policy,
                    SimStructurePolicy("SIM:P024-CLOSE-CUTOFF"), asof,
                )

    def test_05_future_retrieved_m15_is_denied_not_backdated(self):
        for rule in ("B2", "S2"):
            data, _ = case_confirmed(rule)
            last = data.trigger_m15[-1]
            now = last.first_known_utc + timedelta(seconds=1)
            poisoned = replace(last, observation=replace(
                last.observation, retrieved_at_utc=now+timedelta(seconds=1),
            ))
            with self.assertRaisesRegex(ValueError, "FUTURE_KNOWN"):
                derive_sim_structure(
                    rule, replace(data, trigger_m15=(data.trigger_m15[0],
                                                       poisoned)),
                    case_confirmed(rule)[1],
                    SimStructurePolicy("SIM:P024-LATE-RETRIEVAL"),
                    now,
                )

    def test_06_late_first_known_m15_cannot_backdate(self):
        for rule in ("B2", "S2"):
            data, policy = case_confirmed(rule)
            last = data.trigger_m15[-1]
            now = last.first_known_utc + timedelta(seconds=1)
            later = now+timedelta(seconds=1)
            mutated = replace(
                last, first_known_utc=later,
                observation=replace(
                    last.observation, first_known_utc=later,
                    retrieved_at_utc=later,
                ),
            )
            with self.assertRaisesRegex(ValueError, "FUTURE_KNOWN"):
                derive_sim_structure(
                    rule, replace(data, trigger_m15=(
                        data.trigger_m15[0], mutated,
                    )), policy,
                    SimStructurePolicy("SIM:P024-LATE-FIRST-KNOWN"), now,
                )

    def test_07_missing_confirmed_pivot_is_unknown_not_intact(self):
        for rule in ("B2", "S2"):
            data, _ = case_confirmed(rule)
            missing = structure(rule, bars=replace(data,daily=data.daily[:3]))
            self.assertIs(missing.status,StructureStatus.UNKNOWN)
            self.assertIsNone(missing.anchor)
            self.assertIsNone(missing.pivot_first_known_utc)
            self.assertFalse(missing.may_send_confirmed_signal)

    def test_08_open_partial_unverified_candles_fail_closed(self):
        for rule in ("B2", "S2"):
            data, _ = case_confirmed(rule)
            last = data.trigger_m15[-1]
            cases = (
                (replace(last, lifecycle=BarLifecycle.OPEN), "OPEN_PROVISIONAL_BAR"),
                (replace(last, coverage=BarCoverage.PARTIAL), "INCOMPLETE_COVERAGE"),
                (replace(last, quality=SourceQuality.UNVERIFIED),
                 "SOURCE_QUALITY_UNVERIFIED"),
            )
            for bad,reason in cases:
                with self.subTest(rule=rule,reason=reason):
                    with self.assertRaisesRegex(ValueError,reason):
                        structure(rule,bars=replace(
                            data,trigger_m15=(data.trigger_m15[0],bad),
                        ))

    def test_09_unlicensed_provider_or_revision_is_denied(self):
        for rule in ("B2","S2"):
            data,_=case_confirmed(rule)
            first=data.trigger_m15[0]
            for bad in (
                replace(first,observation=replace(
                    first.observation,provider_id="LIVE:NOT_APPROVED")),
                replace(first,revision_number=2),
                replace(first,observation=replace(
                    first.observation,license_scope_claim="PRODUCTION")),
            ):
                with self.subTest(rule=rule):
                    with self.assertRaisesRegex(ValueError,"REJECT_REAL_MARKET"):
                        structure(rule,bars=replace(
                            data,trigger_m15=(bad,data.trigger_m15[-1]),
                        ))

    def test_10_identity_quote_side_calendar_stream_must_match(self):
        for rule in ("B2","S2"):
            data,_=case_confirmed(rule)
            first=data.trigger_m15[0]
            cases=(
                replace(first,key=replace(first.key,side=BarSide.BID)),
                replace(first,key=replace(first.key,
                                          instrument_version="SIM:OTHER")),
                replace(first,key=replace(first.key,
                                          calendar_version="SIM:OTHER")),
                replace(first,observation=replace(
                    first.observation,stream_id="SIM:DIFFERENT")),
            )
            for bad in cases:
                with self.subTest(rule=rule):
                    with self.assertRaises(ValueError):
                        structure(rule,bars=replace(
                            data,trigger_m15=(bad,data.trigger_m15[-1]),
                        ))

    def test_11_sim_policy_and_receipt_cannot_forge_authority(self):
        with self.assertRaisesRegex(ValueError,"SIM_ONLY"):
            SimStructurePolicy("SOURCE:APPROVED")
        with self.assertRaisesRegex(ValueError,"RESEARCH_MUST_NOT_GAIN_AUTHORITY"):
            replace(structure("B2"),may_send_confirmed_signal=True)

    def test_12_first_buffer_is_research_only_and_immutable(self):
        for rule in ("B2","S2"):
            d=gate(rule)
            self.assertIs(d.status,ResearchEventStatus.BUFFERED)
            self.assertEqual(len(d.ledger.events),1)
            self.assertFalse(d.source_numeric_approved)
            self.assertFalse(d.may_send_confirmed_signal)
            self.assertFalse(d.can_trade)
            self.assertEqual(d.provider_requests,0)
            self.assertEqual(d.drive_market_cache_writes,0)

    def test_13_replay_denied_both_immediate_and_after_ttl(self):
        for rule in ("B2","S2"):
            one=gate(rule)
            other=gate(rule,ledger=one.ledger)
            self.assertIs(other.status,ResearchEventStatus.DUPLICATE_DENIED)
            self.assertEqual(other.ledger,one.ledger)
            much_later=gate(rule,ledger=one.ledger,age_seconds=700,
                            ttl_seconds=600)
            self.assertIs(much_later.status,ResearchEventStatus.DUPLICATE_DENIED)

    def test_14_never_seen_event_expires(self):
        for rule in ("B2","S2"):
            x=gate(rule,age_seconds=601,ttl_seconds=600)
            self.assertIs(x.status,ResearchEventStatus.EXPIRED_DENIED)
            self.assertEqual(len(x.ledger.events),0)

    def test_15_ttl_type_and_future_first_known_denied(self):
        for rule in ("B2","S2"):
            for ttl in (0,True,-1,86401):
                with self.subTest(rule=rule,ttl=ttl):
                    with self.assertRaisesRegex(ValueError,"TTL_INVALID"):
                        gate(rule,ttl_seconds=ttl)
            signal,key=research(rule)
            with self.assertRaisesRegex(ValueError,"FUTURE_EVENT"):
                gate(rule,signal=replace(
                    signal,first_known_utc=signal.decision_utc+
                    timedelta(seconds=20),
                ),key=key)

    def test_16_rule_pair_and_policy_keys_do_not_collide(self):
        b2=gate("B2")
        s2_sig,s2key=research("S2")
        self.assertNotEqual(b2.ledger.events[0].key,s2key)
        s2=gate("S2",signal=s2_sig,key=s2key,ledger=b2.ledger)
        self.assertIs(s2.status,ResearchEventStatus.BUFFERED)
        self.assertEqual(len(s2.ledger.events),2)
        b_sig,b_key=research("B2")
        version=replace(b_sig,parameter_version="SIM:P024-DIFFERENT")
        diffkey=replace(b_key,policy_version="SIM:P024-DIFFERENT")
        other=gate("B2",signal=version,key=diffkey,ledger=s2.ledger)
        self.assertIs(other.status,ResearchEventStatus.BUFFERED)
        self.assertEqual(len(other.ledger.events),3)
        self.assertFalse(other.source_numeric_approved)

    def test_17_ledger_digest_is_canonical_and_order_independent(self):
        b_sig,b_key=research("B2")
        s_sig,s_key=research("S2")
        b=SimEventRecord(b_key,b_sig.first_known_utc,
                         b_sig.first_known_utc+timedelta(seconds=1))
        s=SimEventRecord(s_key,s_sig.first_known_utc,
                         s_sig.first_known_utc+timedelta(seconds=1))
        p=SimEventLedger("SIM:P024-LEDGER",(b,s))
        q=SimEventLedger("SIM:P024-LEDGER",(s,b))
        self.assertEqual(p.stable_digest(),q.stable_digest())
        self.assertEqual(len(p.stable_digest()),64)

    def test_18_malformed_unbounded_or_duplicate_ledger_denied(self):
        sig,key=research("B2")
        record=SimEventRecord(key,sig.first_known_utc,
                              sig.first_known_utc+timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError,"DUPLICATE_LEDGER"):
            SimEventLedger("SIM:P024-LEDGER",(record,record))
        with self.assertRaisesRegex(ValueError,"IMMUTABLE_LEDGER"):
            SimEventLedger("SIM:P024-LEDGER",[record])  # type: ignore[arg-type]
        entries=tuple(
            replace(record,key=replace(
                key,origin_event_id=f"SIM:P024-MANY-{i}",
            )) for i in range(65)
        )
        with self.assertRaisesRegex(ValueError,"IMMUTABLE_LEDGER"):
            SimEventLedger("SIM:P024-LEDGER",entries)
        filled=SimEventLedger("SIM:P024-LEDGER",entries[:64])
        self.assertIs(gate("B2",ledger=filled).status,ResearchEventStatus.LEDGER_FULL)

    def test_19_unknown_invalidated_or_no_signal_cannot_buffer(self):
        for rule in ("B2","S2"):
            original=structure(rule)
            unknown=replace(
                original,status=StructureStatus.UNKNOWN,anchor=None,
                pivot_first_known_utc=None,
            )
            self.assertIs(gate(rule,struct=unknown).status,
                          ResearchEventStatus.STRUCTURE_DENIED)
            inv=replace(original,status=StructureStatus.INVALIDATED,
                        reason="P024_SIM_STRUCTURAL_BREACH")
            self.assertIs(gate(rule,struct=inv).status,
                          ResearchEventStatus.STRUCTURE_DENIED)
            sig,key=research(rule)
            nosig=replace(sig,action=CandidateAction.NO_SIGNAL)
            self.assertIs(gate(rule,signal=nosig,key=key).status,
                          ResearchEventStatus.NO_SIGNAL)

    def test_20_forged_approval_and_opposite_direction_denied(self):
        for rule in ("B2","S2"):
            sig,key=research(rule)
            for forged in (
                replace(sig,source_verified_for_market=True),
                replace(sig,may_send_confirmed_signal=True),
                replace(sig,can_trade=True),
                replace(sig,original_forex_numerical_parity=True),
            ):
                with self.subTest(rule=rule):
                    with self.assertRaisesRegex(ValueError,"FORGED_SOURCE"):
                        gate(rule,signal=forged,key=key)
            opposite=replace(sig,action=CandidateAction.SELL
                             if rule=="B2" else CandidateAction.BUY)
            with self.assertRaisesRegex(ValueError,"WRONG_SIDE_EVENT"):
                gate(rule,signal=opposite,key=key)
            wrong=replace(key,origin_event_id="SIM:P024-IMPOSTOR")
            with self.assertRaisesRegex(ValueError,"CROSS_POLICY_OR_IDENTITY"):
                gate(rule,key=wrong)

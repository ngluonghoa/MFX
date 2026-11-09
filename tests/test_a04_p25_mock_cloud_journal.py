"""A04/P0.25: 24 pre-registered deterministic SIM mock-Cloud failure oracles.

No licensed Forex OHLC, real Drive writes, actual alerts or broker orders.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from mfx_research.p025_mock_cloud_journal import (
    MockCloudCASStore, MockJournalSnapshot, MockOutcome, MockPhase,
    SimJournalPolicy, SimMetadataEvent,
    TrustedMockCheckpoint, claim_sim_event,
    confirm_external_delivery_without_receiver_ack,
    mark_sim_attempt_intent, offer_sim_event, release_sim_lease,
)

T = datetime(2026, 11, 9, tzinfo=timezone.utc)


def metadata(rule: str = "B2", origin: str = "SIM:P025-ORIGIN-1"
             ) -> SimMetadataEvent:
    return SimMetadataEvent(
        instrument_version="SIM:EURUSD", rule_id=rule,
        policy_version="SIM:P025-POLICY",
        origin_event_id=origin,
        provider_id="SIM:OFFLINE",
        stream_id="SIM:M15-CLOSED",
        calendar_version="SIM:UTC-FIXED",
        aggregation_version="SIM:OHLC-V1",
        candle_end_utc=T,
        first_known_utc=T+timedelta(seconds=5),
        retrieved_at_utc=T+timedelta(seconds=6),
    )


def policy(**changes: object) -> SimJournalPolicy:
    return replace(SimJournalPolicy(
        version="SIM:P025-MOCK-ONLY",
        metadata_storage_reviewed=True,
    ), **changes)


def offered(event: SimMetadataEvent | None = None,
            p: SimJournalPolicy | None = None) -> MockJournalSnapshot:
    event = metadata() if event is None else event
    p = policy() if p is None else p
    r = offer_sim_event(MockJournalSnapshot(), event,
                        event.retrieved_at_utc + timedelta(seconds=1), p)
    if r.outcome is not MockOutcome.JOURNALED:
        raise AssertionError("fixture must journal only SIM metadata")
    return r.snapshot


def claimed(*, event: SimMetadataEvent | None = None,
            worker: str = "SIM:WORKER-A"):
    e = metadata() if event is None else event
    initial = offered(e)
    result = claim_sim_event(
        initial, e.event_id, worker,
        e.retrieved_at_utc+timedelta(seconds=2), policy(),
    )
    if result.outcome is not MockOutcome.CLAIMED:
        raise AssertionError("mock claim fixture must be valid")
    return result.snapshot, e


class P025CloudCASJournalOracles(unittest.TestCase):
    def test_01_metadata_only_canonical_event_id(self) -> None:
        e = metadata()
        self.assertEqual(e.event_id, metadata().event_id)
        self.assertEqual(len(e.event_id), 64)
        self.assertFalse(hasattr(e, "open"))
        self.assertFalse(hasattr(e, "high"))
        self.assertFalse(hasattr(e, "low"))
        self.assertFalse(hasattr(e, "close"))
        self.assertIsNone(e.raw_market_bar)

    def test_02_independent_identity_dimensions_cannot_collide(self) -> None:
        original = metadata()
        variants = (
            replace(original,instrument_version="SIM:GBPUSD"),
            replace(original,rule_id="S2"),
            replace(original,policy_version="SIM:P025-ALTERNATIVE"),
            replace(original,origin_event_id="SIM:P025-ORIGIN-2"),
            replace(original,provider_id="SIM:ALT_PROVIDER"),
            replace(original,stream_id="SIM:ALTERNATE"),
            replace(original,calendar_version="SIM:OTHER_UTC"),
            replace(original,aggregation_version="SIM:ALT_OHLC"),
            replace(original,candle_end_utc=T-timedelta(minutes=15)),
            replace(original,first_known_utc=T+timedelta(seconds=4)),
            replace(original,retrieved_at_utc=T+timedelta(seconds=7)),
        )
        ids = {original.event_id,*(x.event_id for x in variants)}
        self.assertEqual(len(ids),len(variants)+1)

    def test_03_real_provider_bidask_source_approval_or_ohlc_denied(self) -> None:
        e=metadata()
        for x in (
            {"provider_id":"REAL:NOT_LICENSED"},
            {"policy_version":"SOURCE:APPROVED"},
            {"quote_side":"BID"},
            {"quote_side":"ASK"},
            {"license_scope_claim":"PRODUCTION"},
            {"original_numeric_approved":True},
            {"raw_market_bar":{"high":"1.000"}},
        ):
            with self.subTest(case=x):
                with self.assertRaisesRegex(ValueError,
                                             "SIM_ONLY|REJECT_REAL_QUOTES"):
                    replace(e,**x)

    def test_04_clock_order_naive_and_future_retrieval_denied(self) -> None:
        e=metadata()
        for x in (
            {"first_known_utc":T-timedelta(seconds=1)},
            {"retrieved_at_utc":T+timedelta(seconds=4)},
            {"candle_end_utc":T+timedelta(seconds=8)},
        ):
            with self.subTest(x=x):
                with self.assertRaisesRegex(ValueError,"BAD_OBSERVABLE"):
                    replace(e,**x)
        with self.assertRaises(ValueError):
            replace(e,candle_end_utc=datetime(2026,11,9))
        with self.assertRaisesRegex(ValueError,"FUTURE_KNOWN"):
            offer_sim_event(MockJournalSnapshot(),e,
                            e.retrieved_at_utc-timedelta(microseconds=1),
                            policy())

    def test_05_empty_journal_checksum_deterministic_not_signature(self) -> None:
        a=MockJournalSnapshot()
        b=MockJournalSnapshot()
        self.assertEqual(a.head_hash,b.head_hash)
        self.assertEqual(len(a.head_hash),64)
        self.assertEqual(a.revision,0)
        self.assertEqual(a.entries,())
        self.assertFalse(hasattr(a,"signature"))

    def test_06_unreviewed_metadata_rights_denied_and_real_io_never_granted(self) -> None:
        e=metadata()
        deny=offer_sim_event(MockJournalSnapshot(),e,
                             e.retrieved_at_utc,SimJournalPolicy(
                                version="SIM:UNREVIEWED"))
        self.assertIs(deny.outcome,MockOutcome.PERMISSION_DENIED)
        self.assertEqual(deny.snapshot.revision,0)
        good=offer_sim_event(MockJournalSnapshot(),e,
                            e.retrieved_at_utc,policy())
        self.assertFalse(good.can_publish)
        self.assertEqual(good.real_drive_writes,0)
        self.assertEqual(good.provider_calls,0)
        self.assertEqual(good.broker_orders,0)

    def test_07_first_offer_is_one_append_and_one_revision(self) -> None:
        s=offered()
        self.assertEqual(s.revision,1)
        self.assertEqual(len(s.entries),1)
        self.assertEqual(len(s.records),1)
        self.assertEqual(s.entries[-1].revision,1)
        self.assertEqual(s.entries[-1].action,"OFFER")
        self.assertEqual(s.records[0].phase,MockPhase.QUEUED)
        self.assertEqual(s.entries[-1].digest,s.head_hash)

    def test_08_duplicates_remain_tombstoned_after_expiry(self) -> None:
        e=metadata()
        s=offered(e)
        again=offer_sim_event(
            s,e,e.retrieved_at_utc+timedelta(hours=4),policy())
        self.assertIs(again.outcome,MockOutcome.DUPLICATE_DENIED)
        self.assertIs(again.snapshot,s)
        self.assertEqual(len(again.snapshot.entries),1)

    def test_09_two_cloud_workers_cannot_both_cas_same_revision(self) -> None:
        base=MockJournalSnapshot()
        store=MockCloudCASStore()
        a=metadata(origin="SIM:P025-EVENT-A")
        b=metadata(origin="SIM:P025-EVENT-B")
        first=offer_sim_event(base,a,a.retrieved_at_utc,policy()).snapshot
        second=offer_sim_event(base,b,b.retrieved_at_utc,policy()).snapshot
        committed=store.cas(base.revision,base.head_hash,first,
                            metadata_permission_active=True)
        self.assertEqual(committed.revision,1)
        with self.assertRaisesRegex(ValueError,"CAS_STALE"):
            store.cas(base.revision,base.head_hash,second,
                      metadata_permission_active=True)
        self.assertEqual(store.read().records[0].event.origin_event_id,
                         "SIM:P025-EVENT-A")

    def test_10_wrong_head_digest_denied_even_same_revision(self) -> None:
        s=MockJournalSnapshot()
        event=metadata()
        proposal=offer_sim_event(s,event,event.retrieved_at_utc,policy()).snapshot
        cloud=MockCloudCASStore()
        with self.assertRaisesRegex(ValueError,"CAS_STALE"):
            cloud.cas(0,"0"*64,proposal,metadata_permission_active=True)

    def test_11_tamper_chain_or_record_detected_at_snapshot_read(self) -> None:
        s=offered()
        with self.assertRaisesRegex(ValueError,"TAMPERED_JOURNAL"):
            replace(s.entries[0],digest="0"*64)
        with self.assertRaisesRegex(ValueError,"TAMPERED_JOURNAL"):
            replace(s.entries[0],previous_hash="0"*64)
        damaged=replace(s.records[0],fence=9)
        with self.assertRaisesRegex(ValueError,"SNAPSHOT_STATE_TAMPER"):
            replace(s,records=(damaged,))

    def test_12_claim_monotonic_fence_and_lease_not_delivery(self) -> None:
        s,e=claimed()
        self.assertEqual(s.revision,2)
        self.assertIs(s.records[0].phase,MockPhase.LEASED)
        self.assertEqual(s.records[0].fence,1)
        self.assertEqual(s.records[0].worker_id,"SIM:WORKER-A")
        self.assertEqual(s.records[0].lease_until_utc,
                         e.retrieved_at_utc+timedelta(seconds=62))
        self.assertEqual(s.entries[-1].action,"CLAIM")

    def test_13_two_competing_lease_claims_one_wins(self) -> None:
        e=metadata()
        base=offered(e)
        store=MockCloudCASStore(base)
        clock=e.retrieved_at_utc+timedelta(seconds=3)
        a=claim_sim_event(base,e.event_id,"SIM:A",clock,policy())
        b=claim_sim_event(base,e.event_id,"SIM:B",clock,policy())
        store.cas(base.revision,base.head_hash,a.snapshot,
                  metadata_permission_active=True)
        with self.assertRaisesRegex(ValueError,"CAS_STALE"):
            store.cas(base.revision,base.head_hash,b.snapshot,
                      metadata_permission_active=True)
        self.assertEqual(store.read().records[0].worker_id,"SIM:A")

    def test_14_expired_lease_refenced_and_stale_worker_rejected(self) -> None:
        s,e=claimed()
        takeover=claim_sim_event(
            s,e.event_id,"SIM:WORKER-B",
            e.retrieved_at_utc+timedelta(seconds=63),policy())
        self.assertIs(takeover.outcome,MockOutcome.CLAIMED)
        self.assertEqual(takeover.snapshot.records[0].fence,2)
        old=mark_sim_attempt_intent(
            takeover.snapshot,e.event_id,"SIM:WORKER-A",1,
            e.retrieved_at_utc+timedelta(seconds=64),policy())
        self.assertIs(old.outcome,MockOutcome.FENCE_DENIED)
        self.assertIs(old.snapshot,takeover.snapshot)

    def test_15_release_only_matching_fence_and_worker(self) -> None:
        s,e=claimed()
        now=e.retrieved_at_utc+timedelta(seconds=3)
        bad=release_sim_lease(s,e.event_id,"SIM:WORKER-A",2,now,policy())
        self.assertIs(bad.outcome,MockOutcome.FENCE_DENIED)
        good=release_sim_lease(s,e.event_id,"SIM:WORKER-A",1,now,policy())
        self.assertIs(good.outcome,MockOutcome.RELEASED)
        self.assertEqual(good.snapshot.records[0].fence,1)
        self.assertIs(good.snapshot.records[0].phase,MockPhase.QUEUED)
        again=claim_sim_event(good.snapshot,e.event_id,"SIM:WORKER-B",
                              now+timedelta(seconds=1),policy())
        self.assertEqual(again.snapshot.records[0].fence,2)

    def test_16_never_seen_expired_event_no_retroactive_offer(self) -> None:
        e=metadata()
        d=offer_sim_event(MockJournalSnapshot(),e,
                          e.retrieved_at_utc+timedelta(seconds=601),policy())
        self.assertIs(d.outcome,MockOutcome.EXPIRED_DENIED)
        self.assertEqual(d.snapshot.revision,0)

    def test_17_mock_restart_same_checkpoint_no_duplicate(self) -> None:
        e=metadata()
        s0=MockJournalSnapshot()
        mock=MockCloudCASStore()
        proposal=offer_sim_event(s0,e,e.retrieved_at_utc,policy())
        mock.cas(s0.revision,s0.head_hash,proposal.snapshot,
                 metadata_permission_active=True)
        restarted=MockCloudCASStore(mock.read(),mock.checkpoint())
        self.assertEqual(restarted.read().head_hash,mock.read().head_hash)
        duplicate=offer_sim_event(restarted.read(),e,
                                  e.retrieved_at_utc+timedelta(seconds=2),
                                  policy())
        self.assertIs(duplicate.outcome,MockOutcome.DUPLICATE_DENIED)
        self.assertEqual(restarted.read().revision,1)

    def test_18_crash_after_claim_restores_leased_not_delivered(self) -> None:
        s,e=claimed()
        resumed=MockCloudCASStore(
            s,TrustedMockCheckpoint(s.revision,s.head_hash),
        ).read()
        self.assertEqual(resumed.records[0].phase,MockPhase.LEASED)
        self.assertFalse(hasattr(resumed.records[0],"delivered"))
        busy=claim_sim_event(resumed,e.event_id,"SIM:OTHER",
                             e.retrieved_at_utc+timedelta(seconds=3),
                             policy())
        self.assertIs(busy.outcome,MockOutcome.LEASE_BUSY)

    def test_19_attempt_intent_ambiguity_survives_restart_no_auto_retry(self) -> None:
        s,e=claimed()
        uncertain=mark_sim_attempt_intent(
            s,e.event_id,"SIM:WORKER-A",1,
            e.retrieved_at_utc+timedelta(seconds=3),policy())
        self.assertIs(uncertain.outcome,MockOutcome.ATTEMPT_AMBIGUOUS)
        self.assertIs(uncertain.snapshot.records[0].phase,MockPhase.AMBIGUOUS)
        restored=MockCloudCASStore(
            uncertain.snapshot,TrustedMockCheckpoint(
                uncertain.snapshot.revision,uncertain.snapshot.head_hash,
            ),
        ).read()
        retry=claim_sim_event(
            restored,e.event_id,"SIM:RECOVERY-WORKER",
            e.retrieved_at_utc+timedelta(seconds=100),policy())
        self.assertIs(retry.outcome,MockOutcome.AMBIGUOUS_DENIED)
        self.assertIs(retry.snapshot,restored)

    def test_20_no_ack_no_provable_exactly_once_external_delivery(self) -> None:
        s,e=claimed()
        attempted=mark_sim_attempt_intent(
            s,e.event_id,"SIM:WORKER-A",1,
            e.retrieved_at_utc+timedelta(seconds=3),policy())
        blocked=confirm_external_delivery_without_receiver_ack(
            attempted.snapshot)
        self.assertIs(blocked.outcome,MockOutcome.RECEIVER_ACK_REQUIRED)
        self.assertFalse(blocked.can_publish)
        self.assertEqual(blocked.broker_orders,0)
        self.assertEqual(blocked.real_drive_writes,0)

    def test_21_revoked_metadata_cloud_permission_blocks_cas_and_claim(self):
        e=metadata()
        untrusted=offer_sim_event(
            MockJournalSnapshot(),e,e.retrieved_at_utc,
            policy(metadata_access_revoked=True))
        self.assertIs(untrusted.outcome,MockOutcome.PERMISSION_DENIED)
        before=MockJournalSnapshot()
        candidate=offered(e)
        cloud=MockCloudCASStore()
        with self.assertRaisesRegex(ValueError,"CLOUD_PERMISSION_REVOKED"):
            cloud.cas(before.revision,before.head_hash,candidate,
                      metadata_permission_active=False)
        denied=claim_sim_event(
            candidate,e.event_id,"SIM:WORKER",
            e.retrieved_at_utc+timedelta(seconds=3),
            policy(metadata_access_revoked=True))
        self.assertIs(denied.outcome,MockOutcome.PERMISSION_DENIED)

    def test_22_trusted_checkpoint_rejects_valid_older_rollback(self) -> None:
        e=metadata()
        old=offered(e)
        store=MockCloudCASStore(old)
        two=claim_sim_event(old,e.event_id,"SIM:WORKER",
                            e.retrieved_at_utc+timedelta(seconds=3),policy())
        store.cas(old.revision,old.head_hash,two.snapshot,
                  metadata_permission_active=True)
        with self.assertRaisesRegex(ValueError,"ANTI_ROLLBACK"):
            MockCloudCASStore(old,store.checkpoint())

    def test_23_bounded_capacity_no_silent_history_compaction(self) -> None:
        p=policy()
        snap=MockJournalSnapshot()
        for i in range(32):
            e=metadata(origin=f"SIM:P025-BOUND-{i}")
            r=offer_sim_event(snap,e,e.retrieved_at_utc,p)
            self.assertIs(r.outcome,MockOutcome.JOURNALED)
            snap=r.snapshot
        self.assertEqual(snap.revision,32)
        e=metadata(origin="SIM:P025-EXTRA")
        denied=offer_sim_event(snap,e,e.retrieved_at_utc,p)
        self.assertIs(denied.outcome,MockOutcome.CAP_DENIED)
        self.assertIs(denied.snapshot,snap)
        with self.assertRaisesRegex(ValueError,"SNAPSHOT_STATE_TAMPER"):
            replace(snap,records=())

    def test_24_schema_policy_migration_and_production_claim_denied(self):
        with self.assertRaisesRegex(ValueError,"SCHEMA_MIGRATION"):
            MockJournalSnapshot(schema="SIM:P025-UNREVIEWED-MIGRATION")
        for field in (
            "source_numeric_approved", "allow_real_drive_writes",
            "allow_notifications",
        ):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError,"FORGED_REAL_PERMISSION"):
                    policy(**{field:True})
        e=metadata()
        r=offer_sim_event(MockJournalSnapshot(),e,
                          e.retrieved_at_utc,policy())
        self.assertFalse(r.can_publish)
        self.assertFalse(r.source_numeric_approved)
        self.assertEqual(r.real_drive_writes,0)
        self.assertEqual(r.provider_calls,0)
        self.assertEqual(r.broker_orders,0)

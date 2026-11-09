"""A04/P0.25 Cloud-hosted MOCK journal research receipt, never a real Drive I/O."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import unittest

from mfx_research.p025_mock_cloud_journal import (
    MockCloudCASStore, MockJournalSnapshot, MockOutcome,
    SimJournalPolicy, SimMetadataEvent, claim_sim_event,
    confirm_external_delivery_without_receiver_ack, offer_sim_event,
)


def main() -> None:
    suite = unittest.defaultTestLoader.discover(
        "tests", pattern="test_a04_p25_mock_cloud_journal.py",
    )
    count = suite.countTestCases()
    if count != 24:
        raise ValueError("P025_PRE_REGISTERED_24_METHOD_INVENTORY_DRIFT")
    tested = unittest.TextTestRunner(verbosity=1).run(suite)
    if not tested.wasSuccessful():
        raise ValueError("P025_MOCK_CLOUD_FAULT_CASES_FAILED")
    candle = datetime(2026, 11, 9, tzinfo=timezone.utc)
    event = SimMetadataEvent(
        instrument_version="SIM:EURUSD",
        rule_id="B2", policy_version="SIM:P025-RESEARCH",
        origin_event_id="SIM:P025-DEMO-NOT-A-SIGNAL",
        provider_id="SIM:OFFLINE", stream_id="SIM:FIXTURE",
        calendar_version="SIM:UTC-FIXED",
        aggregation_version="SIM:M15",
        candle_end_utc=candle,
        first_known_utc=candle + timedelta(seconds=1),
        retrieved_at_utc=candle + timedelta(seconds=2),
    )
    policy = SimJournalPolicy(
        version="SIM:P025-MOCK", metadata_storage_reviewed=True,
    )
    current = MockJournalSnapshot()
    mock = MockCloudCASStore()
    proposed = offer_sim_event(
        current, event, event.retrieved_at_utc, policy,
    )
    if proposed.outcome is not MockOutcome.JOURNALED:
        raise ValueError("P025_SIM_OFFER_DENIED")
    committed = mock.cas(
        current.revision, current.head_hash, proposed.snapshot,
        metadata_permission_active=True,
    )
    claimed = claim_sim_event(
        committed, event.event_id, "SIM:CI-MOCK-WORKER",
        event.retrieved_at_utc + timedelta(seconds=1), policy,
    )
    if claimed.outcome is not MockOutcome.CLAIMED:
        raise ValueError("P025_SIM_FENCED_CLAIM_DENIED")
    mock.cas(
        committed.revision, committed.head_hash, claimed.snapshot,
        metadata_permission_active=True,
    )
    if (mock.read().revision != 2
            or confirm_external_delivery_without_receiver_ack(
                mock.read(),
            ).outcome is not MockOutcome.RECEIVER_ACK_REQUIRED):
        raise ValueError("P025_MOCK_CAS_UNSAFE_AUTHORITY")
    print("MFX_A04_P25_MOCK_CLOUD_CAS_SAFETY_PASS")
    print("MFX_A04_P25_RECEIPT " + json.dumps({
        "pre_registered_grouped_tests": count,
        "mock_state_revision": mock.read().revision,
        "mock_append_chain_sha256": mock.read().head_hash,
        "simulation": "IN_MEMORY_CAS_NOT_GOOGLE_DRIVE",
        "external_durable_journal_verified": False,
        "external_receiver_ack_verified": False,
        "exactly_once_external_delivery_proven": False,
        "official_numeric_forex_buy_sell_rules": 0,
        "unapproved_b2_s2_source_numeric_obligations": 36,
        "live_verified_buy_sell_alerts": 0,
        "real_forex_feed_requests": 0,
        "real_drive_market_cache_writes": 0,
        "real_drive_journal_writes": 0,
        "broker_orders": 0,
        "release_ready": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()

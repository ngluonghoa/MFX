"""A04/P0.26 hosted contract receipt -- Docs revision CAS is SIM ONLY."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import unittest

from mfx_research.p025_mock_cloud_journal import SimMetadataEvent
from mfx_research.p026_docs_cas_readiness import (
    ContractOutcome, MockDocsRequiredRevisionServer,
    SimRevisionWriteIntent, SourceRightsGate, go_no_go_for_real_journal,
    unsafe_generic_drive_file_update_verdict,
)


def main() -> None:
    suite = unittest.defaultTestLoader.discover(
        "tests", pattern="test_a04_p26_docs_cas_readiness.py",
    )
    count = suite.countTestCases()
    if count != 20:
        raise ValueError("P026_PRE_REGISTERED_TEST_INVENTORY_DRIFT")
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise ValueError("P026_SIMULATED_DOCS_CAS_ORACLE_FAILED")
    now = datetime(2026, 11, 9, tzinfo=timezone.utc)
    e = SimMetadataEvent(
        instrument_version="SIM:EURUSD", rule_id="B2",
        policy_version="SIM:P026-CONTRACT-DEMO",
        origin_event_id="SIM:P026-DEMO-EVENT",
        provider_id="SIM:OFFLINE",
        stream_id="SIM:M15-FIXTURE",
        calendar_version="SIM:FIXED-UTC",
        aggregation_version="SIM:V1",
        candle_end_utc=now,
        first_known_utc=now+timedelta(seconds=1),
        retrieved_at_utc=now+timedelta(seconds=2),
    )
    server = MockDocsRequiredRevisionServer()
    intent = SimRevisionWriteIntent(
        captured_revision_id=server.read().revision_id,
        event=e, metadata_storage_reviewed=True,
    )
    first = server.append(intent, now+timedelta(seconds=3))
    stale = server.append(intent, now+timedelta(seconds=3))
    if (first.outcome is not ContractOutcome.SIM_CAS_APPENDED
            or stale.outcome is not ContractOutcome.STALE_REVISION
            or server.read().epoch != 1
            or first.verified_buy_sell_alerts != 0
            or first.real_docs_journal_writes != 0
            or go_no_go_for_real_journal(SourceRightsGate())
            is not ContractOutcome.NO_GO_REAL
            or unsafe_generic_drive_file_update_verdict(
                has_file_version=True, has_modified_time=True,
            ) is not ContractOutcome.NO_GO_DRIVE):
        raise ValueError("P026_READ_ONLY_GO_NO_GO_BREACHED")
    print("MFX_A04_P26_DOCS_CAS_READ_ONLY_CONTRACT_PASS")
    print("MFX_A04_P26_RECEIPT "+json.dumps({
        "pre_registered_grouped_tests": count,
        "mock_docs_revision_cas_result": first.outcome.value,
        "mock_second_writer": stale.outcome.value,
        "docs_required_revision_api_documented": True,
        "drive_files_update_typed_cas_supported": False,
        "real_docs_journal_cas_verified": False,
        "actual_docs_multiworker_race_tested": False,
        "go_no_go_real_journal": ContractOutcome.NO_GO_REAL.value,
        "docs_write_requests_by_this_milestone": 0,
        "real_drive_quote_cache_writes": 0,
        "verified_forex_buy_sell_alerts": 0,
        "real_broker_orders": 0,
        "numeric_entry_rules_approved": 0,
        "source_numeric_b2_s2_obligations_pending": 36,
        "release_ready": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()

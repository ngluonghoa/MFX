"""A04/P0.26: 20 pre-registered read-only Docs CAS and Drive NO-GO oracles.

All Google Docs/Drive behaviors here are MOCKED. No real API write, market
data, alerts, user-facing BUY/SELL or broker operations.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from mfx_research.p025_mock_cloud_journal import SimMetadataEvent
from mfx_research.p026_docs_cas_readiness import (
    ContractOutcome, ErrorHandling, MockDocsRequiredRevisionServer,
    SimDocsSnapshot, SimRevisionWriteIntent, SourceRightsGate,
    classify_docs_api_failure, go_no_go_for_real_journal,
    unsafe_generic_drive_file_update_verdict,
)

T = datetime(2026, 11, 9, tzinfo=timezone.utc)


def event(*, rule: str = "B2",
          origin: str = "SIM:P026-FIRST-EVENT") -> SimMetadataEvent:
    return SimMetadataEvent(
        instrument_version="SIM:EURUSD",
        rule_id=rule,
        policy_version="SIM:P026-RESEARCH-UNAPPROVED",
        origin_event_id=origin,
        provider_id="SIM:NO_REAL_MARKET_FEED",
        stream_id="SIM:OFFLINE_M15_CLOSED",
        calendar_version="SIM:UTC_SYNTHETIC",
        aggregation_version="SIM:M15",
        candle_end_utc=T,
        first_known_utc=T + timedelta(seconds=1),
        retrieved_at_utc=T + timedelta(seconds=2),
    )


def intent(e: SimMetadataEvent | None = None,
           revision: str = "SIM:REV-0000",
           **kwargs: object) -> SimRevisionWriteIntent:
    return SimRevisionWriteIntent(
        captured_revision_id=revision,
        event=event() if e is None else e,
        metadata_storage_reviewed=True,
        **kwargs,
    )


def asof() -> datetime:
    return T + timedelta(seconds=3)


class P026DocsRevisionCASOracles(unittest.TestCase):
    def test_01_price_free_typed_event_and_revision_are_required(self) -> None:
        e = event()
        s = SimDocsSnapshot()
        self.assertEqual(len(e.event_id),64)
        self.assertFalse(hasattr(e,"close"))
        self.assertIsNone(e.raw_market_bar)
        self.assertEqual(s.revision_id,"SIM:REV-0000")
        self.assertEqual(s.document_type,"application/vnd.google-apps.document")
        self.assertNotIn("OHLC",s.revision_id)

    def test_02_required_revision_id_exact_control_only(self) -> None:
        m = MockDocsRequiredRevisionServer()
        for control in ("targetRevisionId", "", "unconditional"):
            with self.subTest(control=control):
                r = m.append(intent(write_control=control),asof())
                self.assertIs(r.outcome,ContractOutcome.BAD_CONTROL)
                self.assertEqual(m.read().epoch,0)
        x=m.append(intent(),asof())
        self.assertIs(x.outcome,ContractOutcome.SIM_CAS_APPENDED)

    def test_03_single_conditional_append_increments_mock_version_only(self):
        s=MockDocsRequiredRevisionServer()
        r=s.append(intent(),asof())
        self.assertEqual(r.snapshot.epoch,1)
        self.assertEqual(r.snapshot.revision_id,"SIM:REV-0001")
        self.assertEqual(r.snapshot.event_ids,(event().event_id,))
        self.assertTrue(r.simulated_only)
        self.assertEqual(r.real_docs_journal_writes,0)
        self.assertEqual(r.verified_buy_sell_alerts,0)
        self.assertFalse(r.release_ready)

    def test_04_two_writers_same_revision_only_one_wins(self) -> None:
        s=MockDocsRequiredRevisionServer()
        start=s.read()
        a=s.append(intent(event(origin="SIM:P026-WRITER-A"),
                          revision=start.revision_id),asof())
        b=s.append(intent(event(origin="SIM:P026-WRITER-B"),
                          revision=start.revision_id),asof())
        self.assertIs(a.outcome,ContractOutcome.SIM_CAS_APPENDED)
        self.assertIs(b.outcome,ContractOutcome.STALE_REVISION)
        self.assertEqual(len(s.read().event_ids),1)
        self.assertEqual(s.read().epoch,1)

    def test_05_stale_write_does_not_update_or_publish(self) -> None:
        server=MockDocsRequiredRevisionServer()
        first=server.append(intent(),asof())
        stale=server.append(
            intent(event(origin="SIM:P026-SECOND"),
                   revision="SIM:REV-0000"),asof(),
        )
        self.assertIs(stale.outcome,ContractOutcome.STALE_REVISION)
        self.assertIs(stale.snapshot,first.snapshot)
        self.assertEqual(stale.real_docs_journal_writes,0)
        self.assertEqual(stale.verified_buy_sell_alerts,0)

    def test_06_target_revision_rebase_is_not_strict_cas(self) -> None:
        s=MockDocsRequiredRevisionServer()
        r=s.append(intent(write_control="targetRevisionId"),asof())
        self.assertIs(r.outcome,ContractOutcome.BAD_CONTROL)
        self.assertEqual(s.read().epoch,0)

    def test_07_generic_drive_metadata_version_is_not_cas(self) -> None:
        for version in (False,True):
            for modified in (False,True):
                self.assertIs(unsafe_generic_drive_file_update_verdict(
                    has_file_version=version,has_modified_time=modified,
                ),ContractOutcome.NO_GO_DRIVE)
        with self.assertRaisesRegex(ValueError,"UNVERIFIED_DRIVE_CAS"):
            unsafe_generic_drive_file_update_verdict(
                has_file_version=True,has_modified_time=True,
                has_server_enforced_precondition_in_connector=True,
            )

    def test_08_invalid_or_missing_revision_and_doc_type_denied(self) -> None:
        for rev in ("", "1", "SIM:FAKE"):
            with self.subTest(rev=rev):
                s=MockDocsRequiredRevisionServer()
                r=s.append(intent(revision=rev),asof())
                self.assertIs(r.outcome,ContractOutcome.BAD_CONTROL)
                self.assertEqual(s.read().epoch,0)
        with self.assertRaisesRegex(ValueError,"MOCK_REVISION"):
            SimDocsSnapshot(epoch=1,revision_id="SIM:REV-0000")
        with self.assertRaisesRegex(ValueError,"MOCK_ONLY_NATIVE"):
            SimDocsSnapshot(document_type="application/pdf")

    def test_09_reviewed_simulation_does_not_grant_real_storage(self) -> None:
        s=MockDocsRequiredRevisionServer()
        denied=s.append(SimRevisionWriteIntent(
            captured_revision_id="SIM:REV-0000",
            event=event(),metadata_storage_reviewed=False,
        ),asof())
        self.assertIs(denied.outcome,ContractOutcome.RIGHTS_STOP)
        permitted_mock=s.append(intent(),asof())
        self.assertIs(permitted_mock.outcome,ContractOutcome.SIM_CAS_APPENDED)
        self.assertEqual(permitted_mock.real_docs_journal_writes,0)
        with self.assertRaisesRegex(ValueError,"MOCK_CANNOT_GRANT_REAL"):
            replace(intent(),real_drive_write_authorized=True)

    def test_10_revoked_permission_and_403_401_block_all_writes(self) -> None:
        s=MockDocsRequiredRevisionServer()
        r=s.append(intent(access_revoked=True),asof())
        self.assertIs(r.outcome,ContractOutcome.RIGHTS_STOP)
        for status in (401,403):
            self.assertIs(classify_docs_api_failure(status),
                          ErrorHandling.DENY_RIGHTS)
        self.assertEqual(s.read().epoch,0)

    def test_11_identical_immutable_event_denied_after_first_append(self):
        s=MockDocsRequiredRevisionServer()
        first=s.append(intent(),asof())
        twice=s.append(intent(revision=first.snapshot.revision_id),
                       asof()+timedelta(hours=12))
        self.assertIs(twice.outcome,ContractOutcome.DUPLICATE_EVENT)
        self.assertEqual(twice.snapshot.epoch,1)
        self.assertEqual(len(twice.snapshot.event_ids),1)

    def test_12_ambiguous_delivery_always_stops_replay(self) -> None:
        e=event()
        snap=SimDocsSnapshot(
            epoch=1,revision_id="SIM:REV-0001",
            event_ids=(e.event_id,),
            ambiguous_event_ids=(e.event_id,),
        )
        s=MockDocsRequiredRevisionServer(snap)
        r=s.append(intent(e,revision="SIM:REV-0001"),asof())
        self.assertIs(r.outcome,ContractOutcome.AMBIGUOUS_STOP)
        self.assertEqual(r.verified_buy_sell_alerts,0)
        self.assertEqual(s.read().epoch,1)

    def test_13_network_timeout_after_write_requires_reconcile(self):
        self.assertIs(classify_docs_api_failure(
            None,timeout_after_write=True,
        ),ErrorHandling.MANUAL_COMMIT_RECONCILIATION)
        self.assertIs(classify_docs_api_failure(
            200,timeout_after_write=True,
        ),ErrorHandling.MANUAL_COMMIT_RECONCILIATION)

    def test_14_unrelated_400_is_invalid_not_stale_retry(self) -> None:
        self.assertIs(classify_docs_api_failure(400),
                      ErrorHandling.DENY_INVALID_REQUEST)
        self.assertIs(classify_docs_api_failure(
            400,explicit_stale_revision=True,
        ),ErrorHandling.FETCH_LATEST_NO_ALERT)

    def test_15_429_quota_means_metadata_backoff_only(self) -> None:
        self.assertIs(classify_docs_api_failure(429),
                      ErrorHandling.BOUNDED_BACKOFF_READ)
        r=MockDocsRequiredRevisionServer().append(intent(),asof(),
                        user_writes_this_minute=60)
        self.assertIs(r.outcome,ContractOutcome.QUOTA_STOP)
        self.assertEqual(r.verified_buy_sell_alerts,0)

    def test_16_after_commit_5xx_is_ambiguous_not_a_failure_proof(self):
        for status in (500,502,503,504):
            with self.subTest(code=status):
                self.assertIs(classify_docs_api_failure(status),
                              ErrorHandling.MANUAL_COMMIT_RECONCILIATION)
        self.assertIs(classify_docs_api_failure(None),
                      ErrorHandling.MANUAL_COMMIT_RECONCILIATION)

    def test_17_conflict_must_reload_and_dedup_before_new_proposal(self):
        s=MockDocsRequiredRevisionServer()
        a=s.append(intent(),asof())
        stale=s.append(intent(),asof())
        self.assertIs(stale.outcome,ContractOutcome.STALE_REVISION)
        retry=s.append(intent(revision=s.read().revision_id),asof())
        self.assertIs(retry.outcome,ContractOutcome.DUPLICATE_EVENT)
        self.assertIs(retry.snapshot,a.snapshot)
        self.assertEqual(s.read().epoch,1)

    def test_18_same_store_snapshot_is_not_trusted_highwater(self):
        older=SimDocsSnapshot()
        newer=MockDocsRequiredRevisionServer().append(intent(),asof()).snapshot
        self.assertNotEqual(older.revision_id,newer.revision_id)
        # An attacker can reconstruct a syntactically valid older snapshot;
        # a genuinely trusted external checkpoint is still missing.
        self.assertEqual(MockDocsRequiredRevisionServer(older).read(),older)
        self.assertIs(go_no_go_for_real_journal(SourceRightsGate()),
                      ContractOutcome.NO_GO_REAL)

    def test_19_conservative_docs_write_quota_both_levels(self):
        s=MockDocsRequiredRevisionServer()
        a=s.append(intent(),asof(),
                   user_writes_this_minute=59,
                   project_writes_this_minute=599)
        self.assertIs(a.outcome,ContractOutcome.SIM_CAS_APPENDED)
        e=event(origin="SIM:P026-OTHER")
        at=a.snapshot.revision_id
        for n,p in ((60,0),(0,600)):
            denied=s.append(intent(e,revision=at),asof(),
                            user_writes_this_minute=n,
                            project_writes_this_minute=p)
            self.assertIs(denied.outcome,ContractOutcome.QUOTA_STOP)
        self.assertEqual(s.read().epoch,1)

    def test_20_all_declared_flags_still_no_production_approval(self):
        self.assertIs(go_no_go_for_real_journal(SourceRightsGate()),
                      ContractOutcome.NO_GO_REAL)
        claimed=SourceRightsGate(
            original_numeric_entry_rules_approved=15,
            b2_s2_numeric_obligations_approved=36,
            licensed_market_source_verified=True,
            real_drive_market_cache_rights_verified=True,
            metadata_journal_storage_approved=True,
            receiver_ack_contract_verified=True,
            actual_docs_race_verified=True,
            independently_trusted_highwater_verified=True,
        )
        self.assertIs(go_no_go_for_real_journal(claimed),
                      ContractOutcome.NO_GO_REAL)
        with self.assertRaisesRegex(ValueError,"MOCK_CANNOT_GRANT_REAL"):
            replace(intent(),notification_authorized=True)
        with self.assertRaisesRegex(ValueError,"REJECT_REAL"):
            replace(event(),license_scope_claim="PRODUCTION")

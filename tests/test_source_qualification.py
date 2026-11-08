import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from forex_trading.market_data import BarSide, Timeframe
from forex_trading.source_qualification import (
    DocumentBasis, FeedModel, LicensedUse, PublicCapabilityClaim,
    RightDecision, UseRightsClaim, assess_source_for_m2_review,
)


T = datetime(2026, 11, 7, tzinfo=timezone.utc)
URL = "https://example.org/synthetic-contract-terms"


def candidate(**changes):
    values = dict(
        provider_id="synthetic-provider", product_id="synthetic-two-sided-v1",
        instrument_version="EURUSD-synthetic",
        feed_model=FeedModel.BID_ASK_CANDLES,
        quote_sides=frozenset({BarSide.BID, BarSide.ASK}),
        timeframes=frozenset({Timeframe.M1, Timeframe.M5, Timeframe.M15}),
        documentation_url="https://example.org/public-api",
        documentation_first_known_utc=T - timedelta(days=2),
        timestamp_semantics_documented=True,
        historical_account_price_parity_independently_verified=True,
    )
    values.update(changes)
    return PublicCapabilityClaim(**values)


def right(purpose, **changes):
    values = dict(
        purpose=purpose,
        decision=RightDecision.ALLOW_CLAIMED,
        document_basis=DocumentBasis.ACCOUNT_TERMS,
        evidence_url=URL, evidence_sha256="b"*64,
        first_known_utc=T - timedelta(days=1),
        expires_utc=T + timedelta(days=365),
    )
    values.update(changes)
    return UseRightsClaim(**values)


SCOPES = (LicensedUse.API_ACCESS, LicensedUse.STORE_RAW,
          LicensedUse.DERIVE_BARS, LicensedUse.HISTORICAL_REPLAY,
          LicensedUse.INTERNAL_BACKTEST, LicensedUse.CACHE_INCREMENTAL)


def full_rights():
    return tuple(right(x) for x in SCOPES)


def check(c=None, rights=None):
    return assess_source_for_m2_review(candidate() if c is None else c,
                                       full_rights() if rights is None else rights, T)


class SourceQualificationTests(unittest.TestCase):
    def test_synthetic_package_can_be_review_ready_not_authorized(self):
        got = check()
        self.assertTrue(got.review_packet_ready)
        self.assertTrue(got.public_api_candidate_fit)
        self.assertTrue(got.stated_rights_complete_for_review)
        self.assertFalse(got.vendor_entitlement_independently_verified)
        self.assertFalse(got.may_ingest_real_data)
        self.assertFalse(got.may_cache_or_store_real_data)
        self.assertFalse(got.may_run_real_backtest)

    def test_missing_rights_are_hard_blockers(self):
        got = check(rights=())
        self.assertFalse(got.stated_rights_complete_for_review)
        self.assertIn("RIGHT_MISSING:STORE_RAW", got.reasons)

    def test_some_scopes_missing_blocks(self):
        got = check(rights=tuple(right(x) for x in SCOPES[:-1]))
        self.assertIn("RIGHT_MISSING:CACHE_INCREMENTAL", got.reasons)

    def test_public_documentation_does_not_grant_account_right(self):
        rights = list(full_rights())
        rights[0] = replace(rights[0], document_basis=DocumentBasis.PUBLIC_DOCUMENTATION)
        got = check(rights=tuple(rights))
        self.assertIn("ACCOUNT_ENTITLEMENT_NOT_PROVEN_BY_PUBLIC_DOC:API_ACCESS", got.reasons)
        self.assertFalse(got.review_packet_ready)

    def test_unknown_right_blocks(self):
        rights = list(full_rights())
        rights[0] = replace(rights[0], decision=RightDecision.UNKNOWN)
        self.assertIn("RIGHT_UNVERIFIED:API_ACCESS", check(rights=tuple(rights)).reasons)

    def test_denied_right_blocks(self):
        rights = list(full_rights())
        rights[0] = replace(rights[0], decision=RightDecision.DENY)
        self.assertIn("RIGHT_DENIED:API_ACCESS", check(rights=tuple(rights)).reasons)

    def test_expired_right_blocks(self):
        rights = list(full_rights())
        rights[0] = replace(rights[0], expires_utc=T)
        self.assertIn("RIGHT_EXPIRED:API_ACCESS", check(rights=tuple(rights)).reasons)

    def test_future_known_right_blocks(self):
        rights = list(full_rights())
        rights[0] = replace(rights[0], first_known_utc=T + timedelta(seconds=1),
                            expires_utc=T + timedelta(days=365))
        self.assertIn("RIGHT_FUTURE_KNOWN:API_ACCESS", check(rights=tuple(rights)).reasons)

    def test_duplicate_scope_blocks(self):
        rights = full_rights() + (right(LicensedUse.API_ACCESS),)
        self.assertIn("DUPLICATE_RIGHTS_SCOPE", check(rights=rights).reasons)

    def test_future_public_doc_blocked(self):
        c = candidate(documentation_first_known_utc=T + timedelta(hours=1))
        got = check(c)
        self.assertIn("PUBLIC_DOCUMENTATION_FUTURE_KNOWN", got.reasons)

    def test_mid_only_nonqualifying(self):
        c = candidate(feed_model=FeedModel.GENERIC_OHLC,
                      quote_sides=frozenset({BarSide.MID}))
        got = check(c)
        self.assertIn("PRICE_MODEL_NOT_TWO_SIDED_HISTORICAL", got.reasons)
        self.assertIn("BID_ASK_BOTH_REQUIRED", got.reasons)

    def test_missing_ask_nonqualifying(self):
        got = check(candidate(quote_sides=frozenset({BarSide.BID})))
        self.assertIn("BID_ASK_BOTH_REQUIRED", got.reasons)

    def test_mid_plus_bid_not_ask(self):
        c = candidate(quote_sides=frozenset({BarSide.BID, BarSide.MID}))
        self.assertFalse(check(c).public_api_candidate_fit)

    def test_snapshot_quote_not_historical(self):
        c = candidate(feed_model=FeedModel.SNAPSHOT_QUOTE)
        self.assertIn("PRICE_MODEL_NOT_TWO_SIDED_HISTORICAL", check(c).reasons)

    def test_bid_ask_ticks_allowed_as_candidate_only(self):
        c = candidate(feed_model=FeedModel.BID_ASK_TICKS)
        got = check(c)
        self.assertTrue(got.public_api_candidate_fit)
        self.assertFalse(got.may_run_real_backtest)

    def test_m15_baseline_required(self):
        c = candidate(timeframes=frozenset({Timeframe.M1, Timeframe.M5}))
        self.assertIn("M1_M5_M15_HISTORY_NOT_DOCUMENTED", check(c).reasons)

    def test_timestamp_semantics_missing(self):
        c = candidate(timestamp_semantics_documented=False)
        self.assertIn("TIMESTAMP_SEMANTICS_UNDOCUMENTED", check(c).reasons)

    def test_account_historical_parity_unproven(self):
        c = candidate(historical_account_price_parity_independently_verified=False)
        got = check(c)
        self.assertIn("HISTORICAL_VS_ACCOUNT_PRICE_PARITY_UNVERIFIED", got.reasons)

    def test_unsupported_timeframe_type_rejected(self):
        with self.assertRaises(TypeError):
            candidate(timeframes=frozenset({"M1", "M5", "M15"}))

    def test_unsupported_quote_side_type_rejected(self):
        with self.assertRaises(TypeError):
            candidate(quote_sides=frozenset({"BID", "ASK"}))

    def test_credentials_in_public_url_rejected(self):
        with self.assertRaisesRegex(ValueError, "noncredential HTTPS"):
            candidate(documentation_url="https://user@secret.example/doc")

    def test_plain_http_url_rejected(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            candidate(documentation_url="http://example.org/public-api")

    def test_missing_provider_rejected(self):
        with self.assertRaises(ValueError):
            candidate(provider_id="")

    def test_naive_doc_time_rejected(self):
        with self.assertRaises(ValueError):
            candidate(documentation_first_known_utc=datetime(2026, 11, 7))

    def test_typed_status_required(self):
        with self.assertRaises(TypeError):
            right(LicensedUse.API_ACCESS, decision="ALLOW_CLAIMED")

    def test_invalid_doc_digest_rejected(self):
        with self.assertRaises(ValueError):
            right(LicensedUse.API_ACCESS, evidence_sha256="unverified")

    def test_expiration_before_known_rejected(self):
        with self.assertRaises(ValueError):
            right(LicensedUse.API_ACCESS, expires_utc=T - timedelta(days=3))

    def test_missing_expiration_is_a_claim_not_a_grant(self):
        rights = list(full_rights())
        rights[0] = replace(rights[0], expires_utc=None)
        got = check(rights=tuple(rights))
        self.assertTrue(got.review_packet_ready)
        self.assertFalse(got.may_run_real_backtest)

    def test_redistribution_not_implied_by_internal_backtest(self):
        got = check()
        self.assertEqual(LicensedUse.REDISTRIBUTE.value, "REDISTRIBUTE")
        self.assertFalse(got.may_ingest_real_data)

    def test_non_tuple_rights_rejected(self):
        with self.assertRaises(TypeError):
            assess_source_for_m2_review(candidate(), list(full_rights()), T)

    def test_wrong_asof_timezone_rejected(self):
        with self.assertRaises(ValueError):
            assess_source_for_m2_review(candidate(), full_rights(), datetime(2026, 11, 7))

    def test_invalid_bool_claim_rejected(self):
        with self.assertRaises(TypeError):
            candidate(timestamp_semantics_documented="yes")

    def test_cannot_force_authorized_flag_from_caller(self):
        got = check()
        self.assertFalse(got.vendor_entitlement_independently_verified)
        self.assertFalse(got.may_run_real_backtest)
        self.assertIn("CLAIMED_PERMISSIONS_NEED_INDEPENDENT_CONTRACT_VALIDATION", got.reasons)

    def test_replay_right_does_not_imply_backtest_right(self):
        rights = tuple(right(x) for x in SCOPES if x is not LicensedUse.INTERNAL_BACKTEST)
        got = check(rights=rights)
        self.assertIn("RIGHT_MISSING:INTERNAL_BACKTEST", got.reasons)

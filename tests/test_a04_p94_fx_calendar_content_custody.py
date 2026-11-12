"""A04/P0.94: no source calendar gap waiver from caller-curated JSON/SHA."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from unittest import TestCase

from tools.mfx_fx_calendar_content_custody import (
    SCHEMA, RECEIPT, MAX_BYTES, SnapshotCandidate,
    SnapshotCustodyReceipt, inspect_calendar_candidate,
)
from tools.mfx_fx_calendar_provenance import (
    OFFICIAL_REFERENCES, WRITER_BLOB_SHA, WRITER_ENDPOINT,
)

REF = "TWELVE_DATA_FOREX_V2"
NOW = "2026-11-12T12:00:00+00:00"
SATURDAY = "2026-11-07T08:00:00+00:00"
SUNDAY = "2026-11-08T08:00:00+00:00"
MONDAY = "2026-11-09T08:00:00+00:00"


def payload(**kw):
    d = {
        "schema": SCHEMA, "issuer": "TWELVE_DATA",
        "product_id": "FOREX_COMPOSITE_MID",
        "feed_version": "FOREX_API_V2", "route": WRITER_ENDPOINT,
        "symbol": "EUR/USD", "interval": "5min",
        "timezone": "UTC", "price_side": "MID",
        "claim_scope": "EXACT_PROVIDER_M5_SESSION_CLOSURE",
        "effective_start_utc": "2026-11-07T00:00:00+00:00",
        "effective_end_utc": "2026-11-11T00:00:00+00:00",
        "closed_h4_starts_utc": [SATURDAY, SUNDAY],
        "sequence": 1, "parent_snapshot_sha256": None,
        "issued_at_utc": "2026-11-07T00:00:00+00:00",
    }
    d.update(kw)
    return d


def raw(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")


def candidate(data=None, *, raw_content=None, **kw):
    b = raw(payload() if data is None else data) if raw_content is None else raw_content
    fields = {
        "raw_json": b, "declared_sha256": sha256(b).hexdigest(),
        "publication_reference_id": REF,
        "publication_url": OFFICIAL_REFERENCES[REF].url,
        "captured_at_utc": "2026-11-12T11:00:00+00:00",
    }
    fields.update(kw)
    return SnapshotCandidate(**fields)


def check(c=None, gaps=(SATURDAY,SUNDAY), *, prior=None, now=NOW):
    return inspect_calendar_candidate(
        candidate() if c is None else c, gaps,
        reviewed_at_utc=now, prior_receipt=prior,
    )


class CalendarCustodyTests(TestCase):
    def test_01_sha_does_not_authenticate_publisher(self):
        r=check()
        self.assertTrue(r.raw_bytes_match_declared_sha256)
        self.assertFalse(r.publisher_signature_verified)

    def test_02_readonly_admission_receipt_schema(self):
        self.assertEqual(check().schema, RECEIPT)

    def test_03_p093_v2_page_not_5min_specific_calendar(self):
        self.assertEqual(check().status,
                         "P094_PUBLIC_PAGE_SCOPE_NOT_EXACT_PROVIDER_M5_CLOSURE")

    def test_04_official_public_reference_scope(self):
        self.assertEqual(check().documented_reference_scope,
                         "FEED_SERVICE_AVAILABILITY")

    def test_05_even_exact_gap_overlap_no_waiver(self):
        r=check()
        self.assertEqual(r.exact_label_overlap_count,2)
        self.assertFalse(r.automatic_weekend_gap_waiver)

    def test_06_both_sat_sun_counted_without_rights(self):
        r=check()
        self.assertEqual(r.submitted_gap_count,2)
        self.assertFalse(r.actual_provider_m5_session_calendar_verified)

    def test_07_empty_gap_not_authentication(self):
        self.assertEqual(check(gaps=()).status,
                         "P094_NO_GAP_RESEARCH_RECEIPT_ONLY")

    def test_08_24_7_service_scope_cannot_prove_bar_closure(self):
        d=payload(claim_scope="FEED_SERVICE_AVAILABILITY")
        self.assertEqual(check(candidate(d)).status,
                         "P094_SERVICE_AVAILABILITY_NOT_M5_SESSION_EVIDENCE")

    def test_09_missing_one_gap_denied(self):
        d=payload(closed_h4_starts_utc=[SATURDAY])
        self.assertEqual(check(candidate(d)).status,
                         "P094_INCOMPLETE_CANDIDATE_CLOSURE_COVERAGE")

    def test_10_only_sunday_missing_denied(self):
        d=payload(closed_h4_starts_utc=[SATURDAY])
        self.assertEqual(check(candidate(d),gaps=(SUNDAY,)).exact_label_overlap_count,0)

    def test_11_weekday_gap_not_waived(self):
        self.assertEqual(check(gaps=(MONDAY,)).status,
                         "P094_INCOMPLETE_CANDIDATE_CLOSURE_COVERAGE")

    def test_12_canonical_sha_recomputed_exactly(self):
        c=candidate()
        self.assertEqual(check(c).snapshot_sha256,sha256(c.raw_json).hexdigest())

    def test_13_untampered_canonical_metadata_checked(self):
        self.assertTrue(check().canonical_json_and_scope_valid)

    def test_14_never_trust_self_asserted_feed_mapping(self):
        self.assertFalse(check().actual_mfx_feed_version_verified)

    def test_15_never_grant_data_license(self):
        self.assertFalse(check().separately_licensed_data_usage_verified)

    def test_16_never_claim_html_authenticated(self):
        self.assertFalse(check().published_page_content_sha_verified)

    def test_17_never_claim_external_witness(self):
        self.assertFalse(check().trusted_external_monotonic_witness_verified)

    def test_18_never_claim_owner_go(self):
        self.assertFalse(check().owner_calendar_exception_go)

    def test_19_native_h4_and_d1_never_change(self):
        r=check()
        self.assertFalse(r.may_replace_native_h4)
        self.assertFalse(r.may_reduce_native_h4_requests)
        self.assertFalse(r.may_change_sydney_native_d1)

    def test_20_numeric_signals_and_broker_denied(self):
        r=check()
        self.assertFalse(r.numeric_buy_sell_authorized)
        self.assertFalse(r.broker_orders_authorized)

    def test_21_zero_io_even_on_candidate(self):
        r=check()
        self.assertEqual((r.network_calls,r.drive_writes,r.broker_orders),(0,0,0))

    def test_22_zero_provider_ohlc_disclosed(self):
        self.assertNotIn("1.10000",repr(check()))

    def test_23_wrong_candidate_type(self):
        with self.assertRaisesRegex(ValueError,"CANDIDATE_TYPED"):
            check({})

    def test_24_wrong_raw_type(self):
        with self.assertRaisesRegex(ValueError,"RAW_CONTENT"):
            check(replace(candidate(),raw_json="{}"))

    def test_25_raw_content_tamper_sha_detected(self):
        c=candidate()
        with self.assertRaisesRegex(ValueError,"RAW_CONTENT"):
            check(replace(c,raw_json=c.raw_json+b" "))

    def test_26_declared_digest_wrong(self):
        with self.assertRaisesRegex(ValueError,"RAW_CONTENT"):
            check(replace(candidate(),declared_sha256="f"*64))

    def test_27_digest_invalid_case(self):
        with self.assertRaisesRegex(ValueError,"RAW_CONTENT"):
            check(replace(candidate(),declared_sha256="A"*64))

    def test_28_digest_bool_denied(self):
        with self.assertRaisesRegex(ValueError,"RAW_CONTENT"):
            check(replace(candidate(),declared_sha256=True))

    def test_29_empty_raw_denied(self):
        with self.assertRaisesRegex(ValueError,"RAW_CONTENT"):
            check(candidate(raw_content=b""))

    def test_30_over_limit_denied(self):
        with self.assertRaisesRegex(ValueError,"RAW_CONTENT"):
            check(candidate(raw_content=b" "* (MAX_BYTES+1)))

    def test_31_duplicate_json_key_denied(self):
        b=b'{"x":1,"x":2}'
        with self.assertRaisesRegex(ValueError,"DUPLICATE_JSON_KEY"):
            check(candidate(raw_content=b))

    def test_32_robust_to_invalid_utf8(self):
        with self.assertRaisesRegex(ValueError,"CANONICAL_JSON"):
            check(candidate(raw_content=b"\\xff"))

    def test_33_noncanonical_spacing_denied(self):
        with self.assertRaisesRegex(ValueError,"CANONICAL_JSON"):
            check(candidate(raw_content=raw(payload())+b"\n"))

    def test_34_unknown_json_field_denied(self):
        with self.assertRaisesRegex(ValueError,"CANONICAL_JSON"):
            check(candidate(payload(extra=True)))

    def test_35_wrong_issuer_denied(self):
        with self.assertRaisesRegex(ValueError,"EXACT_PROVIDER"):
            check(candidate(payload(issuer="OANDA")))

    def test_36_wrong_product_denied(self):
        with self.assertRaisesRegex(ValueError,"EXACT_PROVIDER"):
            check(candidate(payload(product_id="FX_SPOT_PLUS")))

    def test_37_wrong_feed_version_denied(self):
        with self.assertRaisesRegex(ValueError,"EXACT_PROVIDER"):
            check(candidate(payload(feed_version="FOREX_API_V1")))

    def test_38_wrong_endpoint_denied(self):
        with self.assertRaisesRegex(ValueError,"EXACT_PROVIDER"):
            check(candidate(payload(route="https://evil.example/price")))

    def test_39_wrong_symbol_denied(self):
        with self.assertRaisesRegex(ValueError,"EXACT_PROVIDER"):
            check(candidate(payload(symbol="GBP/USD")))

    def test_40_wrong_interval_denied(self):
        with self.assertRaisesRegex(ValueError,"EXACT_PROVIDER"):
            check(candidate(payload(interval="4h")))

    def test_41_wrong_timezone_denied(self):
        with self.assertRaisesRegex(ValueError,"EXACT_PROVIDER"):
            check(candidate(payload(timezone="Australia/Sydney")))

    def test_42_broker_bid_ask_not_mid_source_denied(self):
        with self.assertRaisesRegex(ValueError,"EXACT_PROVIDER"):
            check(candidate(payload(price_side="BID")))

    def test_43_wrong_reference_url_denied(self):
        with self.assertRaisesRegex(ValueError,"SOURCE_REFERENCE"):
            check(replace(candidate(),publication_url="https://support.twelvedata.com.evil.invalid/"))

    def test_44_reference_id_wrong_source_denied(self):
        with self.assertRaisesRegex(ValueError,"SOURCE_REFERENCE"):
            check(replace(candidate(),publication_reference_id="OANDA_US_FX_HOURS"))

    def test_45_modified_writer_sha_denied(self):
        with self.assertRaisesRegex(ValueError,"SOURCE_REFERENCE"):
            check(replace(candidate(),writer_blob_sha="0"*40))

    def test_46_future_capture_denied(self):
        with self.assertRaisesRegex(ValueError,"CAPTURE_AFTER"):
            check(replace(candidate(),captured_at_utc="2026-11-12T13:00:00+00:00"))

    def test_47_naive_capture_denied(self):
        with self.assertRaises(ValueError):
            check(replace(candidate(),captured_at_utc="2026-11-12T11:00:00"))

    def test_48_wrong_review_timezone_denied(self):
        with self.assertRaises(ValueError):
            check(now="2026-11-12T19:00:00+07:00")

    def test_49_future_gap_rejected(self):
        with self.assertRaisesRegex(ValueError,"GAP_ALIGNMENT"):
            check(gaps=("2026-11-12T12:00:00+00:00",))

    def test_50_unsorted_gap_rejected(self):
        with self.assertRaisesRegex(ValueError,"GAP_ALIGNMENT"):
            check(gaps=(SUNDAY,SATURDAY))

    def test_51_duplicate_gap_rejected(self):
        with self.assertRaisesRegex(ValueError,"GAP_ALIGNMENT"):
            check(gaps=(SATURDAY,SATURDAY))

    def test_52_unaligned_h4_gap_rejected(self):
        with self.assertRaisesRegex(ValueError,"GAP_ALIGNMENT"):
            check(gaps=("2026-11-07T09:00:00+00:00",))

    def test_53_wrong_gap_container_rejected(self):
        with self.assertRaisesRegex(ValueError,"BOUNDED_TYPED"):
            check(gaps=[SATURDAY])

    def test_54_wrong_closure_label_type(self):
        with self.assertRaises(ValueError):
            check(candidate(payload(closed_h4_starts_utc=[True])))

    def test_55_unsorted_closure_labels_rejected(self):
        with self.assertRaisesRegex(ValueError,"CLOSURE_GRID"):
            check(candidate(payload(closed_h4_starts_utc=[SUNDAY,SATURDAY])))

    def test_56_duplicate_closure_labels_rejected(self):
        with self.assertRaisesRegex(ValueError,"CLOSURE_GRID"):
            check(candidate(payload(closed_h4_starts_utc=[SATURDAY,SATURDAY])))

    def test_57_closure_outside_claimed_time_range(self):
        with self.assertRaisesRegex(ValueError,"CLOSURE_GRID"):
            check(candidate(payload(closed_h4_starts_utc=["2026-11-11T00:00:00+00:00"])))

    def test_58_invalid_window_order(self):
        with self.assertRaisesRegex(ValueError,"WINDOW_BOUNDS"):
            check(candidate(payload(effective_end_utc="2026-11-07T00:00:00+00:00")))

    def test_59_issued_after_capture_denied(self):
        with self.assertRaisesRegex(ValueError,"WINDOW_BOUNDS"):
            check(candidate(payload(issued_at_utc="2026-11-12T12:00:00+00:00")))

    def test_60_wrong_sequence_boolean_denied(self):
        with self.assertRaisesRegex(ValueError,"SEQUENCE_INVALID"):
            check(candidate(payload(sequence=True)))

    def test_61_genesis_parent_spoof_denied(self):
        with self.assertRaisesRegex(ValueError,"GENESIS_PARENT"):
            check(candidate(payload(parent_snapshot_sha256="a"*64)))

    def test_62_non_genesis_no_prior_denied(self):
        with self.assertRaisesRegex(ValueError,"SELF_ASSERTED_CHAIN"):
            check(candidate(payload(sequence=2,parent_snapshot_sha256="b"*64)))

    def test_63_valid_self_reported_chain_not_trusted_witness(self):
        p=check()
        d=payload(sequence=2,parent_snapshot_sha256=p.snapshot_sha256,
                  effective_end_utc="2026-11-12T00:00:00+00:00")
        c=candidate(d,captured_at_utc="2026-11-12T11:30:00+00:00")
        r=check(c,prior=p)
        self.assertTrue(r.chain_structurally_consistent)
        self.assertFalse(r.trusted_external_monotonic_witness_verified)

    def test_64_wrong_parent_sha_in_chain_denied(self):
        p=check()
        d=payload(sequence=2,parent_snapshot_sha256="a"*64)
        with self.assertRaisesRegex(ValueError,"SELF_ASSERTED_CHAIN"):
            check(candidate(d,captured_at_utc="2026-11-12T11:30:00+00:00"),prior=p)

    def test_65_sequence_skipping_denied(self):
        p=check()
        d=payload(sequence=3,parent_snapshot_sha256=p.snapshot_sha256)
        with self.assertRaisesRegex(ValueError,"SELF_ASSERTED_CHAIN"):
            check(candidate(d,captured_at_utc="2026-11-12T11:30:00+00:00"),prior=p)

    def test_66_chain_backward_effective_end_denied(self):
        p=check()
        d=payload(sequence=2,parent_snapshot_sha256=p.snapshot_sha256,
                  effective_end_utc="2026-11-10T00:00:00+00:00")
        with self.assertRaisesRegex(ValueError,"SELF_ASSERTED_CHAIN"):
            check(candidate(d,captured_at_utc="2026-11-12T11:30:00+00:00"),prior=p)

    def test_67_chain_nonmonotonic_capture_denied(self):
        p=check()
        d=payload(sequence=2,parent_snapshot_sha256=p.snapshot_sha256)
        with self.assertRaisesRegex(ValueError,"SELF_ASSERTED_CHAIN"):
            check(candidate(d,captured_at_utc="2026-11-12T10:00:00+00:00"),prior=p)

    def test_68_extra_untrusted_source_cannot_grant_go(self):
        p=check()
        self.assertFalse(p.market_session_or_DST_exception_granted if
                         hasattr(p,"market_session_or_DST_exception_granted") else
                         p.owner_calendar_exception_go)

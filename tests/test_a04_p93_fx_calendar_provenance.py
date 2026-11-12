"""A04/P0.93: official-reference scope != authenticated feed-calendar waiver."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from tools.mfx_fx_calendar_provenance import (
    SCHEMA, OFFICIAL_REFERENCES, WRITER_BLOB_SHA, WRITER_ENDPOINT,
    review_fx_calendar_provenance,
)

UTC = timezone.utc
NOW = datetime(2026,11,12,12,tzinfo=UTC)
SUNDAY = "2026-11-08T08:00:00+00:00"
SATURDAY = "2026-11-07T08:00:00+00:00"
MONDAY = "2026-11-09T08:00:00+00:00"
TD = "TWELVE_DATA_FOREX_V2"
TZ = "TWELVE_DATA_FOREX_TZ"
OA = "OANDA_US_FX_HOURS"
CME = "CME_FX_SPOT_PLUS_2026"


def review(source_ids=(TD,OA), gaps=(SATURDAY,SUNDAY), *,
           asof=NOW, sha=WRITER_BLOB_SHA):
    return review_fx_calendar_provenance(
        source_ids, gaps, reviewed_asof_utc=asof,
        source_writer_blob_sha=sha,
    )


class CalendarProvenanceTests(TestCase):
    def test_01_fixed_four_actual_official_source_ids(self):
        self.assertEqual(set(OFFICIAL_REFERENCES),{TD,TZ,OA,CME})

    def test_02_calendar_policy_provenance_schema(self):
        self.assertEqual(review().schema,SCHEMA)

    def test_03_twelve_data_forex_v2_is_service_availability(self):
        r=review((TD,), (SATURDAY,))
        self.assertEqual(r.source_scopes,("FEED_SERVICE_AVAILABILITY",))
        self.assertEqual(r.status,"P093_24_7_FEED_SERVICE_NOT_M5_CANDLE_SLA_NO_WAIVER")

    def test_04_twelve_data_document_does_not_prove_our_feed_version(self):
        r=review((TD,), (SATURDAY,))
        self.assertFalse(r.actual_mfx_feed_v2_subscription_verified)

    def test_05_24_7_does_not_certify_every_5min_bar(self):
        self.assertFalse(review((TD,), (SATURDAY,)).exact_provider_m5_weekend_bar_sla_verified)

    def test_06_oanda_broker_not_provider_data_calendar(self):
        r=review((OA,), (SATURDAY,))
        self.assertEqual(r.status,"P093_NO_MATCHED_FEED_VERSION_CANNOT_WAIVE_GAP")
        self.assertFalse(r.first_party_twelve_data_v2_reference_present)

    def test_07_cme_venue_not_provider_data_calendar(self):
        r=review((CME,), (SUNDAY,))
        self.assertEqual(r.source_scopes,("VENUE_FX_SPOT_PLUS_SESSION",))
        self.assertFalse(r.official_calendar_exception_for_each_gap_verified)

    def test_08_feed_and_broker_scope_divergence(self):
        r=review((TD,OA), (SATURDAY,))
        self.assertEqual(r.status,"P093_DELIVERY_VS_EXECUTION_SCOPE_DIVERGENCE_NO_WAIVER")
        self.assertTrue(r.scope_mismatch_requires_separate_review)

    def test_09_feed_and_cme_scope_divergence(self):
        self.assertTrue(review((TD,CME), (SUNDAY,)).scope_mismatch_requires_separate_review)

    def test_10_oanda_and_cme_without_feed_cannot_waive(self):
        self.assertEqual(review((OA,CME),(SATURDAY,)).status,
                         "P093_NO_MATCHED_FEED_VERSION_CANNOT_WAIVE_GAP")

    def test_11_all_sources_dont_waive_weekend(self):
        r=review((TD,TZ,OA,CME), (SATURDAY,SUNDAY))
        self.assertEqual(r.utc_weekend_gap_candidates,2)
        self.assertFalse(r.automatic_weekend_gap_waiver_allowed)

    def test_12_weekday_gap_never_waived(self):
        r=review((TD,OA),(MONDAY,))
        self.assertEqual(r.utc_weekday_gap_candidates,1)
        self.assertFalse(r.market_session_or_DST_exception_granted)

    def test_13_utc_weekend_only_candidate_not_new_york_session_proof(self):
        r=review((TD,OA), (SUNDAY,))
        self.assertEqual(r.utc_weekend_gap_candidates,1)
        self.assertFalse(r.official_calendar_exception_for_each_gap_verified)

    def test_14_factual_references_without_gaps_never_upgrade(self):
        r=review((TD,OA), ())
        self.assertEqual(r.status,"P093_REFERENCES_ONLY_NO_MISSING_H4_SLOT_OBSERVED")
        self.assertFalse(r.source_h4_cutover_authorized)

    def test_15_source_timestamp_default_sydney_not_delivery_sla(self):
        r=review((TZ,), (MONDAY,))
        self.assertEqual(r.source_scopes,("DATA_TIMESTAMP_DEFAULT",))
        self.assertFalse(r.exact_provider_m5_weekend_bar_sla_verified)

    def test_16_mfx_writer_endpoint_pinned_without_vendor_call(self):
        r=review()
        self.assertEqual(r.mfx_writer_endpoint,WRITER_ENDPOINT)
        self.assertEqual(r.mfx_writer_symbol,"EUR/USD")
        self.assertEqual(r.mfx_writer_interval,"5min")
        self.assertEqual(r.mfx_writer_timezone,"UTC")
        self.assertEqual(r.writer_git_blob_sha,WRITER_BLOB_SHA)

    def test_17_never_licenses_bid_ask_or_numeric_strategy(self):
        self.assertFalse(review().licensed_bid_ask_or_numeric_fx_signals_authorized)

    def test_18_never_enables_h4_native_reduction(self):
        r=review()
        self.assertFalse(r.may_reduce_native_h4_requests)
        self.assertFalse(r.source_h4_cutover_authorized)

    def test_19_sydney_d1_and_broker_still_locked(self):
        r=review()
        self.assertFalse(r.may_change_sydney_native_d1)
        self.assertFalse(r.broker_orders_authorized)

    def test_20_no_document_digest_or_authenticated_publication(self):
        r=review()
        self.assertFalse(r.publisher_source_html_digest_verified)
        self.assertFalse(r.independently_authenticated_publication_asof)
        self.assertTrue(r.source_document_observation_not_authenticated)

    def test_21_unmodified_inputs(self):
        a=(TD,OA); b=(SATURDAY,SUNDAY)
        review(a,b)
        self.assertEqual(a,(TD,OA))
        self.assertEqual(b,(SATURDAY,SUNDAY))

    def test_22_zero_provider_calls_or_drive_mutations(self):
        r=review()
        self.assertEqual((r.provider_calls_by_this_module,
                          r.drive_writes_by_this_module,
                          r.broker_orders_by_this_module),(0,0,0))

    def test_23_reject_list_source(self):
        with self.assertRaisesRegex(ValueError,"SOURCE_IDS"):
            review([TD], (SATURDAY,))

    def test_24_reject_empty_source(self):
        with self.assertRaisesRegex(ValueError,"SOURCE_IDS"):
            review((), (SATURDAY,))

    def test_25_reject_duplicate_source(self):
        with self.assertRaisesRegex(ValueError,"SOURCE_IDS"):
            review((TD,TD), (SATURDAY,))

    def test_26_reject_unknown_or_impersonated_source(self):
        for bad in ("UNOFFICIAL_FX_CALENDAR","TWELVE_DATA_FOREX_V3","../../"):
            with self.subTest(bad=bad),self.assertRaisesRegex(ValueError,"SOURCE_IDS"):
                review((bad,), (SATURDAY,))

    def test_27_bad_source_int_or_bool(self):
        with self.assertRaisesRegex(ValueError,"SOURCE_IDS"):
            review((True,), (SATURDAY,))

    def test_28_reject_wrong_writer_sha(self):
        with self.assertRaisesRegex(ValueError,"WRITER_SOURCE_BLOB"):
            review(sha="f"*40)

    def test_29_reject_naive_review(self):
        with self.assertRaisesRegex(ValueError,"UTC_OR_WRITER"):
            review(asof=datetime(2026,11,12,12))

    def test_30_reject_non_utc_timezone(self):
        with self.assertRaisesRegex(ValueError,"UTC_OR_WRITER"):
            review(asof=datetime(2026,11,12,19,tzinfo=timezone(timedelta(hours=7))))

    def test_31_reject_list_gaps(self):
        with self.assertRaisesRegex(ValueError,"BOUNDED_TYPED_GAP"):
            review(gaps=[SATURDAY])

    def test_32_reject_wrong_h4_alignment(self):
        with self.assertRaisesRegex(ValueError,"EXACT_4H"):
            review(gaps=("2026-11-07T07:00:00+00:00",))

    def test_33_reject_naive_or_noncanonical_iso(self):
        for bad in ("2026-11-07T08:00:00","2026-11-07 08:00:00+00:00"):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                review(gaps=(bad,))

    def test_34_reject_duplicate_gaps(self):
        with self.assertRaisesRegex(ValueError,"CLOCK_ORDER"):
            review(gaps=(SATURDAY,SATURDAY))

    def test_35_reject_unsorted_gaps(self):
        with self.assertRaisesRegex(ValueError,"CLOCK_ORDER"):
            review(gaps=(SUNDAY,SATURDAY))

    def test_36_reject_future_gap_even_if_publisher_claim(self):
        with self.assertRaisesRegex(ValueError,"CLOCK_ORDER"):
            review(gaps=("2026-11-12T12:00:00+00:00",))

    def test_37_reject_more_than_72_gap_labels(self):
        seq=tuple((datetime(2026,11,1,tzinfo=UTC)+i*timedelta(hours=4)).isoformat()
                  for i in range(73))
        with self.assertRaisesRegex(ValueError,"BOUNDED_TYPED_GAP"):
            review(gaps=seq,asof=datetime(2026,12,1,tzinfo=UTC))

    def test_38_reject_span_over_72_slots(self):
        with self.assertRaisesRegex(ValueError,"CLOCK_ORDER"):
            review(gaps=(SATURDAY,"2026-11-22T08:00:00+00:00"),
                   asof=datetime(2026,12,1,tzinfo=UTC))

    def test_39_reject_source_doc_future_asof(self):
        with self.assertRaisesRegex(ValueError,"DOCUMENT_POSTDATES"):
            review((TD,),(),asof=datetime(2025,6,1,tzinfo=UTC))

    def test_40_all_four_official_urls_https_only(self):
        for d in OFFICIAL_REFERENCES.values():
            self.assertTrue(d.url.startswith("https://"))
            self.assertNotIn("api_key",d.url)
            self.assertNotIn("localhost",d.url)

    def test_41_legal_rights_not_proven_by_public_hours(self):
        self.assertFalse(review((TD,OA,CME),(SATURDAY,)).licensed_bid_ask_or_numeric_fx_signals_authorized)

    def test_42_false_authorization_fields_even_when_no_gap(self):
        r=review((TD,),())
        self.assertFalse(r.market_session_or_DST_exception_granted)
        self.assertFalse(r.automatic_weekend_gap_waiver_allowed)

    def test_43_source_reference_objects_immutable(self):
        d=OFFICIAL_REFERENCES[TD]
        with self.assertRaises(Exception):
            d.source_id="FAKE"

    def test_44_source_count_le4(self):
        with self.assertRaisesRegex(ValueError,"SOURCE_IDS"):
            review((TD,TZ,OA,CME,TD), (SATURDAY,))

    def test_45_no_provider_request_or_candle_ohlc_in_receipt(self):
        r=review()
        self.assertNotIn("1.10000",repr(r))
        self.assertNotIn("MFX_TWELVE_DATA_API_KEY",repr(r))

"""A04/P0.92 pure H4 qualification gate, weekend/weekday, SHA and no-GO."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from tools.mfx_h4_qualification_gate import (
    SCHEMA, H4, ReviewedH4Evidence, review_h4_qualification,
)

UTC = timezone.utc
REAL_HEAD = "2676a0f5695c5639fb5a9d2800debb6d40cb3c0343e9d482144b3e3472f42ea1"
FIRST = datetime(2026, 11, 10, 20, tzinfo=UTC)


def stamp(x: datetime) -> str:
    return x.isoformat()


def native(x: datetime) -> str:
    return x.strftime("%Y-%m-%d %H:%M:%S")


def reviewed_p91() -> ReviewedH4Evidence:
    """Only 9 labels reconstructed from authenticated consecutive-grid receipt.

    The current 41/41 SHA is an externally reviewed historical P0.91 audit,
    NOT freshly fetched raw Drive blobs in these tests.
    """
    labels = tuple(FIRST + i * H4 for i in range(9))
    return ReviewedH4Evidence(
        audit_run_id=43138482666, audit_attempt=5,
        audit_completed_utc=datetime(2026,11,12,11,19,20,tzinfo=UTC),
        m5_latest_hour_utc=datetime(2026,11,12,10,tzinfo=UTC),
        m5_head_sha256=REAL_HEAD,
        m5_manifest_chunk_pairs_verified=41, m5_closed_bars=492,
        m5_full_bounded_sha_verified=True,
        native_manifest_chunk_pairs_verified=8, native_closed_bars=126,
        native_full_bounded_sha_verified=True,
        complete_48xm5_h4_starts_utc=tuple(map(stamp,labels)),
        native_h4_starts_utc_in_or_around_span=tuple(map(native,labels)),
        exact_ohlc_matches=9, ohlc_mismatches=0,
        native_missing_for_complete_m5=0,
        interior_incomplete_h4_windows=0,
        boundary_partial_h4_windows=2,
    )


def synthetic(start: datetime, length: int=44,
              omitted_shadow: frozenset[int]=frozenset(),
              omitted_native: frozenset[int]=frozenset(),
              pairs: int=240) -> ReviewedH4Evidence:
    all_slots = tuple(start+i*H4 for i in range(length))
    shadow = tuple(x for i,x in enumerate(all_slots) if i not in omitted_shadow)
    native_labels = tuple(x for i,x in enumerate(all_slots)
                          if i not in omitted_native)
    # Count only labels in retained shadow extent (same as P0.70).
    span = set(shadow)
    native_in = set(native_labels)
    matches = len(span & native_in)
    return replace(
        reviewed_p91(), audit_run_id=888888, audit_attempt=1,
        audit_completed_utc=start+timedelta(days=14),
        m5_latest_hour_utc=start+timedelta(days=13),
        m5_head_sha256="a"*64,
        m5_manifest_chunk_pairs_verified=pairs, m5_closed_bars=12*pairs,
        native_closed_bars=240,
        complete_48xm5_h4_starts_utc=tuple(map(stamp,shadow)),
        native_h4_starts_utc_in_or_around_span=tuple(map(native,native_labels)),
        exact_ohlc_matches=matches, ohlc_mismatches=0,
        native_missing_for_complete_m5=len(span-native_in),
        interior_incomplete_h4_windows=0,
        boundary_partial_h4_windows=0,
    )


class H4QualificationTests(TestCase):
    def test_01_p091_9_not_30(self):
        r=review_h4_qualification(reviewed_p91())
        self.assertEqual((r.h4_exact_matches,r.h4_complete_m5_windows),(9,9))
        self.assertEqual(r.status,"P092_NO_GO_INSUFFICIENT_30_WINDOWS_OR_7_DAYS")

    def test_02_p091_exact_historical_sha(self):
        r=review_h4_qualification(reviewed_p91())
        self.assertEqual(r.audit_head_sha256,REAL_HEAD)
        self.assertEqual(r.audit_run_id,43138482666)

    def test_03_p091_boundary_partial_allowed_not_promoted(self):
        r=review_h4_qualification(reviewed_p91())
        self.assertEqual(r.h4_boundary_partial_ignored_for_threshold,2)
        self.assertEqual(r.h4_interior_missing_m5_windows,0)
        self.assertFalse(r.h4_observation_threshold_met_for_research_only)

    def test_04_44_full_windows_7d_still_owner_blocked(self):
        r=review_h4_qualification(synthetic(FIRST))
        self.assertTrue(r.h4_at_least_30_exact)
        self.assertTrue(r.h4_at_least_7_real_days)
        self.assertTrue(r.h4_observation_threshold_met_for_research_only)
        self.assertEqual(r.status,"P092_REVIEW_THRESHOLD_ONLY_SESSION_AND_OWNER_GO_REQUIRED")
        self.assertFalse(r.may_replace_native_h4)

    def test_05_weekend_dual_absence_cannot_auto_waive(self):
        fri=datetime(2026,11,6,20,tzinfo=UTC)
        e=synthetic(fri,omitted_shadow=frozenset(range(1,13)),
                    omitted_native=frozenset(range(1,13)))
        r=review_h4_qualification(e)
        self.assertEqual(r.h4_dual_absent_weekend_candidates,12)
        self.assertEqual(r.h4_dual_absent_weekday_unexplained,0)
        self.assertEqual(r.status,"P092_NO_GO_UNVERIFIED_WEEKEND_SESSION_CANDIDATE")
        self.assertFalse(r.independent_market_session_calendar_verified)

    def test_06_weekday_dual_absence_explained_by_neither_never_waived(self):
        e=synthetic(FIRST,omitted_shadow=frozenset({2,3}),
                    omitted_native=frozenset({2,3}))
        r=review_h4_qualification(e)
        self.assertEqual(r.h4_dual_absent_weekday_unexplained,2)
        self.assertEqual(r.status,"P092_NO_GO_UNEXPLAINED_WEEKDAY_DUAL_ABSENCE")

    def test_07_native_only_4h_window_blocks(self):
        e=synthetic(FIRST,omitted_shadow=frozenset({8}))
        r=review_h4_qualification(e)
        self.assertEqual(r.h4_native_only_slots,1)
        self.assertEqual(r.status,"P092_NO_GO_SOURCE_MISMATCH_OR_INTERIOR_GAP")

    def test_08_m5_only_window_blocks(self):
        e=synthetic(FIRST,omitted_native=frozenset({8}))
        r=review_h4_qualification(e)
        self.assertEqual(r.h4_m5_only_slots,1)
        self.assertEqual(r.status,"P092_NO_GO_SOURCE_MISMATCH_OR_INTERIOR_GAP")

    def test_09_ohlc_mismatch_blocks(self):
        e=synthetic(FIRST)
        e=replace(e,ohlc_mismatches=1,exact_ohlc_matches=e.exact_ohlc_matches-1)
        self.assertEqual(review_h4_qualification(e).status,
                         "P092_NO_GO_SOURCE_MISMATCH_OR_INTERIOR_GAP")

    def test_10_interior_m5_gap_blocks(self):
        e=replace(synthetic(FIRST),interior_incomplete_h4_windows=1)
        self.assertEqual(review_h4_qualification(e).status,
                         "P092_NO_GO_SOURCE_MISMATCH_OR_INTERIOR_GAP")

    def test_11_only_30_consecutive_under_7d_denied(self):
        r=review_h4_qualification(synthetic(FIRST,length=30))
        self.assertTrue(r.h4_at_least_30_exact)
        self.assertFalse(r.h4_at_least_7_real_days)

    def test_12_43_windows_reach_exactly_7d_boundary(self):
        r=review_h4_qualification(synthetic(FIRST,length=43))
        self.assertEqual(r.h4_span_seconds,7*86400)
        self.assertTrue(r.h4_at_least_7_real_days)

    def test_13_time_span_calendar_hours_not_number_of_weekdays(self):
        r=review_h4_qualification(synthetic(FIRST,length=44))
        self.assertGreater(r.h4_span_seconds,7*86400)

    def test_14_unsafe_cutover_flags_all_false(self):
        r=review_h4_qualification(synthetic(FIRST))
        self.assertFalse(r.h4_production_cutover_authorized)
        self.assertFalse(r.may_reduce_native_h4_requests)
        self.assertFalse(r.may_replace_native_h4)
        self.assertFalse(r.may_change_sydney_native_d1)
        self.assertFalse(r.numeric_fx_buy_sell_authorized)
        self.assertFalse(r.broker_orders_authorized)

    def test_15_no_external_custody_or_legal_approval(self):
        r=review_h4_qualification(synthetic(FIRST))
        self.assertFalse(r.independently_authenticated_by_this_module)
        self.assertFalse(r.independent_market_session_calendar_verified)
        self.assertFalse(r.actual_vendor_session_and_data_rights_verified)
        self.assertFalse(r.external_monotonic_witness_verified)

    def test_16_pure_no_cloud_calls(self):
        r=review_h4_qualification(synthetic(FIRST))
        self.assertEqual((r.provider_calls_by_this_module,
                          r.drive_writes_by_this_module,
                          r.broker_orders_by_this_module),(0,0,0))

    def test_17_no_sensitive_ohlc(self):
        self.assertNotIn("1.1000",repr(review_h4_qualification(synthetic(FIRST))))

    def test_18_wrong_container_denied(self):
        with self.assertRaisesRegex(ValueError,"TYPED_REVIEWED"):
            review_h4_qualification({})

    def test_19_bool_run_id_denied(self):
        with self.assertRaisesRegex(ValueError,"AUDIT_SHA_CLOCK"):
            review_h4_qualification(replace(reviewed_p91(),audit_run_id=True))

    def test_20_zero_attempt_denied(self):
        with self.assertRaisesRegex(ValueError,"AUDIT_SHA_CLOCK"):
            review_h4_qualification(replace(reviewed_p91(),audit_attempt=0))

    def test_21_negative_paired_sha_denied(self):
        with self.assertRaisesRegex(ValueError,"AUDIT_SHA_CLOCK"):
            review_h4_qualification(replace(reviewed_p91(),
                                  m5_manifest_chunk_pairs_verified=-1))

    def test_22_12_m5_per_hour_invariant(self):
        with self.assertRaisesRegex(ValueError,"AUDIT_SHA_CLOCK"):
            review_h4_qualification(replace(reviewed_p91(),m5_closed_bars=491))

    def test_23_shas_must_be_lowercase_hex(self):
        for x in ("x"*64,"F"*64,"a"*63):
            with self.subTest(x=x[:5]),self.assertRaisesRegex(ValueError,"AUDIT_SHA_CLOCK"):
                review_h4_qualification(replace(reviewed_p91(),m5_head_sha256=x))

    def test_24_not_fully_shaverified_rejected(self):
        with self.assertRaisesRegex(ValueError,"AUDIT_SHA_CLOCK"):
            review_h4_qualification(replace(reviewed_p91(),
                             m5_full_bounded_sha_verified=False))

    def test_25_native_unverified_rejected(self):
        with self.assertRaisesRegex(ValueError,"AUDIT_SHA_CLOCK"):
            review_h4_qualification(replace(reviewed_p91(),
                             native_full_bounded_sha_verified=False))

    def test_26_naive_utc_denied(self):
        with self.assertRaisesRegex(ValueError,"AUDIT_SHA_CLOCK"):
            review_h4_qualification(replace(reviewed_p91(),
                             audit_completed_utc=datetime(2026,11,12,11,19,20)))

    def test_27_timezone_offset_denied(self):
        x=reviewed_p91()
        with self.assertRaisesRegex(ValueError,"AUDIT_SHA_CLOCK"):
            review_h4_qualification(replace(x,
                 m5_latest_hour_utc=x.m5_latest_hour_utc.astimezone(
                      timezone(timedelta(hours=7)))))

    def test_28_future_unclosed_m5_hour_denied(self):
        with self.assertRaisesRegex(ValueError,"AUDIT_SHA_CLOCK"):
            review_h4_qualification(replace(reviewed_p91(),
                       audit_completed_utc=datetime(2026,11,12,10,tzinfo=UTC)))

    def test_29_future_h4_window_denied(self):
        x=reviewed_p91()
        extra=stamp(datetime(2026,11,12,12,tzinfo=UTC))
        with self.assertRaisesRegex(ValueError,"SOURCE_PARITY_COUNTER"):
            review_h4_qualification(replace(x,
                       complete_48xm5_h4_starts_utc=x.complete_48xm5_h4_starts_utc+(extra,),
                       exact_ohlc_matches=x.exact_ohlc_matches+1))

    def test_30_duplicate_h4_label_denied(self):
        x=reviewed_p91()
        with self.assertRaises(ValueError):
            review_h4_qualification(replace(x,
                complete_48xm5_h4_starts_utc=(x.complete_48xm5_h4_starts_utc[0],)*2))

    def test_31_wrong_h4_offset_denied(self):
        x=reviewed_p91()
        labels=list(x.complete_48xm5_h4_starts_utc)
        labels[3]="2026-11-11T15:00:00+07:00"
        with self.assertRaises(ValueError):
            review_h4_qualification(replace(x,complete_48xm5_h4_starts_utc=tuple(labels)))

    def test_32_list_not_tuple_rejected(self):
        x=reviewed_p91()
        with self.assertRaisesRegex(ValueError,"BOUNDED_TYPED"):
            review_h4_qualification(replace(x,
                       complete_48xm5_h4_starts_utc=list(x.complete_48xm5_h4_starts_utc)))

    def test_33_wrong_count_of_exact_ohlc_denied(self):
        with self.assertRaisesRegex(ValueError,"SOURCE_PARITY_COUNTER"):
            review_h4_qualification(replace(reviewed_p91(),exact_ohlc_matches=10))

    def test_34_faked_missing_native_count_denied(self):
        with self.assertRaisesRegex(ValueError,"SOURCE_PARITY_COUNTER"):
            review_h4_qualification(replace(reviewed_p91(),
                                      native_missing_for_complete_m5=1))

    def test_35_record_with_broker_orders_denied(self):
        with self.assertRaisesRegex(ValueError,"AUDIT_SHA_CLOCK"):
            review_h4_qualification(replace(reviewed_p91(),
                                      broker_orders_in_prior_audit=1))

    def test_36_drive_writes_prior_denied(self):
        with self.assertRaisesRegex(ValueError,"AUDIT_SHA_CLOCK"):
            review_h4_qualification(replace(reviewed_p91(),
                                      drive_writes_in_prior_audit=1))

    def test_37_unsafe_vendor_calls_denied(self):
        with self.assertRaisesRegex(ValueError,"AUDIT_SHA_CLOCK"):
            review_h4_qualification(replace(reviewed_p91(),
                                      provider_calls_in_prior_audit=1))

    def test_38_oversized_h4_span_denied(self):
        x=synthetic(FIRST,length=73,pairs=300)
        with self.assertRaisesRegex(ValueError,"BOUNDED_TYPED"):
            review_h4_qualification(x)

    def test_39_48_m5_each_claim_must_have_source_capacity(self):
        x=synthetic(FIRST)
        with self.assertRaisesRegex(ValueError,"SOURCE_PARITY_COUNTER"):
            review_h4_qualification(replace(x,
                m5_manifest_chunk_pairs_verified=20,m5_closed_bars=240))

    def test_40_test_is_pure_does_not_mutate(self):
        x=reviewed_p91()
        before=repr(x)
        review_h4_qualification(x)
        self.assertEqual(repr(x),before)


if __name__=="__main__":
    from unittest import main
    main()

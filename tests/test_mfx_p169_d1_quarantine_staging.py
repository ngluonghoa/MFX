"""P0.169 standalone D1 SHA-addressed quarantine-only raw observations.

No actual Twelve Data, OAuth Drive, M5, H4/D1 canonical or broker access.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from dataclasses import replace
import json

from mfx_cache.native_d1_quarantine_stage import (
    PREFIX, MAX_OBSERVATIONS, PrivateD1QuarantineStore,
    build_d1_quarantine_observation,
    stage_d1_quarantine_snapshot, validate_d1_quarantine_observation,
)
from tools.run_a04_p45_cloud_twelve_data_cache import CHUNK_FOLDER
from test_mfx_p168_independent_h4_d1_hold_cache import (
    D1_LABELS, NOW, batch, state,
)


def source_input(now=NOW, *, new_label="2026-11-12"):
    old = batch("1day", D1_LABELS)
    prior = state("1day",D1_LABELS).last_manifest
    fresh = batch("1day",D1_LABELS+(new_label,),amend="2026-11-11")
    return dict(
        previous=prior, sha_verified_recent=old.closed_bars,
        refetched=fresh, observed_at_utc=now,
    )


class FakeStore:
    def __init__(self):
        self.data={}
        self.create_calls=0
        self.list_calls=0

    def list_names(self,bucket):
        assert bucket=="chunk"
        self.list_calls+=1
        return tuple(sorted(self.data))

    def read(self,bucket,name):
        assert bucket=="chunk"
        return deepcopy(self.data[name])

    def put_if_absent(self,bucket,name,value):
        assert bucket=="chunk" and name.startswith(PREFIX)
        if name in self.data:
            if self.data[name]!=value:
                raise ValueError("FAKE_DRIVE_NO_OVERWRITE")
            return
        self.create_calls+=1
        self.data[name]=deepcopy(value)


class D1QuarantineStageTests(TestCase):
    def test_01_exact_snapshot_has_source_rows_and_false_permissions(self):
        rec=build_d1_quarantine_observation(**source_input())
        self.assertEqual(len(rec["source_batch"]["closed_bars"]),17)
        self.assertTrue(rec["candidate_receipt"]["changed_numeric_ohlc_fields"])
        self.assertTrue(validate_d1_quarantine_observation(rec))
        self.assertFalse(rec["may_publish_buy_sell"])
        self.assertFalse(rec["may_overwrite_canonical"])

    def test_02_append_once_and_readback_raw_rows(self):
        store=FakeStore()
        outcome=stage_d1_quarantine_snapshot(store,**source_input())
        self.assertEqual(outcome["observations_created"],1)
        self.assertEqual(outcome["closed_bars_custodied"],17)
        self.assertEqual(store.create_calls,1)
        self.assertEqual(len(store.data),1)
        self.assertTrue(next(iter(store.data)).startswith(PREFIX))

    def test_03_identical_provider_refetch_no_new_drive_object(self):
        store=FakeStore()
        a=stage_d1_quarantine_snapshot(store,**source_input())
        b=stage_d1_quarantine_snapshot(store,**source_input(
            NOW+timedelta(hours=1)))
        self.assertEqual(a["observations_created"],1)
        self.assertEqual(b["observations_created"],0)
        self.assertEqual(b["first_runner_observation_utc"],NOW.isoformat())
        self.assertEqual(store.create_calls,1)

    def test_04_new_closed_day_creates_new_immutable_snapshot(self):
        store=FakeStore()
        stage_d1_quarantine_snapshot(store,**source_input())
        later=source_input(NOW+timedelta(days=1))
        later["refetched"]=batch("1day",D1_LABELS+(
            "2026-11-12","2026-11-13"),amend="2026-11-11")
        res=stage_d1_quarantine_snapshot(store,**later)
        self.assertEqual(res["observations_created"],1)
        self.assertEqual(store.create_calls,2)
        self.assertEqual(len(store.data),2)

    def test_05_old_sha_manifest_changed_refuses_candidate(self):
        inp=source_input()
        wrong=deepcopy(inp["previous"])
        wrong["last_native_open_label"]="2026-11-09"
        inp["previous"]=wrong
        with self.assertRaises(ValueError):
            build_d1_quarantine_observation(**inp)

    def test_06_new_numeric_incident_other_day_refused(self):
        inp=source_input()
        inp["refetched"]=batch("1day",D1_LABELS+("2026-11-12",),
                              amend="2026-11-10")
        with self.assertRaisesRegex(ValueError,"SINGLE_D1_INCIDENT"):
            build_d1_quarantine_observation(**inp)

    def test_07_no_numeric_difference_refused(self):
        inp=source_input()
        inp["refetched"]=batch("1day",D1_LABELS+("2026-11-12",))
        with self.assertRaises(ValueError):
            build_d1_quarantine_observation(**inp)

    def test_08_utc_runner_observation_not_false_publisher_timestamp(self):
        inp=source_input()
        for d in (NOW.replace(tzinfo=None),
                  NOW.astimezone(timezone(timedelta(hours=7)))):
            with self.subTest(date=d),self.assertRaisesRegex(
                ValueError,"EXACT_UTC"):
                build_d1_quarantine_observation(**{**inp,"observed_at_utc":d})
        x=build_d1_quarantine_observation(**inp)
        self.assertFalse(x["publisher_first_known_verified"])
        self.assertIn("NOT_INDEPENDENT",x["observation_time_quality"])

    def test_09_content_hash_tamper_denied(self):
        old=build_d1_quarantine_observation(**source_input())
        for field,value in [
            ("record_sha256","0"*64),
            ("source_batch_sha256","0"*64),
            ("observation_identity_sha256","0"*64),
            ("may_publish_buy_sell",True),
            ("source_licence_approved",True),
            ("owner_canonical_revision_approved",True),
            ("state","RELEASED"),
        ]:
            with self.subTest(field=field),self.assertRaises(ValueError):
                validate_d1_quarantine_observation({**old,field:value})

    def test_10_change_old_record_payload_detected_on_retry(self):
        store=FakeStore()
        stage_d1_quarantine_snapshot(store,**source_input())
        name=next(iter(store.data))
        store.data[name]["source_batch"]["closed_bars"][-1]["close"]="0.0001"
        with self.assertRaises(ValueError):
            stage_d1_quarantine_snapshot(store,**source_input(
                NOW+timedelta(hours=1)))
        self.assertEqual(store.create_calls,1)

    def test_11_store_capacity_bounded_no_append(self):
        store=FakeStore()
        store.data={f"{PREFIX}{i:064x}.json":{} for i in range(
            MAX_OBSERVATIONS)}
        with self.assertRaisesRegex(ValueError,"CAPACITY"):
            stage_d1_quarantine_snapshot(store,**source_input())
        self.assertEqual(store.create_calls,0)

    def test_12_native_and_m5_namespaces_are_disjoint(self):
        s=PrivateD1QuarantineStore(session="offline")
        self.assertEqual(s._bucket("chunk")[0],CHUNK_FOLDER)
        self.assertEqual(s._bucket("chunk")[1],PREFIX)
        self.assertNotIn("NATIVE_V1",PREFIX)
        self.assertNotIn("M5_chunk",PREFIX)
        with self.assertRaisesRegex(ValueError,"CHUNK_ONLY"):
            s._bucket("manifest")

    def test_13_run_twice_does_not_overwrite_first_observed_time(self):
        store=FakeStore()
        first=stage_d1_quarantine_snapshot(store,**source_input())
        second=stage_d1_quarantine_snapshot(store,**source_input(
            NOW+timedelta(hours=3)))
        self.assertEqual(store.create_calls,1)
        self.assertEqual(first["first_runner_observation_utc"],
                         second["first_runner_observation_utc"])

    def test_14_old_observation_after_current_clock_denied(self):
        store=FakeStore()
        stage_d1_quarantine_snapshot(store,**source_input(
            NOW+timedelta(hours=1)))
        with self.assertRaisesRegex(ValueError,"CLOCK_ROLLBACK"):
            stage_d1_quarantine_snapshot(store,**source_input())

    def test_15_no_source_bar_or_quote_values_leak_in_receipt(self):
        store=FakeStore()
        record=stage_d1_quarantine_snapshot(store,**source_input())
        public=json.dumps(record)
        for forbidden in ("1.1000","1.1041","1.0990","1.1030",
                          "source_batch","candidate_receipt","BUY","SELL"):
            self.assertNotIn(forbidden,public)
        self.assertEqual(record["d1_canonical_writes"],0)

    def test_16_new_snapshot_append_only_never_calls_canonical_methods(self):
        store=FakeStore()
        stage_d1_quarantine_snapshot(store,**source_input())
        self.assertEqual(store.create_calls,1)
        self.assertEqual(store.list_names("chunk") != (),True)

    def test_17_constructor_refuses_injected_market_source(self):
        inp=source_input()
        inp["refetched"]=replace(inp["refetched"],source="FAKE")
        with self.assertRaises(ValueError):
            build_d1_quarantine_observation(**inp)

    def test_18_wrong_symbol_denied_without_store(self):
        inp=source_input()
        inp["refetched"]=replace(inp["refetched"],symbol="GBP/USD")
        with self.assertRaises(ValueError):
            build_d1_quarantine_observation(**inp)

    def test_19_existing_manifest_old_row_sha_missing_denied(self):
        inp=source_input()
        inp["sha_verified_recent"]=inp["sha_verified_recent"][:-1]
        with self.assertRaises(ValueError):
            build_d1_quarantine_observation(**inp)

    def test_20_record_add_unknown_field_denied(self):
        r=build_d1_quarantine_observation(**source_input())
        with self.assertRaisesRegex(ValueError,"EXACT_RECORD_SCHEMA"):
            validate_d1_quarantine_observation({**r,"unverified_go":True})

    def test_21_d1_quarantine_never_clears_source_issue(self):
        s=build_d1_quarantine_observation(**source_input())
        self.assertFalse(s["may_trade"])
        self.assertFalse(s["publisher_first_known_verified"])
        self.assertFalse(s["may_overwrite_canonical"])
        self.assertEqual(s["original_incident_label"],"2026-11-11")

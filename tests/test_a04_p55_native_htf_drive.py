"""P0.55 strict cloud OAuth Drive native HTF adapter: hermetic offline tests."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from io import StringIO
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from typing import Any
import copy
import json
import os
import re
import unittest

from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.native_htf_archive import plan_native_sealed
from tools.mfx_native_htf_drive_seal import (
    PrivateNativeDriveStore, audit_native_archive, commit_native_batch,
    CHUNK_FOLDER, MANIFEST_FOLDER,
)
from tools.run_mfx_native_htf_drive_commit import main

UTC = timezone.utc
NOW = datetime(2026,11,11,3,0,tzinfo=UTC)
HOURS = [
    "2026-11-10 12:00:00", "2026-11-10 16:00:00",
    "2026-11-10 20:00:00",
]
DAYS = ["2026-11-07","2026-11-09"]


def native(interval: str = "4h", *,
           symbol: str = "EUR/USD",
           labels: list[str] | None = None) -> NativeFXBatch:
    axis = ("UTC_INTRADAY_OPEN" if interval=="4h"
            else "EXCHANGE_LOCAL_SESSION_DATE")
    chosen = labels if labels is not None else (
        HOURS[:2] if interval=="4h" else DAYS)
    return NativeFXBatch(
        symbol=symbol, interval=interval,
        exchange_timezone="Australia/Sydney",
        time_reference=axis, incomplete_excluded=0,
        closed_bars=tuple(NativeFXBar(
            symbol=symbol, interval=interval, native_open_label=s,
            time_reference=axis, exchange_timezone="Australia/Sydney",
            open="1.10000",high="1.10500",
            low="1.09800",close="1.10200",
        ) for s in chosen),
    )


class FakeResponse:
    def __init__(self, payload: dict[str,Any]) -> None:
        self.payload=payload
    def raise_for_status(self) -> None:
        pass
    def json(self) -> dict[str,Any]:
        return self.payload


class FakeDrive:
    def __init__(self) -> None:
        self.objects: dict[str,dict[str,Any]] = {}
        self.names: dict[str,str] = {}
        self.parents: dict[str,str] = {}
        self.writes=0
        self.requests: list[tuple[str,dict[str,Any]]] = []

    def get(self, url: str, *, params: dict[str,Any],
            timeout: int) -> FakeResponse:
        assert url == "https://www.googleapis.com/drive/v3/files"
        self.requests.append((url,copy.deepcopy(params)))
        query=params["q"]
        match=re.search(r"name contains '([^']+)'",query)
        assert match
        prefix=match.group(1)
        folder=CHUNK_FOLDER if "chunk_" in prefix else MANIFEST_FOLDER
        selected=[
            {"id":ident,"name":name,
             "mimeType":"application/json","parents":[folder]}
            for name,ident in self.names.items()
            if name.startswith(prefix) and self.parents[ident]==folder
        ]
        return FakeResponse({"files":selected})

    def create(self, folder: str, name: str, body: dict[str,Any]) -> str:
        self.writes+=1
        ident="native-fake-id-"+str(self.writes)
        if name in self.names:
            raise AssertionError("fake Drive duplicate create")
        self.names[name]=ident
        self.parents[ident]=folder
        self.objects[ident]=copy.deepcopy(body)
        return ident

    def read(self, ident: str) -> dict[str,Any]:
        return copy.deepcopy(self.objects[ident])

    def add_other_m5(self) -> None:
        self.writes+=1
        ident="m5-fake-id-"+str(self.writes)
        name="MFX_TD_EURUSD_M5_V2_chunk_20261110T1800Z_hello.json"
        self.names[name]=ident
        self.parents[ident]=CHUNK_FOLDER
        self.objects[ident]={"source_interval":"M5"}


class P055NativeHTFDriveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake=FakeDrive()
        self.p_create=patch(
            "tools.mfx_native_htf_drive_seal._drive_create",
            side_effect=lambda session, folder, name, body:
                self.fake.create(folder,name,body))
        self.p_read=patch(
            "tools.mfx_native_htf_drive_seal._drive_get",
            side_effect=lambda session, ident:
                self.fake.read(ident))
        self.p_create.start()
        self.p_read.start()
        self.addCleanup(self.p_create.stop)
        self.addCleanup(self.p_read.stop)

    def store(self, interval: str="4h", symbol: str="EUR/USD"):
        return PrivateNativeDriveStore(
            self.fake,symbol=symbol,interval=interval)

    def test_01_real_adapter_root_h4_2_write_readbacks(self) -> None:
        r=commit_native_batch(self.store(),native())
        self.assertEqual(r.status,"NATIVE_BATCH_COMMITTED")
        self.assertEqual(r.newly_closed_native_bars,2)
        self.assertEqual(r.total_closed_native_bars,2)
        self.assertEqual(self.fake.writes,2)
        a=audit_native_archive(
            self.store(),symbol="EUR/USD",interval="4h")
        self.assertEqual((a.manifest_count,a.chunk_count),(1,1))
        self.assertEqual(a.uncommitted_chunk_names,())

    def test_02_d1_separate_scope_same_app_owned_drive_folder(self) -> None:
        commit_native_batch(self.store(),native())
        r=commit_native_batch(self.store("1day"),native("1day"))
        self.assertEqual(r.status,"NATIVE_BATCH_COMMITTED")
        self.assertEqual(self.fake.writes,4)
        self.assertEqual(
            len(self.store("1day").list_names("manifest")),1)
        self.assertEqual(
            len(self.store("4h").list_names("manifest")),1)
        self.assertNotEqual(
            self.store("4h").list_names("manifest")[0],
            self.store("1day").list_names("manifest")[0])

    def test_03_repeat_pair_is_idempotent_zero_new_objects(self) -> None:
        commit_native_batch(self.store(),native())
        before=self.fake.writes
        r=commit_native_batch(self.store(),native())
        self.assertEqual(r.status,"NO_NEW_CLOSED_NATIVE_BAR")
        self.assertEqual(r.newly_closed_native_bars,0)
        self.assertEqual(self.fake.writes,before)

    def test_04_append_h4_parent_sha_and_totals(self) -> None:
        first=commit_native_batch(self.store(),native())
        second=commit_native_batch(
            self.store(),native(labels=HOURS))
        self.assertEqual(second.status,"NATIVE_BATCH_COMMITTED")
        self.assertEqual(second.newly_closed_native_bars,1)
        self.assertEqual(second.total_closed_native_bars,3)
        self.assertNotEqual(first.manifest_sha256,second.manifest_sha256)
        current=audit_native_archive(
            self.store(),symbol="EUR/USD",interval="4h")
        self.assertEqual(current.manifest_count,2)
        self.assertEqual(current.last_manifest["batch_count"],2)

    def test_05_recover_exact_orphan_without_reupload(self) -> None:
        commit_native_batch(self.store(),native())
        state=audit_native_archive(
            self.store(),symbol="EUR/USD",interval="4h")
        plan=plan_native_sealed(
            native(labels=HOURS),previous=state.last_manifest)
        assert plan is not None
        self.fake.create(CHUNK_FOLDER,plan.chunk_name,plan.chunk)
        before=self.fake.writes
        r=commit_native_batch(self.store(),native(labels=HOURS))
        self.assertEqual(r.status,"RECOVERED_ORPHAN_AND_COMMITTED")
        self.assertEqual(self.fake.writes,before+1)

    def test_06_unexpected_orphan_is_quarantined_before_write(self) -> None:
        commit_native_batch(self.store(),native())
        state=audit_native_archive(
            self.store(),symbol="EUR/USD",interval="4h")
        plan=plan_native_sealed(
            native(labels=HOURS),previous=state.last_manifest)
        assert plan is not None
        self.fake.create(CHUNK_FOLDER,plan.chunk_name,plan.chunk)
        before=self.fake.writes
        with self.assertRaisesRegex(ValueError,"ORPHAN"):
            commit_native_batch(self.store(),native())
        self.assertEqual(self.fake.writes,before)

    def test_07_mutated_chunk_fails_closed_before_further_writes(self) -> None:
        commit_native_batch(self.store(),native())
        name=self.store().list_names("chunk")[0]
        ident=self.fake.names[name]
        self.fake.objects[ident]["bars"][0]["close"]="1.10300"
        before=self.fake.writes
        with self.assertRaises(ValueError):
            commit_native_batch(self.store(),native(labels=HOURS))
        self.assertEqual(self.fake.writes,before)

    def test_08_mutated_manifest_fails_closed(self) -> None:
        commit_native_batch(self.store(),native())
        name=self.store().list_names("manifest")[0]
        ident=self.fake.names[name]
        self.fake.objects[ident]["total_closed_native_bars"]=999
        with self.assertRaises(ValueError):
            audit_native_archive(
                self.store(),symbol="EUR/USD",interval="4h")

    def test_09_missing_chunk_is_explicit_failure(self) -> None:
        commit_native_batch(self.store(),native())
        name=self.store().list_names("chunk")[0]
        ident=self.fake.names.pop(name)
        self.fake.objects.pop(ident)
        with self.assertRaisesRegex(ValueError,"MISSING_REFERENCED_CHUNK"):
            audit_native_archive(
                self.store(),symbol="EUR/USD",interval="4h")

    def test_10_two_unknowable_orphans_abort_archive(self) -> None:
        for i in range(2):
            name="MFX_TD_EURUSD_H4_NATIVE_V1_chunk_20261110T1"+str(i)+"00UTC_"+str(i)*64+".json"
            self.fake.create(CHUNK_FOLDER,name,{"poison":i})
        with self.assertRaisesRegex(ValueError,"MULTIPLE_UNCOMMITTED"):
            audit_native_archive(
                self.store(),symbol="EUR/USD",interval="4h")

    def test_11_revised_overlap_refused_without_overwriting(self) -> None:
        commit_native_batch(self.store(),native())
        b=native(labels=HOURS)
        b=replace(b,closed_bars=(
            b.closed_bars[0],
            replace(b.closed_bars[1],close="1.10300"),
            b.closed_bars[2]))
        before=self.fake.writes
        with self.assertRaisesRegex(ValueError,"HISTORICAL_NATIVE_REVISION"):
            commit_native_batch(self.store(),b)
        self.assertEqual(self.fake.writes,before)

    def test_12_cross_pair_same_folder_cannot_be_read(self) -> None:
        commit_native_batch(self.store(),native())
        with self.assertRaisesRegex(ValueError,"READ_SCOPE_DENIED"):
            self.store(symbol="GBP/USD").read(
                "manifest",self.store().list_names("manifest")[0])

    def test_13_denies_unapproved_bucket_and_name(self) -> None:
        with self.assertRaisesRegex(ValueError,"BUCKET_DENIED"):
            self.store().list_names("M5")
        with self.assertRaisesRegex(ValueError,"WRITE_SCOPE_DENIED"):
            self.store().put_if_absent("chunk","bad.json",{})

    def test_14_existing_m5_objects_preserved_untouched(self) -> None:
        self.fake.add_other_m5()
        original=copy.deepcopy(self.fake.objects)
        self.assertEqual(self.store().list_names("chunk"),())
        self.assertEqual(self.store().list_names("manifest"),())
        commit_native_batch(self.store(),native())
        self.assertEqual(self.fake.objects["m5-fake-id-1"],
                         original["m5-fake-id-1"])
        self.assertEqual(len(self.store().list_names("chunk")),1)

    def test_15_drive_query_is_folder_and_prefix_scoped(self) -> None:
        self.store().list_names("chunk")
        query=self.fake.requests[-1][1]["q"]
        self.assertIn(CHUNK_FOLDER,query)
        self.assertIn("MFX_TD_EURUSD_H4_NATIVE_V1_chunk_",query)
        self.assertNotIn("M5_V2",query)

    def test_16_malformed_drive_json_response_is_rejected(self) -> None:
        with patch.object(self.fake,"get",
                          return_value=FakeResponse({"files":"wrong"})):
            with self.assertRaisesRegex(ValueError,"BAD_LIST"):
                self.store().list_names("chunk")

    def test_17_same_name_duplicate_drive_files_quarantined(self) -> None:
        item={"id":"id-1","name":"MFX_TD_EURUSD_H4_NATIVE_V1_chunk_a",
              "mimeType":"application/json","parents":[CHUNK_FOLDER]}
        with patch.object(self.fake,"get",
                          return_value=FakeResponse({"files":[item,item]})):
            with self.assertRaisesRegex(ValueError,"DUPLICATE_NAME"):
                self.store().list_names("chunk")

    def test_18_main_native_gate_off_never_uses_credentials(self) -> None:
        with patch.dict(os.environ,{"MFX_REAL_CACHE_ENABLED":"true",
              "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
              "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED":"false"}),patch(
              "tools.run_mfx_native_htf_drive_commit._settings") as settings:
            output=StringIO()
            with redirect_stdout(output):
                main()
        settings.assert_not_called()
        self.assertIn("DISABLED_EXPLICIT_THREE_WAY_GATE",output.getvalue())

    def test_19_quota_no_headroom_does_not_fetch_or_touch_drive(self) -> None:
        with patch.dict(os.environ,{"MFX_REAL_CACHE_ENABLED":"true",
              "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
              "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED":"true"}),patch(
              "tools.run_mfx_native_htf_drive_commit._settings",
              return_value=("fake",{},400)),patch(
              "tools.run_mfx_native_htf_drive_commit._usage",
              return_value=(6,8)),patch(
              "tools.run_mfx_native_htf_drive_commit._probe_one") as probe,patch(
              "tools.run_mfx_native_htf_drive_commit._session") as session:
            output=StringIO()
            with redirect_stdout(output):
                main()
        probe.assert_not_called()
        session.assert_not_called()
        self.assertIn("NO_PRICE_REQUESTS",output.getvalue())

    def test_20_second_provider_failure_prevents_any_drive_write(self) -> None:
        with patch.dict(os.environ,{"MFX_REAL_CACHE_ENABLED":"true",
              "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
              "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED":"true"}),patch(
              "tools.run_mfx_native_htf_drive_commit._settings",
              return_value=("fake",{},400)),patch(
              "tools.run_mfx_native_htf_drive_commit._usage",
              side_effect=[(1,8),(2,8)]),patch(
              "tools.run_mfx_native_htf_drive_commit._probe_one",
              side_effect=[native(),ValueError("provider unsupported")]),patch(
              "tools.run_mfx_native_htf_drive_commit._session") as session:
            with self.assertRaisesRegex(ValueError,"provider unsupported"):
                main()
        session.assert_not_called()
        self.assertEqual(self.fake.writes,0)

    def test_21_success_main_seals_two_provider_native_series(self) -> None:
        with patch.dict(os.environ,{"MFX_REAL_CACHE_ENABLED":"true",
              "MFX_V2_BATCH_CACHE_ACCEPTED":"true",
              "MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED":"true",
              "MFX_TWELVE_DATA_API_KEY":"TOPSECRET"}),patch(
              "tools.run_mfx_native_htf_drive_commit._settings",
              return_value=("TOPSECRET",{},400)),patch(
              "tools.run_mfx_native_htf_drive_commit._usage",
              side_effect=[(1,8),(2,8)]),patch(
              "tools.run_mfx_native_htf_drive_commit._probe_one",
              side_effect=[native(),native("1day")]),patch(
              "tools.run_mfx_native_htf_drive_commit._session",
              return_value=self.fake):
            out=StringIO()
            with redirect_stdout(out):
                main()
        s=out.getvalue()
        self.assertIn("NATIVE_H4_D1_DRIVE_PAIR_SHA_READBACK_PASS",s)
        self.assertIn("NATIVE_H4_D1_SEALED_BATCHES_COMMITTED",s)
        self.assertNotIn("TOPSECRET",s)
        self.assertNotIn("1.10000",s)
        self.assertEqual(self.fake.writes,4)
        for tf in ("4h","1day"):
            x=audit_native_archive(
                self.store(tf),symbol="EUR/USD",interval=tf)
            self.assertEqual(x.manifest_count,1)

    def test_22_workflow_is_manual_and_three_way_opt_in(self) -> None:
        y=Path(".github/workflows/mfx-native-htf-drive-commit.yml").read_text(
            encoding="utf-8")
        self.assertIn("workflow_dispatch:",y)
        self.assertNotIn("schedule:",y)
        self.assertIn("MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED",y)
        self.assertIn("mfx-twelvedata-private-cache",y)
        self.assertIn("run_mfx_native_htf_drive_commit",y)
        m5=Path(".github/workflows/twelve-data-cache.yml").read_text(
            encoding="utf-8")
        self.assertNotIn("MFX_NATIVE_HTF_DRIVE_WRITE_ACCEPTED",m5)
        self.assertNotIn("run_mfx_native_htf_drive_commit",m5)


    def test_23_documented_zone_origin_survives_sealed_drive_readback(self) -> None:
        b=native("1day")
        b=replace(b,closed_bars=tuple(
            replace(row,exchange_timezone_origin=
                    "DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT")
            for row in b.closed_bars))
        receipt=commit_native_batch(self.store("1day"),b)
        self.assertEqual(receipt.status,"NATIVE_BATCH_COMMITTED")
        state=audit_native_archive(
            self.store("1day"),symbol="EUR/USD",interval="1day")
        self.assertEqual(state.manifest_count,1)
        chunk=self.store("1day").read(
            "chunk",state.last_manifest["chunk_name"])
        self.assertEqual(
            chunk["bars"][0]["exchange_timezone_origin"],
            "DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT")

    def test_24_unverified_zone_origin_denied_before_drive_mutation(self) -> None:
        b=native("4h")
        b=replace(b,closed_bars=(
            replace(b.closed_bars[0],exchange_timezone_origin="GUESS"),
            b.closed_bars[1]))
        with self.assertRaisesRegex(ValueError,"TIMEZONE_PROVENANCE_INVALID"):
            commit_native_batch(self.store(),b)
        self.assertEqual(self.fake.writes,0)


    def test_25_real_drive_broad_results_do_not_cross_native_scopes(self) -> None:
        # P0.57 replay: H4 was sealed on real Drive; D1 has no objects.
        # Mock a server list that returns same-folder siblings in addition
        # to names matching the requested native interval and bucket.
        self.fake.add_other_m5()
        self.fake.create(
            MANIFEST_FOLDER,
            "MFX_TD_EURUSD_M5_V2_manifest_20261110T1800Z_mock.json",
            {"source_interval":"M5"})
        old_m5=copy.deepcopy({
            name:self.fake.objects[ident]
            for name,ident in self.fake.names.items()
            if "_M5_V2_" in name
        })

        def broad_get(url: str, *, params: dict[str,Any],
                      timeout: int) -> FakeResponse:
            self.assertEqual(url,"https://www.googleapis.com/drive/v3/files")
            bucket="chunk" if "chunk_" in params["q"] else "manifest"
            folder=CHUNK_FOLDER if bucket=="chunk" else MANIFEST_FOLDER
            return FakeResponse({"files":[
                {"id":ident,"name":name,
                 "mimeType":"application/json","parents":[folder]}
                for name,ident in self.fake.names.items()
                if self.fake.parents[ident]==folder
            ]})

        with patch.object(self.fake,"get",side_effect=broad_get):
            a=commit_native_batch(self.store(),native("4h"))
            b=commit_native_batch(self.store("1day"),native("1day"))
            self.assertEqual((a.status,b.status),
                             ("NATIVE_BATCH_COMMITTED",)*2)
            self.assertEqual(
                audit_native_archive(self.store("4h"),
                  symbol="EUR/USD",interval="4h").manifest_count,1)
            self.assertEqual(
                audit_native_archive(self.store("1day"),
                  symbol="EUR/USD",interval="1day").manifest_count,1)
        for name,contents in old_m5.items():
            self.assertEqual(
                self.fake.objects[self.fake.names[name]],contents)

    def test_26_optional_list_parents_can_be_absent(self) -> None:
        # The folder is already constrained by the server-side query.
        plan=plan_native_sealed(native(),previous=None)
        assert plan is not None
        ident=self.fake.create(CHUNK_FOLDER,plan.chunk_name,plan.chunk)
        response=FakeResponse({"files":[{
            "id":ident,"name":plan.chunk_name,"mimeType":"application/json"
        }]})
        with patch.object(self.fake,"get",return_value=response):
            self.assertEqual(
                self.store().list_names("chunk"),(plan.chunk_name,))

    def test_27_wrong_parent_and_native_mime_still_fail_closed(self) -> None:
        name="MFX_TD_EURUSD_H4_NATIVE_V1_chunk_probe.json"
        wrong_parent={"id":"x","name":name,"mimeType":"application/json",
                      "parents":["unrelated-folder"]}
        wrong_mime={"id":"x","name":name,"mimeType":"text/plain",
                    "parents":[CHUNK_FOLDER]}
        for item,reason in (
            (wrong_parent,"P057_NATIVE_DRIVE_WRONG_PARENT"),
            (wrong_mime,"P057_NATIVE_DRIVE_BAD_NATIVE_MIME"),
        ):
            with self.subTest(reason=reason),patch.object(
                    self.fake,"get",
                    return_value=FakeResponse({"files":[item]})):
                with self.assertRaisesRegex(ValueError,reason):
                    self.store().list_names("chunk")


if __name__=="__main__":
    unittest.main()

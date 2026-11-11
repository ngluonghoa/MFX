"""A04/P0.77: 28 hermetic GET-only Drive V2 archive tests.

No live credentials, no real Drive, Twelve Data, or broker. A fake V1 256
tail is NEVER independent historical V1 validation or a real V2 rollout.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
from unittest import TestCase

from mfx_cache.td_m5_codec import canonical, digest
from tools.mfx_native_v2_drive_readonly import (
    CHUNK_FOLDER, MANIFEST_FOLDER, MAX_OBJECT_BYTES, PAGE_SIZE, URL,
    V2NativeDriveReadOnlyStore, audit_v2_native_drive_readonly,
)
from test_a04_p74_native_v2_handoff import v1_state
from test_a04_p75_native_v2_shard_chain import (
    H4, D1, NOW, chain, fake_full_v1,
)


class FakeResponse:
    def __init__(self, body):
        self.body=deepcopy(body)
    def json(self):
        return deepcopy(self.body)
    def raise_for_status(self):
        return None


class FakeGetOnlySession:
    def __init__(self, *, page_length=1000):
        self.rows = {}
        self.reads = 0
        self.lists = 0
        self.posts = 0
        self.page_length=page_length
        self.force_wrong_envelope=False
        self.force_repeated_token=False
        self.force_long_pagination=False
        self.force_change_on_third_list=False
        self.force_extra=[]
    def seed(self, pairs):
        for pair in pairs:
            for kind,folder,name,body in (
                ("chunk",CHUNK_FOLDER,pair.chunk_name,pair.chunk),
                ("manifest",MANIFEST_FOLDER,pair.manifest_name,pair.manifest)
            ):
                file_id=f"mockv2object{len(self.rows):05d}"
                self.rows[file_id]=dict(
                    id=file_id,name=name,mimeType="application/json",
                    parents=[folder],size=str(len(canonical(body))),
                    body=deepcopy(body),
                )
        return self
    def get(self, url, *, params, timeout):
        if url == URL:
            self.lists+=1
            if self.force_change_on_third_list and self.lists == 3:
                entry=next(r for r in self.rows.values()
                           if r["name"].find("_manifest_")>=0)
                entry["id"]="changeddriveid00002"
            if self.force_wrong_envelope:
                return FakeResponse({"files":"not-list"})
            assert timeout == 45
            assert params["pageSize"] == PAGE_SIZE
            assert params["supportsAllDrives"] == "true"
            assert params["includeItemsFromAllDrives"] == "true"
            q=re.fullmatch(
                r"'([^']+)' in parents and name contains '([^']+)' and trashed = false",
                params["q"],
            )
            if not q:
                raise AssertionError("Unscoped Drive query")
            folder,prefix=q.groups()
            items=[
                {k:v for k,v in obj.items() if k != "body"}
                for obj in self.rows.values()
                if folder in obj["parents"] and prefix in obj["name"]
            ]
            items.extend(deepcopy(self.force_extra))
            token=params.get("pageToken")
            start=int(token) if token and token.isdigit() else 0
            if self.force_repeated_token:
                return FakeResponse({"files":items[:1],
                                     "nextPageToken":"forever"})
            if self.force_long_pagination:
                return FakeResponse({"files":[],
                                     "nextPageToken":str(start+1)})
            page=items[start:start+self.page_length]
            answer={"files":page}
            if start+self.page_length < len(items):
                answer["nextPageToken"]=str(start+self.page_length)
            return FakeResponse(answer)
        if url.startswith(URL+"/") and params=={
            "alt":"media","supportsAllDrives":"true"}:
            self.reads+=1
            assert timeout == 40
            file_id=url.removeprefix(URL+"/")
            if file_id not in self.rows:
                raise ValueError("FAKE_MISSING_FILE_ID")
            return FakeResponse(self.rows[file_id]["body"])
        raise AssertionError("GET-only scope violated: "+url)
    def post(self, *a, **k):
        self.posts+=1
        raise AssertionError("MUST NEVER POST")
    def patch(self, *a, **k):
        raise AssertionError("MUST NEVER PATCH")
    def delete(self, *a, **k):
        raise AssertionError("MUST NEVER DELETE")


def prepared(tf="4h", labels=None, *, cap=2, page_length=1000):
    if labels is None:
        labels=H4[:3] if tf=="4h" else D1[:3]
    state,p,v1,h=chain(tf, labels,cap=cap)
    session=FakeGetOnlySession(page_length=page_length).seed(h)
    expected=h[-1].manifest_sha256 if h else p.proposed_anchor_sha256
    return session,state,p,v1,h,expected


def audit(prep, *, cap=2, tip=None):
    sess,legacy,proposal,v1,h,expected=prep
    return audit_v2_native_drive_readonly(
        sess,proposal,legacy,
        expected_v1_manifest_sha256=v1,
        expected_v2_tip_sha256=expected if tip is None else tip,
        now_utc=NOW,shard_capacity=cap,
    )


class A04P077DriveReadOnlyTests(TestCase):
    def test_01_full_native_h4_cross_shard_sha_pass(self):
        p=prepared()
        r=audit(p)
        self.assertEqual((r.pair_count,r.shard_count),(3,2))
        self.assertTrue(r.full_supplied_chain_sha_verified)
        self.assertEqual(r.last_native_open_label,H4[2])
        self.assertTrue(r.scan_snapshot_unchanged)
        self.assertEqual(r.status,
                         "V2_GET_ONLY_SHA_CHECK_NO_REAL_TRUST_OR_ACTIVATION")
        self.assertFalse(r.independent_external_tail_witness_verified)
        self.assertFalse(r.live_v2_activation_authorized)
        self.assertEqual((r.drive_writes,r.provider_requests,r.broker_orders),
                         (0,0,0))
        self.assertEqual(p[0].posts,0)
        self.assertEqual(p[0].reads,6)

    def test_02_native_sydney_d1_is_not_utc_h4(self):
        p=prepared("1day")
        r=audit(p)
        self.assertEqual(r.interval,"1day")
        self.assertEqual(r.last_native_open_label,D1[2])
        self.assertEqual(r.shard_count,2)
        self.assertIn("D1_NATIVE_V2",p[4][-1].manifest_name)

    def test_03_empty_v2_folder_is_only_empty_unattested_proposal(self):
        state,proposal,v1=fake_full_v1("4h")
        sess=FakeGetOnlySession()
        receipt=audit_v2_native_drive_readonly(
            sess,proposal,state,expected_v1_manifest_sha256=v1,
            expected_v2_tip_sha256=proposal.proposed_anchor_sha256,
            now_utc=NOW,shard_capacity=2)
        self.assertEqual(receipt.pair_count,0)
        self.assertFalse(receipt.independent_external_tail_witness_verified)
        self.assertEqual(sess.reads,0)
        self.assertEqual(sess.lists,4)

    def test_04_legacy_short_of_256_fails_before_http(self):
        _,short=v1_state("4h")
        from tools.mfx_native_shard_v2_design import propose_native_v2_shard_handoff
        proposal=propose_native_v2_shard_handoff(
            short,symbol="EUR/USD",interval="4h",
            expected_v1_manifest_sha256=digest(short.last_manifest))
        session=FakeGetOnlySession()
        with self.assertRaisesRegex(ValueError,
                                    "V1_NOT_FULL_OR_PROPOSAL_NOT_INERT"):
            audit_v2_native_drive_readonly(
                session,proposal,short,
                expected_v1_manifest_sha256=digest(short.last_manifest),
                expected_v2_tip_sha256=proposal.proposed_anchor_sha256,
                now_utc=NOW,shard_capacity=2)
        self.assertEqual((session.lists,session.reads),(0,0))

    def test_05_get_only_no_provider_or_mutation(self):
        p=prepared()
        audit(p)
        self.assertEqual(p[0].posts,0)
        self.assertEqual(p[0].lists,4)
        self.assertEqual(p[0].reads,2*len(p[4]))

    def test_06_client_filters_unrelated_v1_and_m5_hits(self):
        p=prepared()
        p[0].force_extra=[
            {"id":"mockunrelated12345",
             "name":"MFX_TD_EURUSD_H4_NATIVE_V1_manifest_other.json",
             "parents":[MANIFEST_FOLDER],"mimeType":"application/json",
             "size":"10"}
        ]
        self.assertEqual(audit(p).pair_count,3)

    def test_07_exact_symbol_tf_namespace_segregation(self):
        p=prepared()
        d=prepared("1day")
        p[0].seed(d[4])
        self.assertEqual(audit(p).pair_count,3)
        self.assertNotEqual(p[2].proposed_v2_scope,d[2].proposed_v2_scope)

    def test_08_forged_near_prefix_name_rejected(self):
        p=prepared()
        row=next(x for x in p[0].rows.values() if "_chunk_" in x["name"])
        row["name"]=row["name"].replace("_chunk_", "_other_")
        with self.assertRaisesRegex(ValueError,"OBJECT_NAME_MALFORMED"):
            audit(p)

    def test_09_wrong_mime_denied(self):
        p=prepared()
        next(iter(p[0].rows.values()))["mimeType"]="text/plain"
        with self.assertRaisesRegex(ValueError,"OBJECT_METADATA_UNSAFE"):
            audit(p)

    def test_10_wrong_parent_denied(self):
        p=prepared()
        next(iter(p[0].rows.values()))["parents"]=["otherparent"]
        # Server folder filter ordinarily prevents discovery. Simulate a
        # malicious or malformed Drive list item returned despite query.
        fake=next(iter(p[0].rows.values()))
        p[0].force_extra=[{k:v for k,v in fake.items() if k != "body"}]
        with self.assertRaisesRegex(ValueError,"OBJECT_METADATA_UNSAFE"):
            audit(p)

    def test_11_missing_parent_denied(self):
        p=prepared()
        row=next(iter(p[0].rows.values()))
        row.pop("parents")
        with self.assertRaisesRegex((ValueError,KeyError),
                                    "OBJECT_METADATA_UNSAFE|parents"):
            audit(p)

    def test_12_oversize_and_zero_size_denied(self):
        for size in (str(MAX_OBJECT_BYTES+1),"0","NaN"):
            p=prepared()
            next(iter(p[0].rows.values()))["size"]=size
            with self.subTest(size=size),self.assertRaisesRegex(
                    ValueError,"OBJECT_METADATA_UNSAFE"):
                audit(p)

    def test_13_invalid_file_id_denied(self):
        p=prepared()
        next(iter(p[0].rows.values()))["id"]="bad/id"
        with self.assertRaisesRegex(ValueError,"OBJECT_METADATA_UNSAFE"):
            audit(p)

    def test_14_duplicate_index_different_hash_rejected(self):
        p=prepared()
        row=next(x for x in p[0].rows.values() if "_manifest_" in x["name"])
        duplicate=deepcopy(row)
        duplicate["id"]="duplicatedfile123"
        duplicate["name"]=row["name"].replace(
            row["name"].split("_")[-1][:-5],"f"*64)
        p[0].rows[duplicate["id"]]=duplicate
        with self.assertRaisesRegex(ValueError,"DUPLICATE_NAME_ID_OR_INDEX"):
            audit(p)

    def test_15_duplicate_name_different_id_rejected(self):
        p=prepared()
        row=next(x for x in p[0].rows.values() if "_manifest_" in x["name"])
        duplicate=deepcopy(row)
        duplicate["id"]="duplicatedfile567"
        p[0].rows[duplicate["id"]]=duplicate
        with self.assertRaisesRegex(ValueError,"DUPLICATE_NAME_ID_OR_INDEX"):
            audit(p)

    def test_16_missing_chunk_fails_before_media_reads(self):
        p=prepared()
        file_id=next(k for k,v in p[0].rows.items() if "_chunk_" in v["name"])
        del p[0].rows[file_id]
        with self.assertRaisesRegex(ValueError,"MISSING_OR_ORPHAN_V2_PAIR"):
            audit(p)
        self.assertEqual(p[0].reads,0)

    def test_17_missing_manifest_fails_before_media_reads(self):
        p=prepared()
        file_id=next(k for k,v in p[0].rows.items() if "_manifest_" in v["name"])
        del p[0].rows[file_id]
        with self.assertRaisesRegex(ValueError,"MISSING_OR_ORPHAN_V2_PAIR"):
            audit(p)
        self.assertEqual(p[0].reads,0)

    def test_18_historical_chunk_content_corrupted(self):
        p=prepared()
        row=next(v for v in p[0].rows.values() if "_chunk_" in v["name"])
        row["body"]["bars"][0]["close"]="9.9000"
        with self.assertRaises(ValueError):
            audit(p)

    def test_19_manifest_parent_tamper(self):
        p=prepared()
        row=next(v for v in p[0].rows.values() if "_manifest_" in v["name"])
        row["body"]["parent_manifest_sha256"]="a"*64
        with self.assertRaises(ValueError):
            audit(p)

    def test_20_supplied_tip_pin_fork_detected(self):
        p=prepared()
        with self.assertRaisesRegex(ValueError,"TIP_ROLLBACK_OR_FORK"):
            audit(p,tip="e"*64)

    def test_21_shortened_consistent_history_pin_is_not_trust(self):
        p=prepared(labels=H4[:1])
        r=audit(p)
        self.assertEqual(r.pair_count,1)
        self.assertFalse(r.independent_external_tail_witness_verified)

    def test_22_nonordered_pagination_is_sorted_exactly(self):
        p=prepared(page_length=2)
        self.assertEqual(audit(p).pair_count,3)
        self.assertGreater(p[0].lists,4)

    def test_23_repeated_page_token_denied(self):
        p=prepared()
        p[0].force_repeated_token=True
        with self.assertRaisesRegex(ValueError,"REPEATED_OR_INVALID_PAGE_TOKEN"):
            audit(p)

    def test_24_unbounded_pagination_denied(self):
        p=prepared()
        p[0].force_long_pagination=True
        with self.assertRaisesRegex(ValueError,"PAGE_SCAN_LIMIT_EXCEEDED"):
            audit(p)

    def test_25_bad_list_envelope_denied(self):
        p=prepared()
        p[0].force_wrong_envelope=True
        with self.assertRaisesRegex(ValueError,"BAD_DRIVE_LIST_ENVELOPE"):
            audit(p)

    def test_26_race_renamed_id_after_read_denied(self):
        p=prepared()
        p[0].force_change_on_third_list=True
        with self.assertRaisesRegex(ValueError,"LIST_CHANGED_DURING_AUDIT"):
            audit(p)

    def test_27_wrong_bucket_and_capacity_type_denied(self):
        p=prepared()
        store=V2NativeDriveReadOnlyStore(
            p[0],p[2],shard_capacity=2)
        with self.assertRaisesRegex(ValueError,"ONLY_CHUNK_AND_MANIFEST_READS"):
            store.scan("other")
        with self.assertRaisesRegex(ValueError,"READONLY_SCOPE_OR_CAPACITY_DENIED"):
            V2NativeDriveReadOnlyStore(p[0],p[2],shard_capacity=True)

    def test_28_v1_writer_and_workflow_are_not_wired(self):
        from pathlib import Path
        path=Path(".github/workflows/mfx-native-htf-incremental-commit.yml")
        content=path.read_text(encoding="utf-8")
        self.assertIn('cron: "25 * * * *"',content)
        self.assertNotIn("mfx_native_v2_drive_readonly",content)
        audit_code=Path("tools/run_mfx_native_htf_cache_audit.py").read_text(
            encoding="utf-8")
        self.assertNotIn("mfx_native_v2_drive_readonly",audit_code)
        self.assertEqual(audit(prepared()).drive_writes,0)

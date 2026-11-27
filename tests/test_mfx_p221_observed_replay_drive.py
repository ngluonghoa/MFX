"""P221 existing GET-only metadata adapter, hermetic tests."""
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
from unittest import TestCase
from unittest.mock import patch

from mfx_research.p219_m5_archive_time_prefixes import ObservedObjectTime
from mfx_research.p220_private_observed_six_tf import PrivateObservedReplay
from mfx_research.unified_modes import MfxMode
from tools import mfx_private_observed_replay_drive as adapter
from tools import run_mfx_v1_manual_drive_six_tf as manual
from test_mfx_v1_manual_signal_only_drive_output import mocked, settings
from test_mfx_v1_six_tf_sealed_archive_consumer import ASOF


class Response:
    def __init__(self, value):
        self.value = value

    def raise_for_status(self):
        pass

    def json(self):
        return self.value


class Session:
    def __init__(self, pages):
        self.pages = iter(pages)
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append((url, params, timeout))
        return Response(next(self.pages))


def item(scope, suffix="a", **overrides):
    folder, prefix, _ = adapter._SCOPES[scope]
    value = dict(id="private_object_" + suffix, name=prefix + suffix,
                 mimeType="application/json", parents=[folder],
                 createdTime="2026-11-12T12:00:00.123Z",
                 modifiedTime="2026-11-12T12:00:00.123Z")
    value.update(overrides)
    return value


class P221Tests(TestCase):
    def test_paginated_exact_scope_through_existing_proxy(self):
        upstream = Session([
            {"files": [item("m5_manifests","b")], "nextPageToken":"next"},
            {"files": [item("m5_manifests","a")]},
        ])
        proxy = manual.GetOnlyDriveSession(upstream)
        records = adapter._metadata(proxy, "m5_manifests")
        self.assertEqual([i for i,_ in records],
                         ["private_object_a","private_object_b"])
        self.assertEqual(proxy.get_count,2)
        self.assertEqual(upstream.calls[1][1]["pageToken"],"next")
        self.assertFalse(hasattr(proxy,"post"))

    def test_metadata_rejects_scope_duplicates_modified_partial(self):
        scope = "m5_manifests"
        for body in (
            {"files":[item(scope, parents=["foreign"])]},
            {"files":[item(scope),item(scope)]},
            {"files":[item(scope, modifiedTime="2026-11-12T13:00:00Z")]},
            {"files":[], "incompleteSearch":True},
        ):
            with self.subTest(body=body), self.assertRaises(ValueError):
                adapter._metadata(manual.GetOnlyDriveSession(Session([body])),scope)

    def test_repeated_page_token_rejected(self):
        with self.assertRaisesRegex(ValueError,"PAGINATION_TOKEN"):
            adapter._metadata(manual.GetOnlyDriveSession(Session([
                {"files":[], "nextPageToken":"same"},
                {"files":[], "nextPageToken":"same"},
            ])),"h4_chunks")

    def test_fixed_decision_cutoffs_before_and_at_recent_commits(self):
        t = datetime(2026,11,12,12,tzinfo=timezone.utc)
        items = tuple(ObservedObjectTime(str(i),t+timedelta(hours=i),
                                        t+timedelta(hours=i)) for i in range(3))
        now = t+timedelta(hours=4)
        decisions = adapter._decisions(items,now)
        self.assertEqual(decisions,(t+timedelta(hours=1,microseconds=-1),
                                    t+timedelta(hours=1),
                                    t+timedelta(hours=2,microseconds=-1),
                                    t+timedelta(hours=2),now))
        with self.assertRaises(ValueError):
            adapter._decisions(items,t)

    def test_integration_uses_same_get_only_probe_and_stores(self):
        evidence = mocked()
        replay = PrivateObservedReplay((),1,2,3,False)
        with patch.object(manual,"capture_replay_metadata",return_value={}) as capture, patch.object(manual,"consume_sealed_archives_for_six_tf",
                          return_value=evidence) as consume, patch.object(
                              manual,"observed_replay_in_existing_probe",
                              return_value=replay) as observed:
            result,count = manual.private_get_only_probe(Session([]),asof_utc=ASOF)
        self.assertEqual(result.private_observed_replay,replace(replay,replay_io_counts=(0,0,0)))
        capture.assert_called_once()
        self.assertEqual(observed.call_args.kwargs["metadata_before_audit"],{})
        self.assertEqual(count,0)
        args = observed.call_args.args
        self.assertIsInstance(args[0],manual.GetOnlyDriveSession)
        self.assertIs(args[2],consume.call_args.args[0])
        self.assertIs(args[3],consume.call_args.args[1])
        self.assertIs(args[4],consume.call_args.kwargs["owner_nov18_d1_epoch_store"])
        self.assertIs(args[5],consume.call_args.kwargs["revised_d1_research_store"])
        self.assertNotIn("private_observed_replay",repr(result))

    def test_p275_existing_audit_calls_explicit_validation(self):
        m5_tip, h4_tip = "a"*64, "b"*64
        evidence = replace(
            mocked(), active_d1_source_epoch="P192_D1_FRESH_20261118",
            m5_total_archived_manifest_pairs=1, h4_manifest_pairs_full_sha=1,
            m5_manifest_tip_sha256=m5_tip, h4_manifest_tip_sha256=h4_tip,
        )
        now = ASOF
        prior = now - timedelta(minutes=5)
        metadata = {key: () for key in adapter._SCOPES}
        for key, tip in (("m5_manifests", m5_tip), ("h4_manifests", h4_tip)):
            metadata[key] = (("fixture", ObservedObjectTime("m_"+tip+".json", prior, prior)),)
        expected = PrivateObservedReplay((),1,0,1,False)
        with patch.object(adapter, "replay_private_observed_six_tf", return_value=expected) as replay, patch.object(
                adapter, "capture_replay_metadata", return_value=metadata):
            actual = adapter.observed_replay_in_existing_probe(
                Session([]), evidence, None, None, None, None,
                asof_utc=now, metadata_before_audit=metadata,
            )
        self.assertIs(actual, expected)
        self.assertIs(replay.call_args.kwargs["mode"], MfxMode.VALIDATION)
        self.assertEqual(actual.public_summary()["action"], "NO_SIGNAL")
        self.assertFalse(actual.public_summary()["historical_oos_qualified"])

    def test_cli_projects_only_safe_aggregate(self):
        output = StringIO()
        replay = PrivateObservedReplay((),1,2,3,False)
        evidence = replace(mocked(),private_observed_replay=replay)
        with patch.dict("os.environ",settings(),clear=True), patch.object(
                manual,"_drive_auth_info",return_value=object()), patch.object(
                manual,"_require_oauth_cache_folders"), patch.object(
                manual,"_session",return_value=object()), patch.object(
                manual,"private_get_only_probe",return_value=(evidence,10)), redirect_stdout(output):
            manual.main()
        report = json.loads(output.getvalue().splitlines()[1])
        nested = report["p221_private_observed_replay"]
        self.assertEqual(nested,replay.public_summary())
        self.assertEqual(nested["action"],"NO_SIGNAL")
        self.assertFalse(nested["historical_oos_qualified"])
        self.assertNotIn("private_contexts",nested)

    def test_adapter_rejects_unselected_epoch_without_network(self):
        with self.assertRaisesRegex(ValueError,"OWNER_SELECTED"):
            adapter.observed_replay_in_existing_probe(
                Session([]),mocked(),None,None,None,None,asof_utc=ASOF)


class CountingStore:
    def __init__(self):
        self.value = {"nested": [{"value": "1"}]}
        self.reads = 0
        self.lists = 0

    def list_names(self, bucket):
        self.lists += 1
        return ("known",)

    def read(self, bucket, name):
        self.reads += 1
        return json.loads(json.dumps(self.value))


class P224CaptureTests(TestCase):
    def test_first_audit_keeps_independent_live_reads(self):
        store = CountingStore()
        view = manual.ReadOnlyView(store, capture=True)
        view.read("manifest","known")
        view.read("manifest","known")
        self.assertEqual(store.reads,2)
        view.freeze_for_replay()
        self.assertEqual(view.read("manifest","known"),store.value)
        self.assertEqual(store.reads,2)
        self.assertEqual(view.replay_reads,1)

    def test_frozen_replay_copies_and_live_namespace(self):
        store = CountingStore()
        view = manual.ReadOnlyView(store,capture=True)
        original = view.read("manifest","known")
        original["nested"][0]["value"]="mutated"
        view.freeze_for_replay()
        copied = view.read("manifest","known")
        self.assertEqual(copied["nested"][0]["value"],"1")
        copied["nested"][0]["value"]="changed"
        self.assertEqual(view.read("manifest","known"),store.value)
        self.assertEqual(store.reads,1)
        view.list_names("manifest")
        view.list_names("manifest")
        self.assertEqual(store.lists,2)

    def test_first_audit_changed_payload_fails(self):
        store = CountingStore()
        view = manual.ReadOnlyView(store,capture=True)
        view.read("manifest","known")
        store.value["nested"][0]["value"]="2"
        with self.assertRaisesRegex(ValueError,"REPEATED_LIVE_READ_DRIFT"):
            view.read("manifest","known")

    def test_unseen_object_never_falls_back_to_network(self):
        store = CountingStore()
        view = manual.ReadOnlyView(store,capture=True)
        view.read("manifest","known")
        view.freeze_for_replay()
        for bucket,name in (("manifest","new"),("chunk","known")):
            with self.assertRaisesRegex(ValueError,"UNAUDITED_REPLAY_OBJECT"):
                view.read(bucket,name)
        self.assertEqual(store.reads,1)

    def test_normal_store_unchanged_and_phase_one_way(self):
        store = CountingStore()
        view = manual.ReadOnlyView(store)
        view.read("manifest","known")
        store.value["nested"][0]["value"]="2"
        self.assertEqual(view.read("manifest","known"),store.value)
        with self.assertRaisesRegex(ValueError,"INVALID_CAPTURE_PHASE"):
            view.freeze_for_replay()
        capturing = manual.ReadOnlyView(store,capture=True)
        capturing.freeze_for_replay()
        with self.assertRaisesRegex(ValueError,"INVALID_CAPTURE_PHASE"):
            capturing.freeze_for_replay()

    def test_public_io_counts_are_not_second_independent_download(self):
        replay = PrivateObservedReplay((),1,2,3,False,replay_io_counts=(1250,10,900))
        d = replay.public_summary()["replay_io"]
        self.assertEqual(d["first_audit_gets_including_metadata"],1250)
        self.assertEqual(d["replay_live_gets"],10)
        self.assertEqual(d["replay_recorded_payload_reads"],900)
        self.assertFalse(d["second_independent_raw_download"])
        with self.assertRaisesRegex(ValueError,"IO_COUNT_DRIFT"):
            replace(replay,replay_io_counts=(-1,0,1)).public_summary()

    def test_metadata_capture_before_audit_uses_fixed_scopes(self):
        with patch.object(adapter,"_metadata",return_value=()) as m:
            result = adapter.capture_replay_metadata(object())
        self.assertEqual(set(result),set(adapter._SCOPES))
        self.assertEqual(m.call_count,len(adapter._SCOPES))

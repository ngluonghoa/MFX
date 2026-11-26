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
        with patch.object(manual,"consume_sealed_archives_for_six_tf",
                          return_value=evidence) as consume, patch.object(
                              manual,"observed_replay_in_existing_probe",
                              return_value=replay) as observed:
            result,count = manual.private_get_only_probe(Session([]),asof_utc=ASOF)
        self.assertIs(result.private_observed_replay,replay)
        self.assertEqual(count,0)
        args = observed.call_args.args
        self.assertIsInstance(args[0],manual.GetOnlyDriveSession)
        self.assertIs(args[2],consume.call_args.args[0])
        self.assertIs(args[3],consume.call_args.args[1])
        self.assertIs(args[4],consume.call_args.kwargs["owner_nov18_d1_epoch_store"])
        self.assertIs(args[5],consume.call_args.kwargs["revised_d1_research_store"])
        self.assertNotIn("private_observed_replay",repr(result))

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

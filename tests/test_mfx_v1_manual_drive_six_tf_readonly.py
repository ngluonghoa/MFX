"""MFX v1 manual Drive GET-only adapter: all hermetic, no actual OAuth."""
from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import replace
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from mfx_research.six_tf_sealed_archive_consumer import (
    SealedArchiveSixTFReceipt,
)
from tools.run_a04_p45_cloud_twelve_data_cache import (
    CHUNK_FOLDER, MANIFEST_FOLDER,
)
from tools.run_mfx_v1_manual_drive_six_tf import (
    CONFIRMATION, EXISTING_GATES, READ_APPROVAL,
    GetOnlyDriveSession, ReadOnlyView,
    manual_dispatch_authorized, private_get_only_probe,
    safe_summary, main,
)
from test_mfx_v1_six_tf_sealed_archive_consumer import (
    consume, fixtures,
)


class FakeGetSession:
    def __init__(self):
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append((url, params, timeout))
        return object()


def good_settings():
    return {
        READ_APPROVAL: "true",
        "MFX_V1_READONLY_CONFIRMATION": CONFIRMATION,
        **{gate: "true" for gate in EXISTING_GATES},
    }


def list_query(prefix="MFX_TD_EURUSD_M5_V2_manifest_",
               folder=MANIFEST_FOLDER):
    return {
        "q": (f"'{folder}' in parents and name contains "
              f"'{prefix}' and trashed = false"),
        "pageSize": 1000,
        "fields": "nextPageToken,files(id,name,mimeType,parents)",
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
    }


class ManualSixTFDriveTests(TestCase):
    def test_01_owner_gate_all_four_exact_values(self):
        self.assertTrue(manual_dispatch_authorized(good_settings()))

    def test_02_missing_new_owner_gate_fails_closed(self):
        cfg = good_settings()
        del cfg[READ_APPROVAL]
        self.assertFalse(manual_dispatch_authorized(cfg))

    def test_03_old_cache_gates_alone_never_enable(self):
        self.assertFalse(manual_dispatch_authorized(
            {gate: "true" for gate in EXISTING_GATES}))

    def test_04_missing_any_existing_gate_fails_closed(self):
        for gate in EXISTING_GATES:
            with self.subTest(gate=gate):
                cfg = good_settings()
                del cfg[gate]
                self.assertFalse(manual_dispatch_authorized(cfg))

    def test_05_readonly_ack_must_match_exact(self):
        for value in ("", "YES", "READ_ONLY", "read_only_no_signal"):
            with self.subTest(value=value):
                cfg = good_settings()
                cfg["MFX_V1_READONLY_CONFIRMATION"] = value
                self.assertFalse(manual_dispatch_authorized(cfg))

    def test_06_bad_type_and_boolean_true_rejected(self):
        self.assertFalse(manual_dispatch_authorized([]))
        cfg = good_settings()
        cfg[READ_APPROVAL] = True
        self.assertFalse(manual_dispatch_authorized(cfg))

    def test_07_get_only_wrapper_has_no_write_methods(self):
        s = GetOnlyDriveSession(FakeGetSession())
        for method in ("post", "put", "delete", "patch", "request"):
            self.assertFalse(hasattr(s, method))

    def test_08_fixed_m5_folder_prefix_list_get_allowed(self):
        source = FakeGetSession()
        proxy = GetOnlyDriveSession(source)
        proxy.get("https://www.googleapis.com/drive/v3/files",
                  params=list_query(), timeout=45)
        self.assertEqual(proxy.get_count, 1)
        self.assertEqual(len(source.calls), 1)

    def test_09_fixed_native_h4_d1_prefix_get_allowed(self):
        proxy = GetOnlyDriveSession(FakeGetSession())
        for prefix in ("MFX_TD_EURUSD_H4_NATIVE_V1_manifest_",
                       "MFX_TD_EURUSD_D1_NATIVE_V1_chunk_"):
            proxy.get("https://www.googleapis.com/drive/v3/files",
                      params=list_query(prefix, CHUNK_FOLDER), timeout=45)
        self.assertEqual(proxy.get_count, 2)

    def test_10_file_media_get_only_allowed(self):
        proxy = GetOnlyDriveSession(FakeGetSession())
        proxy.get("https://www.googleapis.com/drive/v3/files/Abc_123def45",
                  params={"alt": "media", "supportsAllDrives": "true"},
                  timeout=40)
        self.assertEqual(proxy.get_count, 1)

    def test_11_wrong_host_or_scheme_rejected_before_network(self):
        source = FakeGetSession()
        proxy = GetOnlyDriveSession(source)
        for url in (
            "https://api.twelvedata.com/time_series",
            "https://www.googleapis.com.evil.example/drive/v3/files",
            "http://www.googleapis.com/drive/v3/files",
            "https://www.googleapis.com:443/drive/v3/files",
            "https://www.googleapis.com/drive/v3/files?q=secret",
            "https://www.googleapis.com/drive/v3/files#fragment",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                proxy.get(url, params=list_query(), timeout=45)
        self.assertEqual(source.calls, [])

    def test_12_list_q_wrong_folder_denied(self):
        proxy = GetOnlyDriveSession(FakeGetSession())
        with self.assertRaisesRegex(ValueError, "LIST_SCOPE_DENIED"):
            proxy.get("https://www.googleapis.com/drive/v3/files",
                      params=list_query(folder="unauthorizedfolder123"),
                      timeout=45)

    def test_13_list_q_wrong_prefix_denied(self):
        proxy = GetOnlyDriveSession(FakeGetSession())
        with self.assertRaisesRegex(ValueError, "LIST_SCOPE_DENIED"):
            proxy.get("https://www.googleapis.com/drive/v3/files",
                      params=list_query(prefix="OtherProject_"), timeout=45)

    def test_14_list_without_trashed_filter_denied(self):
        proxy = GetOnlyDriveSession(FakeGetSession())
        p = list_query()
        p["q"] = p["q"].replace("and trashed = false", "")
        with self.assertRaisesRegex(ValueError, "LIST_SCOPE_DENIED"):
            proxy.get("https://www.googleapis.com/drive/v3/files",
                      params=p, timeout=45)

    def test_15_extra_arbitrary_list_argument_denied(self):
        proxy = GetOnlyDriveSession(FakeGetSession())
        p = list_query()
        p["fields"] = "nextPageToken"
        p["includePermissionForView"] = "published"
        with self.assertRaisesRegex(ValueError, "LIST_EXTRA_ARGUMENT"):
            proxy.get("https://www.googleapis.com/drive/v3/files",
                      params=p, timeout=45)

    def test_16_non_media_file_get_denied(self):
        proxy = GetOnlyDriveSession(FakeGetSession())
        with self.assertRaisesRegex(ValueError, "FILE_SCOPE_DENIED"):
            proxy.get("https://www.googleapis.com/drive/v3/files/Abc_123def45",
                      params={"fields": "id,permissions"}, timeout=45)

    def test_17_file_id_path_traversal_denied(self):
        proxy = GetOnlyDriveSession(FakeGetSession())
        with self.assertRaisesRegex(ValueError, "FILE_SCOPE_DENIED"):
            proxy.get("https://www.googleapis.com/drive/v3/files/abc/../../x",
                      params={"alt": "media", "supportsAllDrives": "true"},
                      timeout=45)

    def test_18_strict_read_only_store_view_no_put(self):
        m5, _, _, _ = fixtures()
        view = ReadOnlyView(m5)
        self.assertFalse(hasattr(view, "put_if_absent"))
        self.assertEqual(view.list_names("manifest"),
                         m5.list_names("manifest"))

    def test_19_bad_store_contract_rejected(self):
        with self.assertRaisesRegex(ValueError, "STORE_CONTRACT"):
            ReadOnlyView({})

    def test_20_probe_does_not_take_synthetic_pin_overrides(self):
        with self.assertRaises(TypeError):
            private_get_only_probe(
                FakeGetSession(),
                asof_utc=datetime(2026, 11, 12, tzinfo=timezone.utc),
                fixture_pins=object())

    def test_21_denied_cli_does_not_load_credentials(self):
        out = StringIO()
        with patch.dict("os.environ", {}, clear=True), \
             patch("tools.run_mfx_v1_manual_drive_six_tf._drive_auth_info",
                   side_effect=AssertionError("AUTH_MUST_NOT_BE_CALLED")), \
             redirect_stdout(out):
            main()
        self.assertIn("DISABLED_OWNER_GATE", out.getvalue())

    def test_22_enabled_cli_redacts_private_oauth_errors(self):
        out = StringIO()
        with patch.dict("os.environ", good_settings(), clear=True), \
             patch("tools.run_mfx_v1_manual_drive_six_tf._drive_auth_info",
                   side_effect=RuntimeError("PRIVATE_REFRESH_TOKEN_123")), \
             redirect_stdout(out):
            with self.assertRaises(SystemExit) as raised:
                main()
        self.assertEqual(raised.exception.code, 1)
        self.assertIn("FAILED_FAIL_CLOSED", out.getvalue())
        self.assertNotIn("PRIVATE_REFRESH_TOKEN", out.getvalue())

    def test_23_safe_summary_has_no_ohlc_or_secret_fields(self):
        mock = consume()
        # Tests may model reviewed pins, but this is NOT a real Drive proof.
        mock = replace(mock, github_reviewed_m5_anchors_checked=True)
        summary = safe_summary(mock, drive_gets=76)
        self.assertEqual(summary["action"], "NO_SIGNAL")
        self.assertEqual(summary["drive_reads"], 76)
        for forbidden in ("open", "high", "low", "close",
                          "credentials", "refresh_token", "file_id"):
            self.assertNotIn(forbidden, summary)

    def test_24_safe_summary_never_accepts_unreviewed_fixture(self):
        with self.assertRaisesRegex(ValueError, "UNSAFE"):
            safe_summary(consume(), drive_gets=1)

    def test_25_safe_summary_denies_flagged_buy(self):
        m = replace(consume(), github_reviewed_m5_anchors_checked=True,
                    may_publish_buy_sell=True)
        with self.assertRaisesRegex(ValueError, "UNSAFE"):
            safe_summary(m, drive_gets=1)

    def test_26_safe_summary_denies_uncertified_sha(self):
        m = replace(consume(), github_reviewed_m5_anchors_checked=True,
                    all_three_bounded_sha_chains_verified=False)
        with self.assertRaisesRegex(ValueError, "UNSAFE"):
            safe_summary(m, drive_gets=1)

    def test_27_safe_summary_denies_negative_or_fake_get_count(self):
        m = replace(consume(), github_reviewed_m5_anchors_checked=True)
        for n in (-1, True, 8001):
            with self.subTest(n=n), self.assertRaises(ValueError):
                safe_summary(m, drive_gets=n)

    def test_28_workflow_only_manual_and_no_cron_or_push_trigger(self):
        path = Path(".github/workflows/mfx-v1-manual-drive-six-tf-readonly.yml")
        text = path.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("\n  push:", text)
        self.assertNotIn("\n  pull_request:", text)
        self.assertIn("persist-credentials: false", text)

    def test_29_workflow_has_double_owner_guard_and_existing_scope(self):
        text = Path(
            ".github/workflows/mfx-v1-manual-drive-six-tf-readonly.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("inputs.confirm_read_only == 'READ_ONLY_NO_SIGNAL'", text)
        self.assertIn(
            "vars.MFX_V1_SIX_TF_MANUAL_READONLY_APPROVED == 'true'", text)
        for gate in EXISTING_GATES:
            self.assertIn("vars." + gate + " == 'true'", text)
        self.assertIn("group: mfx-twelvedata-private-cache", text)
        self.assertIn("contents: read", text)

    def test_30_workflow_has_no_vendor_secret_or_price_api(self):
        text = Path(
            ".github/workflows/mfx-v1-manual-drive-six-tf-readonly.yml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("MFX_TWELVE_DATA_API_KEY", text)
        self.assertNotIn("time_series", text)
        self.assertNotIn("api.twelvedata.com", text)
        self.assertIn("python -m tools.run_mfx_v1_manual_drive_six_tf", text)

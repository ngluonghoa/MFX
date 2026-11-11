"""A04/P0.54 independent per-pair / per-native-timeframe archive tests."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
import copy
import unittest

from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.native_htf_archive import (
    RECENT_INDEX_LIMIT, NativeSealedPlan, _name, _scope,
    check_native_manifest, plan_native_sealed, verify_native_sealed,
)

H4_LABELS = [
    "2026-11-10 00:00:00","2026-11-10 04:00:00",
    "2026-11-10 08:00:00","2026-11-10 12:00:00",
]
D1_LABELS = ["2026-11-06","2026-11-09","2026-11-10"]


def make_batch(interval: str = "4h", symbol: str = "EUR/USD",
               labels: list[str] | None = None,
               zone: str = "Australia/Sydney") -> NativeFXBatch:
    axis=("UTC_INTRADAY_OPEN" if interval=="4h"
          else "EXCHANGE_LOCAL_SESSION_DATE")
    selected=labels if labels is not None else (
        H4_LABELS[:2] if interval=="4h" else D1_LABELS[:2])
    bars=tuple(NativeFXBar(
        symbol=symbol,interval=interval,native_open_label=label,
        time_reference=axis,exchange_timezone=zone,
        open="1.1200",high="1.1250",low="1.1190",close="1.1230",
    ) for label in selected)
    return NativeFXBatch(
        symbol=symbol,interval=interval,exchange_timezone=zone,
        time_reference=axis,closed_bars=bars,incomplete_excluded=0,
    )


class P054NativeHTFArchiveTests(unittest.TestCase):
    def test_01_root_h4_is_exactly_two_sha_pinned_objects(self) -> None:
        p=plan_native_sealed(make_batch(),previous=None)
        assert p is not None
        verify_native_sealed(p,previous=None)
        self.assertEqual(p.newly_closed_bars,2)
        self.assertEqual(p.manifest["total_closed_native_bars"],2)
        self.assertEqual(p.manifest["batch_count"],1)
        self.assertIsNone(p.manifest["parent_manifest_sha256"])
        self.assertEqual(len(p.manifest_sha256),64)
        self.assertEqual(p.broker_orders,0)

    def test_02_root_daily_retains_exchange_local_date(self) -> None:
        p=plan_native_sealed(make_batch("1day"),previous=None)
        assert p is not None
        verify_native_sealed(p,previous=None)
        self.assertIn("D1_NATIVE_V1",p.chunk_name)
        self.assertIn("LOCAL",p.chunk_name)
        self.assertEqual(p.manifest["time_reference"],
                         "EXCHANGE_LOCAL_SESSION_DATE")
        self.assertEqual(p.chunk["bars"][0]["native_open_label"],"2026-11-06")
        self.assertNotIn("start_utc",p.chunk["bars"][0])

    def test_03_two_pairs_use_non_overlapping_drive_object_namespace(self) -> None:
        a=plan_native_sealed(make_batch(symbol="EUR/USD"),previous=None)
        b=plan_native_sealed(make_batch(symbol="GBP/USD"),previous=None)
        assert a and b
        self.assertNotEqual(a.chunk_name,b.chunk_name)
        self.assertTrue(a.chunk_name.startswith("MFX_TD_EURUSD_H4_NATIVE_V1_"))
        self.assertTrue(b.chunk_name.startswith("MFX_TD_GBPUSD_H4_NATIVE_V1_"))

    def test_04_two_native_timeframes_are_isolated(self) -> None:
        a=plan_native_sealed(make_batch(),previous=None)
        b=plan_native_sealed(make_batch("1day"),previous=None)
        assert a and b
        self.assertNotEqual(a.manifest_name,b.manifest_name)
        self.assertEqual(a.manifest["interval"],"4h")
        self.assertEqual(b.manifest["interval"],"1day")

    def test_05_second_hourly_batch_links_to_root_sha(self) -> None:
        root=plan_native_sealed(make_batch(),previous=None)
        assert root is not None
        next_batch=make_batch(labels=H4_LABELS)
        child=plan_native_sealed(next_batch,previous=root.manifest)
        assert child is not None
        verify_native_sealed(child,previous=root.manifest)
        self.assertEqual(child.manifest["parent_manifest_sha256"],
                         root.manifest_sha256)
        self.assertEqual(child.manifest["batch_count"],2)
        self.assertEqual(child.manifest["total_closed_native_bars"],4)
        self.assertEqual(child.newly_closed_bars,2)

    def test_06_repeat_same_closed_bars_is_idempotent_no_new_plan(self) -> None:
        root=plan_native_sealed(make_batch(),previous=None)
        assert root is not None
        self.assertIsNone(plan_native_sealed(
            make_batch(),previous=root.manifest))

    def test_07_late_old_overlap_does_not_rewrite_archive(self) -> None:
        root=plan_native_sealed(make_batch(labels=H4_LABELS),previous=None)
        assert root is not None
        self.assertIsNone(plan_native_sealed(
            make_batch(labels=H4_LABELS[:2]),previous=root.manifest))

    def test_08_revised_overlap_is_quarantined(self) -> None:
        root=plan_native_sealed(make_batch(),previous=None)
        assert root is not None
        changed=make_batch(labels=H4_LABELS[:3])
        bar=replace(changed.closed_bars[1],close="1.1240")
        changed=replace(changed,closed_bars=(
            changed.closed_bars[0],bar,changed.closed_bars[2]))
        with self.assertRaisesRegex(ValueError,"HISTORICAL_NATIVE_REVISION"):
            plan_native_sealed(changed,previous=root.manifest)

    def test_09_unsorted_native_rows_fail_closed(self) -> None:
        x=make_batch(labels=list(reversed(H4_LABELS[:2])))
        with self.assertRaisesRegex(ValueError,"NOT_SORTED"):
            plan_native_sealed(x,previous=None)

    def test_10_duplicate_native_labels_fail_closed(self) -> None:
        x=make_batch(labels=[H4_LABELS[0]]*2)
        with self.assertRaisesRegex(ValueError,"DUPLICATE_NATIVE"):
            plan_native_sealed(x,previous=None)

    def test_11_malformed_symbol_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError,"INVALID_PAIR"):
            plan_native_sealed(make_batch(symbol="EUR/EUR"),previous=None)

    def test_12_unsupported_m5_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError,"UNSUPPORTED_NATIVE_INTERVAL"):
            plan_native_sealed(make_batch(interval="5min"),previous=None)

    def test_13_h4_cannot_read_d1_parent(self) -> None:
        root=plan_native_sealed(make_batch("1day"),previous=None)
        assert root is not None
        with self.assertRaisesRegex(ValueError,"INVALID_MANIFEST"):
            plan_native_sealed(make_batch(),previous=root.manifest)

    def test_14_gbp_usd_cannot_reuse_eurusd_parent(self) -> None:
        root=plan_native_sealed(make_batch(),previous=None)
        assert root is not None
        with self.assertRaisesRegex(ValueError,"INVALID_MANIFEST"):
            plan_native_sealed(make_batch(symbol="GBP/USD"),
                               previous=root.manifest)

    def test_15_exchange_zone_change_is_denied(self) -> None:
        root=plan_native_sealed(make_batch(),previous=None)
        assert root is not None
        with self.assertRaisesRegex(ValueError,"INVALID_MANIFEST"):
            plan_native_sealed(
                make_batch(zone="America/New_York"),
                previous=root.manifest)

    def test_16_source_provenance_promotion_is_denied(self) -> None:
        x=make_batch()
        x=replace(x,closed_bars=(replace(
            x.closed_bars[0],source_numeric_strategy_approved=True),
            x.closed_bars[1]))
        with self.assertRaisesRegex(ValueError,"PROVENANCE"):
            plan_native_sealed(x,previous=None)

    def test_17_empty_batch_is_noop(self) -> None:
        self.assertIsNone(plan_native_sealed(
            make_batch(labels=[]),previous=None))

    def test_18_oversized_payload_rejected(self) -> None:
        labels=[f"2026-11-{1+i//24:02d} {i%24:02d}:00:00"
                for i in range(121)]
        with self.assertRaisesRegex(ValueError,"NATIVE_BATCH_SCOPE"):
            plan_native_sealed(make_batch(labels=labels),previous=None)

    def test_19_invalid_ohlc_rejected(self) -> None:
        x=make_batch()
        x=replace(x,closed_bars=(replace(
            x.closed_bars[0],high="1.1100"),x.closed_bars[1]))
        with self.assertRaisesRegex(ValueError,"INVALID_NATIVE_OHLC"):
            plan_native_sealed(x,previous=None)

    def test_20_nonfinite_quote_rejected(self) -> None:
        x=make_batch()
        x=replace(x,closed_bars=(replace(
            x.closed_bars[0],close="NaN"),x.closed_bars[1]))
        with self.assertRaisesRegex(ValueError,"INVALID_NATIVE_PRICE"):
            plan_native_sealed(x,previous=None)

    def test_21_wrong_exchange_zone_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError,"IANA_ZONE_INVALID"):
            plan_native_sealed(
                make_batch(zone="Mars/Deimos"),previous=None)

    def test_22_mutated_chunk_fails_sha_recomputation(self) -> None:
        p=plan_native_sealed(make_batch(),previous=None)
        assert p is not None
        corrupted=copy.deepcopy(p.chunk)
        corrupted["bars"][0]["close"]="1.1240"
        with self.assertRaisesRegex(ValueError,"IMMUTABLE_NATIVE_PAIR"):
            verify_native_sealed(replace(p,chunk=corrupted),previous=None)

    def test_23_mutated_manifest_fails_sha_recomputation(self) -> None:
        p=plan_native_sealed(make_batch(),previous=None)
        assert p is not None
        corrupted=copy.deepcopy(p.manifest)
        corrupted["total_closed_native_bars"]=999
        with self.assertRaisesRegex(ValueError,"IMMUTABLE_NATIVE_PAIR"):
            verify_native_sealed(replace(p,manifest=corrupted),previous=None)

    def test_24_wrong_parent_link_fails_recomputation(self) -> None:
        root=plan_native_sealed(make_batch(),previous=None)
        assert root is not None
        child=plan_native_sealed(
            make_batch(labels=H4_LABELS),
            previous=root.manifest)
        assert child is not None
        bad=copy.deepcopy(child.chunk)
        bad["parent_manifest_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"IMMUTABLE_NATIVE_PAIR"):
            verify_native_sealed(replace(child,chunk=bad),
                                 previous=root.manifest)

    def test_25_changed_name_without_content_denied(self) -> None:
        p=plan_native_sealed(make_batch(),previous=None)
        assert p is not None
        with self.assertRaisesRegex(ValueError,"IMMUTABLE_NATIVE_PAIR"):
            verify_native_sealed(replace(p,chunk_name=p.chunk_name+"x"),
                                 previous=None)

    def test_26_bad_bar_axis_denied(self) -> None:
        x=make_batch("1day")
        x=replace(x,closed_bars=(replace(
            x.closed_bars[0],time_reference="UTC_INTRADAY_OPEN"),
            x.closed_bars[1]))
        with self.assertRaisesRegex(ValueError,"PROVENANCE"):
            plan_native_sealed(x,previous=None)

    def test_27_broker_approval_denied(self) -> None:
        x=replace(make_batch(),broker_orders=1)
        with self.assertRaisesRegex(ValueError,"NATIVE_BATCH_SCOPE"):
            plan_native_sealed(x,previous=None)

    def test_28_recent_index_capped_and_sorted(self) -> None:
        # 30 real UTC 4-hour slots, not 30 hourly off-grid fixtures.
        first=datetime(2026,11,1,0,0,0)
        labels=[(first+timedelta(hours=4*i)).strftime("%Y-%m-%d %H:%M:%S")
                for i in range(30)]
        p=plan_native_sealed(make_batch(labels=labels),previous=None)
        assert p is not None
        self.assertEqual(len(p.manifest["recent_native_bar_index"]),
                         RECENT_INDEX_LIMIT)
        self.assertEqual(
            p.manifest["recent_native_bar_index"][-1]["label"],
            labels[-1])
        check_native_manifest(
            p.manifest,symbol="EUR/USD",interval="4h",
            zone="Australia/Sydney")

    def test_29_no_http_or_drive_in_native_archive_module(self) -> None:
        s=Path("mfx_cache/native_htf_archive.py").read_text(
            encoding="utf-8")
        self.assertNotIn("requests.get",s)
        self.assertNotIn("drive/v3",s)
        self.assertNotIn("broker.submit",s)
        self.assertNotIn("googleapiclient",s)
        y=Path(".github/workflows/twelve-data-cache.yml").read_text(
            encoding="utf-8")
        self.assertNotIn("native_htf_archive",y)
        self.assertIn('cron: "10 * * * *"',y)

    def test_30_daily_label_namespace_cannot_equal_h4(self) -> None:
        self.assertNotEqual(_scope("EUR/USD","4h"),
                            _scope("EUR/USD","1day"))
        x="0"*64
        self.assertNotEqual(
            _name("chunk","EUR/USD","4h",H4_LABELS[0],x),
            _name("chunk","EUR/USD","1day",D1_LABELS[0],x))


    def test_31_documented_timezone_origin_is_in_sha_sealed_chunk(self) -> None:
        base=make_batch("1day")
        from dataclasses import replace
        changed=replace(base,closed_bars=tuple(
            replace(row,exchange_timezone_origin=
                    "DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT")
            for row in base.closed_bars))
        a=plan_native_sealed(base,previous=None)
        b=plan_native_sealed(changed,previous=None)
        assert a and b
        verify_native_sealed(b,previous=None)
        self.assertNotEqual(a.chunk_sha256,b.chunk_sha256)
        self.assertEqual(
            b.chunk["bars"][0]["exchange_timezone_origin"],
            "DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT")

    def test_32_fallback_timezone_origin_other_pair_rejected(self) -> None:
        x=make_batch(symbol="GBP/USD")
        x=replace(x,closed_bars=tuple(
            replace(bar,exchange_timezone_origin=
                    "DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT")
            for bar in x.closed_bars))
        with self.assertRaisesRegex(ValueError,"TIMEZONE_PROVENANCE_INVALID"):
            plan_native_sealed(x,previous=None)

    def test_33_unrecognized_provenance_must_fail_closed(self) -> None:
        x=make_batch()
        x=replace(x,closed_bars=(
            replace(x.closed_bars[0],exchange_timezone_origin="UNVERIFIED"),
            x.closed_bars[1]))
        with self.assertRaisesRegex(ValueError,"TIMEZONE_PROVENANCE_INVALID"):
            plan_native_sealed(x,previous=None)


if __name__=="__main__":
    unittest.main()

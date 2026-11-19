"""P0.200 synthetic redacted forensic diagnostics on immutable P192 D1 hold."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import json
from unittest import TestCase

from mfx_cache.native_d1_epoch_20261118 import (
    audit_fresh_epoch, commit_fresh_epoch,
)
from mfx_cache.p200_p192_d1_sha_diff_forensics import (
    VERSION, diagnose_p192_owner_overlap,
)
from test_mfx_p171_d1_fresh_epoch import MemoryEpochStore, original_sha
from test_mfx_p192_d1_nov18_cutoff import AFTER, NEXT, source
from test_mfx_p192_native_writer_nov18 import P192RealWriterCutoffTests


def fixture():
    s = MemoryEpochStore()
    commit_fresh_epoch(
        s, batch=source(), origin_v1_sha=original_sha(), now_utc=AFTER,
    )
    state = audit_fresh_epoch(s, origin_v1_sha=original_sha())
    sealed = s.read("chunk", state.last_manifest["chunk_name"])
    return s, state, sealed


def classify(batch):
    _, state, chunk = fixture()
    return diagnose_p192_owner_overlap(
        state=state, sealed_chunk=chunk,
        refetched=batch, origin_v1_sha=original_sha(),
    )


def revise(field: str, value: str):
    original = source(include19=True)
    return replace(original, closed_bars=tuple(
        replace(bar, **{field: value})
        if bar.native_open_label == "2026-11-18" else bar
        for bar in original.closed_bars
    ))


class P200P192D1RedactedOverlapForensicsTests(TestCase):
    def test_01_actual_pattern_revised_18nov_numeric_detected_without_price(self):
        r = classify(source(include19=True, revised="2026-11-18"))
        self.assertEqual(r["schema"], VERSION)
        self.assertEqual(r["conflict_classification"],
                         "NUMERIC_OHLC_VALUE_CHANGED")
        self.assertEqual(r["overlap_sha_changed_count"], 1)
        self.assertEqual(r["numeric_ohlc_value_changed_count"], 1)
        self.assertEqual(r["overlap_missing_count"], 0)
        self.assertEqual((r["additional_vendor_requests"],
                          r["drive_reads_added_by_diagnostic"],
                          r["drive_writes"], r["broker_orders"]),
                         (0, 1, 0, 0))
        self.assertFalse(r["may_write_d1"])
        self.assertFalse(r["may_publish_buy_sell"])

    def test_02_missing_original_18nov_source_identified(self):
        r = classify(source(include18=False, include19=True))
        self.assertEqual(r["conflict_classification"], "MISSING_OVERLAP")
        self.assertEqual(r["overlap_missing_count"], 1)
        self.assertEqual(r["overlap_sha_changed_count"], 0)

    def test_03_metadata_only_different_exchange_timezone_origin(self):
        b = revise("exchange_timezone_origin", "PROVIDER_META")
        r = classify(b)
        self.assertEqual(r["conflict_classification"], "METADATA_ONLY_CHANGED")
        self.assertEqual(r["metadata_changed_count"], 1)
        self.assertEqual(r["numeric_ohlc_value_changed_count"], 0)

    def test_04_lexically_changed_number_without_real_price_change(self):
        b = source(include19=True)
        target = next(x for x in b.closed_bars
                      if x.native_open_label == "2026-11-18")
        b = revise("open", target.open + "0")
        r = classify(b)
        self.assertEqual(r["conflict_classification"],
                         "PRICE_TEXT_FORMAT_ONLY_CHANGED")
        self.assertEqual(r["price_text_format_changed_count"], 1)
        self.assertEqual(r["numeric_ohlc_value_changed_count"], 0)

    def test_05_normalized_same_source_is_not_a_forensic_incident(self):
        with self.assertRaisesRegex(ValueError, "QUARANTINE_SHOULD_PRECEDE"):
            classify(source(include19=True))

    def test_06_modified_sealed_raw_chunk_fails_independent_sha(self):
        _, st, chunk = fixture()
        chunk["bars"][0]["high"] = "9.99999"
        with self.assertRaises(ValueError):
            diagnose_p192_owner_overlap(
                state=st, sealed_chunk=chunk,
                refetched=source(include19=True, revised="2026-11-18"),
                origin_v1_sha=original_sha(),
            )

    def test_07_bad_owner_original_parent_refused(self):
        _, st, chunk = fixture()
        with self.assertRaises(ValueError):
            diagnose_p192_owner_overlap(
                state=st, sealed_chunk=chunk,
                refetched=source(include19=True, revised="2026-11-18"),
                origin_v1_sha="a"*64,
            )

    def test_08_never_publish_private_label_ohlc_or_sha_in_forensic_json(self):
        r = classify(source(include19=True, revised="2026-11-18"))
        j = json.dumps(r, sort_keys=True)
        for secret in ("2026-11-18", "2026-11-19", "1.1000",
                       '"open":', '"close":', '"high":', '"low":',
                       original_sha()):
            self.assertNotIn(secret, j)
        self.assertFalse(r["may_trade"])

    def test_09_real_scheduled_writer_path_still_quarantines_without_write(self):
        err, log, calls, store = P192RealWriterCutoffTests().run_job(
            clock=NEXT, revision=True,
        )
        self.assertEqual(err, "P192_NEW_EPOCH_OVERLAP_REVISION_QUARANTINE")
        self.assertEqual(store.puts, 2)  # exactly two pre-existing root objects
        self.assertEqual([tf for kind, tf in calls if kind == "vendor"],
                         ["1day"])
        self.assertIn("MFX_P200_P192_D1_SHA_DIFF_REDACTED_NO_COMMIT",log)
        self.assertNotIn("D1_20261118_OWNER_CUTOFF_SHA_READBACK_PASS",log)
        diagnostic = json.loads(log.splitlines()[-1])
        self.assertEqual(diagnostic["source_epoch"], "P192_D1_FRESH_20261118")
        self.assertEqual(diagnostic["numeric_ohlc_value_changed_count"], 1)
        self.assertFalse(diagnostic["may_write_d1"])
        self.assertEqual(diagnostic["drive_writes"], 0)

    def test_10_no_raw_source_bars_mutated_by_diagnostic(self):
        _, st, sealed = fixture()
        provider = source(include19=True, revised="2026-11-18")
        before = deepcopy((sealed, provider))
        diagnose_p192_owner_overlap(
            state=st, sealed_chunk=sealed, refetched=provider,
            origin_v1_sha=original_sha(),
        )
        self.assertEqual((sealed, provider), before)

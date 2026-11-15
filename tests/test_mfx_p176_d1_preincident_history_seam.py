"""P0.176 hermetic D1 seam: keep old SHA-proven pre-11 Nov history only.

No provider call, Drive write, broker order, public numeric BUY/SELL or
assertion of retroactive publisher first-known. Test fixture prices are SIM.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch

from mfx_cache.native_fx_htf import NativeFXBar, NativeFXBatch
from mfx_cache.td_m5_codec import digest
from mfx_research.p174_active_d1_epoch_reader import (
    SEAM_VERSION, MAX_RECENT_CONTEXT, read_active_d1_epoch,
    compose_verified_preincident_d1_history,
)
from mfx_research.six_tf_sealed_archive_consumer import (
    D1_HOLD_PUBLIC_STATUS,
)
from test_mfx_p174_active_d1_six_tf_readonly import (
    RESEARCH_ASOF, archived_tip, consume_offline, make_epoch,
    reviewed_inputs,
)
from test_mfx_v1_six_tf_sealed_archive_consumer import _native
from test_mfx_p171_d1_fresh_epoch import original_sha


def old_batch(labels=("2026-11-10","2026-11-11")):
    return _native("1day", tuple(labels))


def seam_inputs(*, archived=None):
    original=old_batch() if archived is None else archived
    epoch=make_epoch(origin=original_sha())
    root=epoch.list_names("manifest")[0]
    return original,epoch,digest(epoch.read("manifest",root))


def joined(*, original=None):
    original,epoch,root=seam_inputs(archived=original)
    with patch.multiple(
        "mfx_research.p174_active_d1_epoch_reader",
        PINNED_ORIGINAL_D1_V1_HEAD_SHA256=original_sha(),
        PINNED_FRESH_D1_20261111_ROOT_SHA256=root,
    ):
        fresh=read_active_d1_epoch(
            epoch,old_v1_manifest_sha256=original_sha(),
            asof_utc=RESEARCH_ASOF)
        out=compose_verified_preincident_d1_history(
            original,fresh,original_v1_head_sha256=original_sha())
    return out,original,epoch


class D1OwnerSeamTests(TestCase):
    def test_01_keeps_preincident_and_exact_new_day(self):
        r,old,_=joined()
        self.assertEqual(r.schema,SEAM_VERSION)
        self.assertEqual(r.last_preincident_label,"2026-11-10")
        self.assertEqual(r.first_fresh_label,"2026-11-11")
        self.assertEqual(
            [x.native_open_label for x in r.batch.closed_bars],
            ["2026-11-10","2026-11-11","2026-11-12","2026-11-13"])
        self.assertIs(r.batch.closed_bars[0],old.closed_bars[0])
        self.assertIsNot(r.batch.closed_bars[1],old.closed_bars[1])

    def test_02_disputed_old_11_nov_candle_cannot_enter(self):
        initial=old_batch()
        revised=replace(initial.closed_bars[-1],open="9.1000", high="9.1000",
                        low="9.1000",close="9.1000")
        old=replace(initial,closed_bars=initial.closed_bars[:-1]+(revised,))
        r,_,_=joined(original=old)
        self.assertNotIn("9.1000",[x.close for x in r.batch.closed_bars])
        self.assertNotEqual(r.batch.closed_bars[1],revised)

    def test_03_reuses_original_preincident_close_unchanged(self):
        original=old_batch()
        changed=replace(original.closed_bars[0],open="1.0240", high="1.0240",
                        low="1.0240",close="1.0240")
        original=replace(original,closed_bars=(changed,original.closed_bars[1]))
        r,_,_=joined(original=original)
        self.assertEqual(r.batch.closed_bars[0],changed)
        self.assertEqual(r.original_v1_preincident_bars_verified,1)
        self.assertEqual(r.new_epoch_bars_verified_in_context,3)
        self.assertEqual(r.context_bars_after_120_limit,4)

    def test_04_composes_120_bar_bounded_history(self):
        start=date(2026,11,11)-timedelta(days=119)
        labels=tuple((start+timedelta(days=n)).isoformat() for n in range(120))
        r,_,_=joined(original=old_batch(labels))
        self.assertEqual(r.original_v1_preincident_bars_verified,119)
        self.assertEqual(r.new_epoch_bars_verified_in_context,3)
        self.assertEqual(r.context_bars_after_120_limit,MAX_RECENT_CONTEXT)
        self.assertEqual(len(r.batch.closed_bars),120)
        self.assertEqual(r.batch.closed_bars[-1].native_open_label,
                         "2026-11-13")
        self.assertNotIn("2026-11-11",
                         [b.native_open_label for b in r.batch.closed_bars[:-3]])

    def test_05_original_latest_must_be_incident(self):
        for bad in (old_batch(("2026-11-09","2026-11-10")),
                    old_batch(("2026-11-10","2026-11-12"))):
            with self.subTest(labels=bad.closed_bars),self.assertRaisesRegex(
                    ValueError,"OLD_INCIDENT_OR_FRESH_SEQUENCE_MISMATCH"):
                joined(original=bad)

    def test_06_missing_preincident_nov10_denied(self):
        with self.assertRaisesRegex(ValueError,
                                    "PREINCIDENT_BOUNDARY_NOT_PROVEN"):
            joined(original=old_batch(("2026-11-09","2026-11-11")))

    def test_07_single_old_disputed_bar_cannot_be_only_history(self):
        with self.assertRaisesRegex(ValueError,
                                    "INDEPENDENT_SOURCE_SCOPE_OR_PIN_REQUIRED"):
            joined(original=old_batch(("2026-11-11",)))

    def test_08_duplicate_old_prior_label_denied(self):
        with self.assertRaisesRegex(ValueError,
                                    "OLD_INCIDENT_OR_FRESH_SEQUENCE_MISMATCH"):
            joined(original=old_batch(
                ("2026-11-10","2026-11-10","2026-11-11")))

    def test_09_reversed_old_native_history_denied(self):
        with self.assertRaisesRegex(ValueError,
                                    "OLD_INCIDENT_OR_FRESH_SEQUENCE_MISMATCH"):
            joined(original=old_batch(("2026-11-11","2026-11-10")))

    def test_10_unknown_old_provider_denied(self):
        bad=replace(old_batch(),source="UNTRUSTED_PROVIDER")
        with self.assertRaisesRegex(ValueError,
                                    "INDEPENDENT_SOURCE_SCOPE_OR_PIN_REQUIRED"):
            joined(original=bad)

    def test_11_wrong_old_price_side_denied(self):
        old=old_batch()
        bad=replace(old,closed_bars=(
            replace(old.closed_bars[0],price_side="ASK"),
            old.closed_bars[1]))
        with self.assertRaisesRegex(ValueError,"UNTRUSTED_BAR_PROVENANCE"):
            joined(original=bad)

    def test_12_existing_old_bar_cannot_be_marked_numeric_approved(self):
        old=old_batch()
        bad=replace(old,closed_bars=(
            replace(old.closed_bars[0],source_numeric_strategy_approved=True),
            old.closed_bars[1]))
        with self.assertRaisesRegex(ValueError,"UNTRUSTED_BAR_PROVENANCE"):
            joined(original=bad)

    def test_13_owner_selected_fresh_source_must_match_old_trust_head(self):
        old,epoch,root=seam_inputs()
        with patch.multiple("mfx_research.p174_active_d1_epoch_reader",
            PINNED_ORIGINAL_D1_V1_HEAD_SHA256=original_sha(),
            PINNED_FRESH_D1_20261111_ROOT_SHA256=root):
            fresh=read_active_d1_epoch(epoch,old_v1_manifest_sha256=original_sha(),
                                       asof_utc=RESEARCH_ASOF)
            with self.assertRaisesRegex(ValueError,
                                        "INDEPENDENT_SOURCE_SCOPE_OR_PIN_REQUIRED"):
                compose_verified_preincident_d1_history(
                    old,fresh,original_v1_head_sha256="a"*64)

    def test_14_new_source_last_date_mismatch_rejected(self):
        old,epoch,root=seam_inputs()
        with patch.multiple("mfx_research.p174_active_d1_epoch_reader",
            PINNED_ORIGINAL_D1_V1_HEAD_SHA256=original_sha(),
            PINNED_FRESH_D1_20261111_ROOT_SHA256=root):
            fresh=read_active_d1_epoch(epoch,old_v1_manifest_sha256=original_sha(),
                                       asof_utc=RESEARCH_ASOF)
            bad=replace(fresh,last_native_open_label="2026-11-14")
            with self.assertRaisesRegex(ValueError,
                                        "OLD_INCIDENT_OR_FRESH_SEQUENCE_MISMATCH"):
                compose_verified_preincident_d1_history(
                    old,bad,original_v1_head_sha256=original_sha())

    def test_15_new_source_unauthorized_signal_flag_denied(self):
        old,epoch,root=seam_inputs()
        with patch.multiple("mfx_research.p174_active_d1_epoch_reader",
            PINNED_ORIGINAL_D1_V1_HEAD_SHA256=original_sha(),
            PINNED_FRESH_D1_20261111_ROOT_SHA256=root):
            fresh=read_active_d1_epoch(epoch,old_v1_manifest_sha256=original_sha(),
                                       asof_utc=RESEARCH_ASOF)
            with self.assertRaisesRegex(ValueError,
                                        "INDEPENDENT_SOURCE_SCOPE_OR_PIN_REQUIRED"):
                compose_verified_preincident_d1_history(
                    old,replace(fresh,may_publish_buy_sell=True),
                    original_v1_head_sha256=original_sha())

    def test_16_private_batch_never_appears_in_repr(self):
        r,_,_=joined()
        line=repr(r)
        self.assertNotIn("NativeFXBar",line)
        self.assertNotIn("closed_bars",line)
        self.assertNotIn("1.10",line)
        self.assertEqual(len(r.composition_sha256),64)

    def test_17_deterministic_SHA_from_both_sources(self):
        x,_,_=joined()
        y,_,_=joined()
        self.assertEqual(x.composition_sha256,y.composition_sha256)
        self.assertEqual(x.original_v1_head_sha256,original_sha())
        self.assertNotEqual(x.active_epoch_head_sha256,x.original_v1_head_sha256)

    def test_18_no_mutations_or_repricing_when_joined(self):
        old,epoch,root=seam_inputs()
        before=deepcopy(epoch.files)
        with patch.multiple("mfx_research.p174_active_d1_epoch_reader",
            PINNED_ORIGINAL_D1_V1_HEAD_SHA256=original_sha(),
            PINNED_FRESH_D1_20261111_ROOT_SHA256=root):
            fresh=read_active_d1_epoch(epoch,old_v1_manifest_sha256=original_sha(),
                                       asof_utc=RESEARCH_ASOF)
            res=compose_verified_preincident_d1_history(
                old,fresh,original_v1_head_sha256=original_sha())
        self.assertEqual(epoch.files,before)
        self.assertEqual(epoch.puts,2)
        self.assertEqual((res.provider_requests,res.drive_writes,
                          res.broker_orders),(0,0,0))
        self.assertEqual(res.public_action,"NO_SIGNAL")
        self.assertFalse(res.may_trade)

    def test_19_integrated_real_mode_research_receipt_has_seam(self):
        m5,h4,old_store,pins=reviewed_inputs()
        active=make_epoch(origin=archived_tip(old_store))
        r=consume_offline(m5,h4,old_store,pins,active=active)
        self.assertEqual(r.active_d1_source_epoch,"P171_D1_FRESH_20261111")
        self.assertEqual(r.original_preincident_d1_rows_verified,1)
        self.assertEqual(r.new_epoch_d1_rows_in_context,3)
        self.assertEqual(len(r.active_d1_composed_history_sha256),64)
        self.assertIsNotNone(r.private_multibar)
        self.assertEqual(r.technical.action,"NO_SIGNAL")
        self.assertFalse(r.may_publish_buy_sell)
        self.assertFalse(r.may_trade)

    def test_20_without_explicit_fresh_source_legacy_hold_remains(self):
        m5,h4,old_store,pins=reviewed_inputs()
        r=consume_offline(m5,h4,old_store,pins)
        self.assertEqual(r.status,D1_HOLD_PUBLIC_STATUS)
        self.assertEqual(r.active_d1_composed_history_sha256,"")
        self.assertEqual(r.original_preincident_d1_rows_verified,0)

    def test_21_no_source_schedule_or_oauth_mutation(self):
        from pathlib import Path
        source=Path("mfx_research/p174_active_d1_epoch_reader.py").read_text()
        self.assertIn("compose_verified_preincident_d1_history",source)
        self.assertNotIn("requests.post(",source)
        self.assertNotIn("googleapiclient",source)
        self.assertNotIn("broker.submit",source)
        assert "NO_SIGNAL" in source

    def test_22_original_disputed_candle_not_in_120_context(self):
        first=date(2026,11,11)-timedelta(days=119)
        old=old_batch(tuple((first+timedelta(days=n)).isoformat()
                      for n in range(120)))
        # Exotic old incident bar makes accidental inclusion measurable.
        old=replace(old,closed_bars=old.closed_bars[:-1]+(
            replace(old.closed_bars[-1],
                    open="9.20",high="9.20",low="9.20",close="9.20"),))
        r,_,_=joined(original=old)
        self.assertNotIn("9.20",[b.close for b in r.batch.closed_bars])
        self.assertEqual(len(r.batch.closed_bars),120)

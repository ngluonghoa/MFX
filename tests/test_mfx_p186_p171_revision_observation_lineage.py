"""P0.186: hermetic, private D1 SHA-version lineage, strictly NO I/O."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from unittest import TestCase

from mfx_cache.p185_p171_d1_revision_review import build_p171_revision_review
from mfx_cache.p186_p171_revision_observation_lineage import (
    SCHEMA, MAX_ENTRIES, append_private_p171_observation,
    verify_private_p171_lineage, private_p171_versions_known_by_runner_asof,
    public_p171_lineage_status,
)
from mfx_cache.td_m5_codec import digest
from test_mfx_p180_d1_overlap_diagnosis import audited
from test_mfx_p185_p171_d1_revision_review import (
    OBSERVED, candidate, one_changed_refetch,
)

ROOT = candidate()["original_epoch_manifest_tip_sha256"]


def second_candidate(*, observed_at=OBSERVED+timedelta(hours=1),
                     high="1.9010"):
    _, state = audited()
    original = one_changed_refetch()
    newer = replace(original, closed_bars=tuple(
        replace(bar, high=high)
        if bar.native_open_label == "2026-11-12" else bar
        for bar in original.closed_bars
    ))
    return build_p171_revision_review(
        state=state, refetched=newer, runner_observed_utc=observed_at,
    )


def start():
    return append_private_p171_observation(
        (), candidate=candidate(), expected_p171_manifest_sha256=ROOT,
    )


def append(existing, newest):
    return append_private_p171_observation(
        existing, candidate=newest, expected_p171_manifest_sha256=ROOT,
    )


class P186P171PrivateObservationLineageTests(TestCase):
    def test_01_initial_root_and_sha_pair_are_private_and_unapproved(self):
        chain = start()
        self.assertEqual(len(chain), 1)
        self.assertEqual(chain[0]["schema"], SCHEMA)
        self.assertIsNone(chain[0]["previous_lineage_entry_sha256"])
        self.assertEqual(chain[0]["origin_p171_manifest_sha256"], ROOT)
        self.assertEqual(chain[0]["native_open_label"], "2026-11-12")
        self.assertFalse(chain[0]["may_publish_buy_sell"])
        self.assertFalse(chain[0]["may_write_drive"])
        self.assertEqual(verify_private_p171_lineage(
            chain, expected_p171_manifest_sha256=ROOT), chain)

    def test_02_sequential_changes_are_sha_parent_linked(self):
        chain = start()
        nxt = append(chain, second_candidate())
        self.assertEqual(len(nxt), 2)
        self.assertEqual(nxt[1]["sequence"], 2)
        self.assertEqual(nxt[1]["previous_lineage_entry_sha256"],
                         nxt[0]["entry_sha256"])
        self.assertNotEqual(nxt[0]["refetched_bar_sha256"],
                            nxt[1]["refetched_bar_sha256"])
        self.assertEqual(len(chain), 1)
        self.assertEqual(verify_private_p171_lineage(
            nxt, expected_p171_manifest_sha256=ROOT), nxt)

    def test_03_same_sha_is_idempotent_not_new_first_runner_date(self):
        chain = start()
        again = second_candidate(high="1.9000")
        self.assertEqual(append(chain, again), chain)
        self.assertEqual(append(chain, again)[0]["first_runner_observed_utc"],
                         OBSERVED.isoformat())

    def test_04_old_or_equal_runner_clock_must_not_advance(self):
        first = start()
        for clock in (OBSERVED-timedelta(seconds=1), OBSERVED):
            # This candidate is produced for an earlier/equal runner observation.
            new = second_candidate(observed_at=clock)
            with self.assertRaises(ValueError):
                append(first, new)

    def test_05_wrong_manifest_or_label_is_never_joined(self):
        first = start()
        with self.assertRaisesRegex(ValueError, "PRIVATE_CHAIN_INTEGRITY"):
            append_private_p171_observation(
                first, candidate=second_candidate(),
                expected_p171_manifest_sha256="f"*64,
            )
        wrong = deepcopy(second_candidate())
        wrong["revised_source_sha_pair"]["label"] = "2026-11-13"
        wrong["proposal_content_sha256"] = digest({
            k:v for k,v in wrong.items() if k!="proposal_content_sha256"
        })
        with self.assertRaises(ValueError):
            append(first, wrong)

    def test_06_tampered_parent_or_digests_fail_ledger_validation(self):
        chain = append(start(), second_candidate())
        for key,value in (("previous_lineage_entry_sha256","e"*64),
                          ("entry_sha256","e"*64),
                          ("first_runner_observed_utc",
                           "2026-11-17T13:30:00")):
            bad = deepcopy(chain)
            bad[1][key] = value
            with self.assertRaises(ValueError):
                verify_private_p171_lineage(
                    bad, expected_p171_manifest_sha256=ROOT)

    def test_07_rehashed_policy_forgery_is_not_source_authority(self):
        chain = start()
        for key,value in (
            ("owner_canonical_revision_approved",True),
            ("may_publish_buy_sell",True),
            ("may_write_drive",True),
            ("historical_asof_rewrite_allowed",True),
            ("source_account_rights_verified",True),
            ("source_publisher_first_known_verified",True),
            ("broker_orders",1),
        ):
            with self.subTest(key=key):
                bad = deepcopy(chain)
                bad[0][key] = value
                bad[0]["entry_sha256"] = digest({
                    k:v for k,v in bad[0].items() if k!="entry_sha256"
                })
                with self.assertRaises(ValueError):
                    verify_private_p171_lineage(
                        bad, expected_p171_manifest_sha256=ROOT)

    def test_08_reorder_truncate_and_malformed_fields_rejected(self):
        chain = append(start(), second_candidate())
        for bad in (tuple(reversed(chain)), (chain[1],),
                    ({**chain[0], "raw_ohlc":{"close":"secret"}},)):
            with self.assertRaises(ValueError):
                verify_private_p171_lineage(
                    bad, expected_p171_manifest_sha256=ROOT)
        for bad in (None, list(chain), tuple(chain)*40):
            with self.assertRaises(ValueError):
                verify_private_p171_lineage(
                    bad, expected_p171_manifest_sha256=ROOT)

    def test_09_public_report_exposes_only_counters(self):
        chain = append(start(), second_candidate())
        public = public_p171_lineage_status(
            chain, expected_p171_manifest_sha256=ROOT,
        )
        rendered = json.dumps(public, sort_keys=True)
        self.assertEqual(public["private_revision_observations"], 2)
        for secret in (
            "2026-11-12", "EUR/USD", ROOT,
            chain[0]["refetched_bar_sha256"], chain[1]["entry_sha256"],
            "native_open_label", "candidate_receipt_sha256",
            '"close"', '"open"',
        ):
            self.assertNotIn(secret, rendered)
        self.assertFalse(public["may_publish_buy_sell"])
        self.assertFalse(public["owner_canonical_revision_approved"])
        self.assertEqual(public["vendor_price_requests"], 0)
        self.assertEqual(public["drive_writes"], 0)

    def test_10_asof_returns_only_versions_seen_by_runner(self):
        chain = append(start(), second_candidate())
        for at, expected in (
            (OBSERVED-timedelta(seconds=1),0),
            (OBSERVED,1),
            (OBSERVED+timedelta(minutes=30),1),
            (OBSERVED+timedelta(hours=1),2),
        ):
            self.assertEqual(len(private_p171_versions_known_by_runner_asof(
                chain, expected_p171_manifest_sha256=ROOT,
                asof_utc=at,
            )), expected)
        with self.assertRaises(ValueError):
            private_p171_versions_known_by_runner_asof(
                chain, expected_p171_manifest_sha256=ROOT,
                asof_utc=datetime(2026,11,17,20,30),
            )

    def test_11_same_version_can_recur_later_as_new_event(self):
        first = start()
        second = append(first, second_candidate())
        back = candidate()
        # A returned old vendor version is a new observation, not the same
        # as idempotently fetching the current tail again.
        newer = deepcopy(back)
        newer["runner_observed_utc"] = (OBSERVED+timedelta(hours=2)).isoformat()
        newer["proposal_content_sha256"] = digest({
            k:v for k,v in newer.items() if k!="proposal_content_sha256"
        })
        third = append(second, newer)
        self.assertEqual(len(third),3)
        self.assertEqual(third[0]["refetched_bar_sha256"],
                         third[2]["refetched_bar_sha256"])
        self.assertEqual(third[1]["entry_sha256"],
                         third[2]["previous_lineage_entry_sha256"])

    def test_12_capacity_is_explicit_no_silent_discard(self):
        chain = start()
        for i in range(2, MAX_ENTRIES+1):
            version = second_candidate(
                observed_at=OBSERVED+timedelta(minutes=i),
                high=f"{1.9+i/10000:.4f}",
            )
            chain = append(chain, version)
        self.assertEqual(len(chain),MAX_ENTRIES)
        with self.assertRaisesRegex(ValueError, "CAPACITY_HOLD"):
            append(chain, second_candidate(
                observed_at=OBSERVED+timedelta(hours=3), high="1.9999",
            ))

    def test_13_live_store_and_candidate_are_unchanged(self):
        store,_ = audited()
        prior_store = deepcopy(store.files)
        before_puts = store.puts
        source = candidate()
        before = deepcopy(source)
        _ = append_private_p171_observation(
            (), candidate=source, expected_p171_manifest_sha256=ROOT,
        )
        self.assertEqual(store.files, prior_store)
        self.assertEqual(store.puts, before_puts)
        self.assertEqual(source,before)

    def test_14_untrusted_candidate_signoff_and_hash_denied(self):
        source = candidate()
        for key, value in (("may_write_d1",True),
                           ("owner_canonical_revision_approved",True),
                           ("proposal_content_sha256","f"*64)):
            bad = deepcopy(source)
            bad[key] = value
            with self.assertRaises(ValueError):
                append_private_p171_observation(
                    (), candidate=bad, expected_p171_manifest_sha256=ROOT,
                )

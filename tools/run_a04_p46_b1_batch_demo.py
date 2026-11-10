"""A04/P0.46-B1 hosted no-network two-object fake-Drive transaction demo."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any

from mfx_cache.td_m5_codec import ClosedM5Bar
from mfx_cache.v2_batch_commit import PrivateObjectStore, commit_hour


class FakeObjectStore(PrivateObjectStore):
    def __init__(self) -> None:
        self.files: dict[str, dict[str, dict[str, Any]]] = {
            "chunk": {}, "manifest": {},
        }

    def list_names(self, bucket: str) -> tuple[str, ...]:
        return tuple(sorted(self.files[bucket]))

    def read(self, bucket: str, name: str) -> dict[str, Any]:
        return self.files[bucket][name]

    def put_if_absent(
        self, bucket: str, name: str, body: dict[str, Any],
    ) -> None:
        if name in self.files[bucket]:
            if self.files[bucket][name] != body:
                raise ValueError("P046_B1_FAKE_IMMUTABLE_STORAGE_CONFLICT")
            return
        self.files[bucket][name] = body


def main() -> None:
    start = datetime(2026,11,10,12,tzinfo=timezone.utc)
    now = start + timedelta(hours=1,minutes=10)
    rows = tuple(ClosedM5Bar(
        start_utc=(start+timedelta(minutes=5*i)).isoformat(),
        open="1.1",high="1.2",low="1.0",close="1.12",
    ) for i in range(12))
    store = FakeObjectStore()
    first = commit_hour(store,now_utc=now,observed=rows)
    repeated = commit_hour(store,now_utc=now,observed=rows)
    if (first.status != "BATCH_COMMITTED"
            or repeated.status != "NOT_DUE_OR_INCOMPLETE_HOUR"
            or len(store.files["chunk"]) != 1
            or len(store.files["manifest"]) != 1):
        raise RuntimeError("P046_B1_IDEMPOTENT_BATCH_RECEIPT_FAILED")
    chunk = next(iter(store.files["chunk"].values()))
    if {f:len(c) for f,c in chunk["derived"].items()} != {
            "M15":4, "M30":2, "H1":1}:
        raise RuntimeError("P046_B1_EXACT_M5_DERIVATION_FAILED")
    print("MFX_A04_P46_B1_STAGED_HOURLY_DRIVE_NO_NETWORK_PASS")
    print("MFX_A04_P46_B1_RECEIPT "+json.dumps({
        "stage":"CLOUD_ONLY_SYNTHETIC_NOT_REAL_VENDOR",
        "closed_m5_batch":12,
        "derived_counts":{"M15":4,"M30":2,"H1":1},
        "committed_objects":2,
        "duplicate_commits":0,
        "explicit_second_activation_flag_required":True,
        "actual_market_provider_calls":0,
        "actual_google_drive_writes":0,
        "real_user_buy_sell_signals":0,
        "broker_orders":0,
        "real_cache_activation_verified":False,
    },sort_keys=True))


if __name__ == "__main__":
    main()

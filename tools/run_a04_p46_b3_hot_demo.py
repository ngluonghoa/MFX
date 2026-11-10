"""A04/P0.46-B3 hosted synthetic five-minute HOT overlay receipt.

This is deliberately NOT connected to real Twelve Data, Drive, MOCHI,
the original Forex detectors, alerts or a broker.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from typing import Any

from mfx_cache.td_m5_codec import ClosedM5Bar
from mfx_cache.v3_hot_overlay import HOT_NAME, commit_hot, freshness


class MemoryHotPort:
    def __init__(self)->None:
        self.state:dict[str,Any]|None=None
        self.new_files=0
        self.in_place_updates=0

    def load(self)->dict[str,Any]|None:
        return deepcopy(self.state)

    def write(self,*,expected:dict[str,Any]|None,
              replacement:dict[str,Any])->None:
        if self.state!=expected:
            raise ValueError("P046_B3_DEMO_STALE_READER")
        if self.state is None:
            self.new_files+=1
        else:
            self.in_place_updates+=1
        self.state=deepcopy(replacement)


def _bars(start:datetime)->tuple[ClosedM5Bar,...]:
    return tuple(ClosedM5Bar(
        start_utc=(start+timedelta(minutes=5*i)).isoformat(),
        open="1.1",high="1.2",low="1.0",close="1.15",
    ) for i in range(16))


def main()->None:
    start=datetime(2026,11,10,12,10,tzinfo=timezone.utc)
    now=datetime(2026,11,10,13,30,30,tzinfo=timezone.utc)
    port=MemoryHotPort()
    first=commit_hot(port,_bars(start),now_utc=now)
    duplicate=commit_hot(port,_bars(start),now_utc=now+timedelta(seconds=20))
    later=now+timedelta(minutes=5)
    second=commit_hot(
        port,_bars(start+timedelta(minutes=5)),now_utc=later,
    )
    state=port.load()
    if state is None:
        raise RuntimeError("P046_B3_DEMO_NO_HOT")
    q=freshness(state,now_utc=later)
    if (first.new_closed_m5!=16 or duplicate.new_state is not None
            or second.new_closed_m5!=1 or port.new_files!=1
            or port.in_place_updates!=1 or not q.research_data_usable
            or q.live_buy_sell_authorized or q.broker_orders_authorized):
        raise RuntimeError("P046_B3_SYNTHETIC_HOT_CONTRACT_FAILURE")
    print("MFX_A04_P46_B3_CLOUD_SYNTHETIC_HOT_NO_SIGNAL_PASS")
    print("MFX_A04_P46_B3_RECEIPT "+json.dumps({
        "scope":"SYNTHETIC_FIVE_MINUTE_CLOSED_MID_M5",
        "single_fixed_overlay_name":HOT_NAME,
        "new_file_objects_after_two_new_bar_cycles":port.new_files,
        "in_place_overwrites_after_two_new_bar_cycles":port.in_place_updates,
        "unchanged_cycle_creates_or_updates":0,
        "latest_closed_m5_quality":q.status,
        "recent_closed_m5":q.recent_closed_m5,
        "licensed_raw_provider_access_verified":False,
        "actual_twelve_data_queries":0,
        "actual_google_drive_writes":0,
        "real_trading_signals":0,
        "broker_orders":0,
        "multi_writer_atomic_cas_proven":False,
    },sort_keys=True))


if __name__=="__main__":
    main()

"""Backward-compatible P2.1-B entrypoint for synthetic Forex staging.

The historical M2/P0.8 public names are re-exported by identity. New code
should import cache state from synthetic_drive_cache_store and fixture scan
orchestration from synthetic_drive_scan_orchestrator respectively.

Neither module provides network, Google Drive IO, licensed quotes, persistence,
real-time scans, Backtest or trading permissions.
"""
# Retain originally importable names where existing callers may rely on them.
from .cache_core import (
    CandleSnapshot, IncrementalPolicy, RefreshMode,
    plan_incremental_refresh, reconcile_closed_delta,
)
from .cache_storage_review import (
    SyntheticGenerationManifest, make_synthetic_generation,
    validate_synthetic_generation_chain,
)
from .market_data import BarSide, Timeframe
from .quotes import ensure_utc
from .scan_contract import ScanMode, ScanSelection, plan_scan_selection
from .synthetic_drive_cache_store import (
    SyntheticCacheAction, SyntheticChunk, SyntheticDriveCacheStaging,
)
from .synthetic_drive_scan_orchestrator import (
    MixedScanResult, run_mixed_scope_synthetic_drive_scan,
)

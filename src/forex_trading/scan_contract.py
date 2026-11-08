"""Pure read-only Forex pair selection contract, independent of synthetic scan workloads.

The externally supplied 20-pair catalog is metadata, not authorization to fetch
licensed market data or trade. This module performs no IO or cache updates.
"""
from dataclasses import dataclass
from enum import Enum
from re import fullmatch


class ScanMode(str, Enum):
    SINGLE = "SINGLE"
    CUSTOM = "CUSTOM"
    ALL = "ALL"


@dataclass(frozen=True, slots=True)
class ScanSelection:
    mode: ScanMode
    universe: tuple[str, ...]
    selected_pairs: tuple[str, ...]
    skipped_pairs: tuple[str, ...]
    # Metadata-only, not a quote-loading plan or permission to use a provider.
    may_fetch_real_data: bool = False
    may_trade: bool = False


def plan_scan_selection(
    universe: tuple[str, ...],
    mode: ScanMode,
    requested_pairs: tuple[str, ...] = (),
) -> ScanSelection:
    """SINGLE=1; CUSTOM=2..19; ALL=20, with no unselected pairs scanned.

    Validate membership without loading candle histories for all 20 pairs.
    No hardcoded external-source symbol mapping is implied.
    """
    if not isinstance(universe, tuple) or len(universe) != 20:
        raise ValueError("TWENTY_PAIR_CATALOG_REQUIRED")
    if any(
        not isinstance(pair, str)
        or not fullmatch(r"[A-Z][A-Z0-9_]{2,31}", pair)
        for pair in universe
    ):
        raise ValueError("INVALID_CATALOG_INSTRUMENT")
    if len(set(universe)) != 20:
        raise ValueError("DUPLICATE_CATALOG_INSTRUMENT")
    if not isinstance(mode, ScanMode):
        raise TypeError("TYPED_SCAN_MODE_REQUIRED")
    if not isinstance(requested_pairs, tuple):
        raise TypeError("IMMUTABLE_REQUESTED_PAIRS_REQUIRED")
    if any(not isinstance(pair, str) for pair in requested_pairs):
        raise TypeError("INVALID_REQUESTED_PAIR_TYPE")
    if len(set(requested_pairs)) != len(requested_pairs):
        raise ValueError("DUPLICATE_REQUESTED_PAIR")
    if any(pair not in universe for pair in requested_pairs):
        raise ValueError("PAIR_NOT_IN_APPROVED_CATALOG")

    selected: tuple[str, ...]
    if mode is ScanMode.SINGLE:
        if len(requested_pairs) != 1:
            raise ValueError("SINGLE_REQUIRES_EXACTLY_ONE_PAIR")
        selected = requested_pairs
    elif mode is ScanMode.CUSTOM:
        if not 2 <= len(requested_pairs) <= 19:
            raise ValueError("CUSTOM_REQUIRES_TWO_TO_NINETEEN_PAIRS")
        selected = requested_pairs
    else:
        if requested_pairs:
            raise ValueError("ALL_MODE_TAKES_NO_PAIR_SELECTION")
        selected = universe

    chosen = set(selected)
    return ScanSelection(mode, universe, selected, tuple(
        pair for pair in universe if pair not in chosen
    ))


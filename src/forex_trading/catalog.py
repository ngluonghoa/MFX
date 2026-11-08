"""The approved design taxonomy, NOT executable signal predicates."""
from collections import Counter
from .model import ZoneDefinition, ZonePurpose

P = ZonePurpose

ZONES: tuple[ZoneDefinition, ...] = (
    ZoneDefinition("B1", "F1_MAJOR_REVERSAL", P.ENTRY_LONG_CANDIDATE),
    ZoneDefinition("B2", "F2_TREND_PULLBACK", P.ENTRY_LONG_CANDIDATE),
    ZoneDefinition("B3", "F3_RANGE_REJECTION", P.ENTRY_LONG_CANDIDATE),
    ZoneDefinition("B4", "F4_FIRST_HL", P.ENTRY_LONG_CANDIDATE),
    ZoneDefinition("B5", "F5_BREAK_RETEST", P.ENTRY_LONG_CANDIDATE),
    ZoneDefinition("B6", "F6_COMPRESSION", P.ENTRY_LONG_CANDIDATE),
    ZoneDefinition("B7", "COUNTERTREND_WATCH", P.WATCH_ONLY),
    ZoneDefinition("B8", "F7_MOMENTUM_BREAK", P.ENTRY_LONG_CANDIDATE),
    ZoneDefinition("S1", "F1_MAJOR_REVERSAL", P.ENTRY_SHORT_CANDIDATE),
    ZoneDefinition("S2", "F2_TREND_PULLBACK", P.ENTRY_SHORT_CANDIDATE),
    ZoneDefinition("S3", "LONG_PROTECTION_WARNING", P.EXIT_LONG_WARNING_ONLY),
    ZoneDefinition("S4", "F3_RANGE_REJECTION", P.ENTRY_SHORT_CANDIDATE),
    ZoneDefinition("S5", "F4_FIRST_LH", P.ENTRY_SHORT_CANDIDATE),
    ZoneDefinition("S6", "F8_FALSE_UP_BREAK", P.ENTRY_SHORT_CANDIDATE),
    ZoneDefinition("S7", "F5_BREAK_RETEST", P.ENTRY_SHORT_CANDIDATE),
    ZoneDefinition("S8", "LONG_PROTECTION_WARNING", P.EXIT_LONG_WARNING_ONLY),
    ZoneDefinition("FX-S9", "F6_BEARISH_COMPRESSION", P.ENTRY_SHORT_CANDIDATE),
    ZoneDefinition("FX-S10", "F7_BEARISH_MOMENTUM", P.ENTRY_SHORT_CANDIDATE),
)


def validate_catalog(zones: tuple[ZoneDefinition, ...]) -> None:
    """Check identity, purpose and forbidden research promotions; no fixed quota."""
    seen: set[str] = set()
    for zone in zones:
        if not isinstance(zone, ZoneDefinition):
            raise TypeError("Unrecognized zone manifest record")
        if zone.label in seen:
            raise ValueError("Duplicate zone label")
        if zone.label == "FX-B9":
            raise ValueError("FX-B9 is research-only, not an approved catalog label")
        seen.add(zone.label)


def catalog_counts(zones: tuple[ZoneDefinition, ...]) -> dict[ZonePurpose, int]:
    validate_catalog(zones)
    result = Counter(z.purpose for z in zones)
    return {p: result[p] for p in ZonePurpose}


validate_catalog(ZONES)

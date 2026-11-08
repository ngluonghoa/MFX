"""First-class Forex domain vocabulary; statuses are not broker instructions."""
from dataclasses import dataclass
from enum import Enum


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class Horizon(str, Enum):
    FAST = "FAST"
    SWING = "SWING"


class ActionIntent(str, Enum):
    ENTRY_LONG = "ENTRY_LONG"
    EXIT_LONG = "EXIT_LONG"
    ENTRY_SHORT = "ENTRY_SHORT"
    EXIT_SHORT = "EXIT_SHORT"


class SignalStage(str, Enum):
    WAIT_EARLY = "WAIT_EARLY"
    WAIT = "WAIT"
    EARLY_SIGNAL = "EARLY_SIGNAL"
    CONFIRMED_SIGNAL = "CONFIRMED_SIGNAL"
    NO_TRADE = "NO_TRADE"
    UNVERIFIED = "UNVERIFIED"
    ERROR = "ERROR"


class ZonePurpose(str, Enum):
    ENTRY_LONG_CANDIDATE = "ENTRY_LONG_CANDIDATE"
    ENTRY_SHORT_CANDIDATE = "ENTRY_SHORT_CANDIDATE"
    WATCH_ONLY = "WATCH_ONLY"
    EXIT_LONG_WARNING_ONLY = "EXIT_LONG_WARNING_ONLY"


@dataclass(frozen=True, slots=True)
class ZoneDefinition:
    label: str
    family: str
    purpose: ZonePurpose

    def __post_init__(self) -> None:
        if not self.label or not self.family:
            raise ValueError("Zone label and family are required")
        if not isinstance(self.purpose, ZonePurpose):
            raise TypeError("Purpose must use ZonePurpose")


@dataclass(frozen=True, slots=True)
class SignalDisplay:
    direction: Direction
    horizon: Horizon
    stage: SignalStage
    zone_label: str | None
    source_verified: bool
    reason: str

    def __post_init__(self) -> None:
        if not all((isinstance(self.direction, Direction),
                    isinstance(self.horizon, Horizon),
                    isinstance(self.stage, SignalStage))):
            raise TypeError("Direction, horizon and stage must be typed enums")
        if not self.reason:
            raise ValueError("Evidence reason is mandatory")
        if self.stage in (SignalStage.EARLY_SIGNAL, SignalStage.CONFIRMED_SIGNAL):
            if not self.source_verified or self.zone_label is None:
                raise ValueError("Cannot display a signal without verified source and zone")
        # Even a verified display is NOT broker permission.

"""M1 design contract for 8 pipeline stages. Not an executable market scanner."""
from dataclasses import dataclass
from enum import Enum

STEPS: tuple[str, ...] = (
    "DATA_MANAGER",
    "VALIDATOR",
    "ANALYSIS",
    "POSITION_AND_EXIT_PROTECTION",
    "ZONE_DETECTION",
    "SIGNAL_ENGINE",
    "AUDIT_AND_DECISION",
    "REPORT_AND_HISTORY",
)


class StepStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class PipelineSnapshot:
    step_states: tuple[tuple[str, StepStatus], ...]

    def __post_init__(self) -> None:
        if tuple(name for name, _ in self.step_states) != STEPS:
            raise ValueError("Exactly eight ordered pipeline stages required")
        if any(not isinstance(state, StepStatus) for _, state in self.step_states):
            raise TypeError("A stage's state must be explicit")


def can_publish_full_analysis(snapshot: PipelineSnapshot) -> bool:
    """All steps COMPLETE is necessary, never sufficient for trade permission."""
    return all(state is StepStatus.COMPLETE for _, state in snapshot.step_states)

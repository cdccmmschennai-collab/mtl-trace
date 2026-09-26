from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass(frozen=True)
class Issue:
    """A validation/processing finding, located as precisely as the input allows."""
    severity: Severity
    code: str
    message: str
    rows: tuple[int, ...] = ()      # 1-based worksheet row numbers
    column: str | None = None       # worksheet column letter
    value: str | None = None

from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    # Expected, informational: what a document does not carry (no `TAG NUMBER AS PER DOC` column) or a column
    # deliberately left alone (a cross-reference). Shown with the document, never flags it as needing attention.
    INFO = "INFO"


@dataclass(frozen=True)
class Issue:
    """A validation/processing finding, located as precisely as the input allows."""
    severity: Severity
    code: str
    message: str
    rows: tuple[int, ...] = ()      # 1-based worksheet row numbers
    column: str | None = None       # worksheet column letter
    value: str | None = None

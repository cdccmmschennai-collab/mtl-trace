"""Comparison rules loaded from `rules/<version>.yaml` (TRD §18: rules are data, not code)."""

from dataclasses import dataclass
from pathlib import Path

import yaml

ALLOWED_STATES = ("MATCH", "MISMATCH", "REVIEW REQUIRED")


class RulesError(ValueError):
    pass


@dataclass(frozen=True)
class Rules:
    version: str
    source_priority: tuple[str, ...]          # rank 1 first
    trim: bool
    case_insensitive: bool
    milestone_anchored: frozenset[str]        # attribute codes compared against the milestone tag
    manufacturer_names: frozenset[str] = frozenset()   # attribute codes holding a manufacturer name

    def rank(self, source_type: str) -> int:
        try:
            return self.source_priority.index(source_type)
        except ValueError:
            raise RulesError(f"Source type '{source_type}' has no priority rank in rules {self.version}.") from None

    def key(self, value: str | None) -> str | None:
        """The comparison value of a source value. Raw values are never changed; this is used for equality only."""
        if value is None:
            return None
        if self.trim:
            value = value.strip()
        if not value:
            return None
        return value.casefold() if self.case_insensitive else value


def load_rules(path: Path) -> Rules:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    states = tuple(data.get("states", ()))
    if states != ALLOWED_STATES:
        raise RulesError(f"Rules {path.name} define states {states}; exactly {ALLOWED_STATES} are allowed.")
    priority = tuple(data["source_priority"])
    if len(set(priority)) != len(priority):
        raise RulesError(f"Rules {path.name} list a source type twice in source_priority.")
    norm = data.get("normalization", {})
    return Rules(version=str(data["version"]), source_priority=priority, trim=bool(norm.get("trim", True)),
                 case_insensitive=bool(norm.get("case_insensitive", True)),
                 milestone_anchored=frozenset(data.get("milestone_anchored_attributes", ())),
                 manufacturer_names=frozenset(data.get("manufacturer_name_attributes", ())))

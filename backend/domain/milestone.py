"""Milestone domain rules.

A milestone is a finalized business scope (e.g. `MTL-2026-001`, 717 tags). It is distinct from a
processing run: a run is one processing attempt against a milestone's *locked* scope, and a milestone
accumulates many runs over time.
"""

import re
from enum import StrEnum


class MilestoneStatus(StrEnum):
    DRAFT = "DRAFT"                  # scope may be imported / replaced
    SCOPE_LOCKED = "SCOPE_LOCKED"    # scope is frozen; runs may be attached


class ScopeStatus(StrEnum):
    """Derived, user-facing view of the scope lifecycle."""
    NONE = "NONE"          # no scope imported yet
    DRAFT = "DRAFT"        # imported, still replaceable
    LOCKED = "LOCKED"      # frozen


# The milestone code names a folder under MTL_DATA/milestones/, so it must be filesystem-safe on Windows.
_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}


def validate_milestone_code(code: str) -> str | None:
    """Return an error message, or None when the code is acceptable."""
    if not code:
        return "Milestone ID is required."
    if not _CODE_PATTERN.match(code):
        return ("Milestone ID must start with a letter or digit and contain only letters, digits, "
                "'.', '-' or '_' (max 64 characters).")
    if code.endswith("."):
        return "Milestone ID must not end with '.'."
    if code.split(".")[0].upper() in _WINDOWS_RESERVED:
        return f"'{code}' is a reserved name on Windows and cannot be used as a Milestone ID."
    return None


def scope_status(status: str, tag_count: int) -> ScopeStatus:
    if status == MilestoneStatus.SCOPE_LOCKED:
        return ScopeStatus.LOCKED
    return ScopeStatus.DRAFT if tag_count else ScopeStatus.NONE

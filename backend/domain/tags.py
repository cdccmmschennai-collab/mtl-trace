"""Central tag normalization (TRD §14).

Every component that turns a tag into a lookup key must use `normalize_tag`, so the milestone scope
and every source adapter agree on what "the same tag" means.

Only evidence-backed normalization is applied (SPEC_VALIDATION_REPORT CR-5): trim surrounding
whitespace and compare case-insensitively. No punctuation stripping, no internal-whitespace collapsing,
no prefix handling — `88-LT-802` and `88-LIT-802` are different tags.
"""


def normalize_tag(tag: str) -> str:
    return tag.strip().upper()

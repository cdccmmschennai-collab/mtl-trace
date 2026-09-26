"""Semantic header discovery for source documents — ONE rule set for every source type.

A source is never described by a fixed field list. Each header is classified on its own, by keyword,
after `normalize_header`:

    header → strip document qualifiers → core keyword phrase → concept

Document qualifiers say *where* a value was read, not *what* it is:
    - the suffix `AS PER DOC` / `AS PER DOCUMENT`   (Data Sheet: `TAG NUMBER AS PER DOC`)
    - one source-type phrase, leading or trailing     (SPIR: `SPIR TAG NUMBER`; `MTC MAKE`; `O&M MODEL`)
      — the registered codes, summary codes and keywords (`backend.domain.sources.SOURCE_TYPES`)

Core phrases (TRD §12.1 controlled alias table, confirmed on the real Data Sheet and SPIR files):

    TAG · TAG NUMBER · TAG NO                         bare      → join key (the milestone tag searched for)
                                                      qualified → attribute TAG NUMBER (tag printed on the document)
    MAKE · MANUFACTURER · MFR · OEM                   → MAKE
    MODEL · MODEL NO · MODEL NUMBER                   → MODEL
    SERIAL · SERIAL NUMBER · SERIAL NO                → SERIAL NUMBER
    PART · PART NUMBER · PART NO                      → PART NUMBER

The whole remaining phrase must equal a core phrase: `PART NUMBER REMARKS`, `VALVE SCHEDULE SIZE & RATING`
or `VENDOR NAME` never bind. Only these five attributes are discovered (the MTL comparison attributes);
every other header is reported as found and left alone.

Provenance is discovered the same way, by whole-word keywords, and may bind several columns:
    `IDB` / `DOKNR`        → document_idb        (DATASHEET REFERENCE-DOC IDB · DOKNR INITIAL/NORMAL/LCS)
    `REF` / `REFERENCE`    → document_reference  (DATASHEET REFERENCE-ORIGINAL · SPIR REF-INITIAL/NORMAL/LCS)
    `PAGE` / `PAGE NO`     → page
"""

from dataclasses import dataclass
from enum import StrEnum

from backend.domain.headers import normalize_header
from backend.domain.sources import SOURCE_TYPES, Attribute


class FieldKind(StrEnum):
    JOIN_KEY = "JOIN_KEY"
    ATTRIBUTE = "ATTRIBUTE"
    PROVENANCE = "PROVENANCE"


@dataclass(frozen=True)
class HeaderMeaning:
    kind: FieldKind
    key: str                                  # TAG_KEY · TAG_AS_PER_DOC · MAKE … · DOCUMENT_REFERENCE · PAGE_NO
    attribute: Attribute | None = None
    role: str | None = None                   # provenance role


JOIN_KEY = "TAG_KEY"
PROVENANCE_ROLES = ("document_reference", "document_idb", "page")

TAG_CORE = frozenset({"TAG", "TAG NUMBER", "TAG NO"})
ATTRIBUTE_CORE: dict[Attribute, frozenset[str]] = {
    Attribute.MAKE: frozenset({"MAKE", "MANUFACTURER", "MFR", "OEM"}),
    Attribute.MODEL: frozenset({"MODEL", "MODEL NO", "MODEL NUMBER"}),
    Attribute.SERIAL_NUMBER: frozenset({"SERIAL", "SERIAL NUMBER", "SERIAL NO"}),
    Attribute.PART_NUMBER: frozenset({"PART", "PART NUMBER", "PART NO"}),
}
ATTRIBUTE_KEYS: dict[Attribute, str] = {
    Attribute.TAG_NUMBER: "TAG_AS_PER_DOC", Attribute.MAKE: "MAKE", Attribute.MODEL: "MODEL",
    Attribute.SERIAL_NUMBER: "SERIAL_NUMBER", Attribute.PART_NUMBER: "PART_NUMBER",
}
DOCUMENT_SUFFIXES = ("AS PER DOCUMENT", "AS PER DOC")
# Source-type phrases (codes, summary codes, keywords), longest first so `O & M MANUAL` wins over `O & M`.
SOURCE_PHRASES = tuple(sorted({normalize_header(p) for t in SOURCE_TYPES.values()
                               for p in (t.code, t.summary_code, *t.keywords)}, key=len, reverse=True))
PAGE_CORE = frozenset({"PAGE", "PAGE NO"})


def _strip_qualifiers(text: str) -> tuple[str, bool]:
    qualified = False
    for suffix in DOCUMENT_SUFFIXES:
        if text.endswith(" " + suffix):
            text, qualified = text[: -len(suffix) - 1], True
            break
    for phrase in SOURCE_PHRASES:
        if text.startswith(phrase + " "):
            return text[len(phrase) + 1:], True
        if text.endswith(" " + phrase):
            return text[: -len(phrase) - 1], True
    return text, qualified


def contains_phrase(text: str, phrase: str) -> bool:
    """Whole-word phrase containment on normalized text (`MXS` is in `MXS DATA`, not in `MXSTAG`)."""
    return f" {phrase} " in f" {text} "


def classify_header(value: object) -> HeaderMeaning | None:
    """The concept a header carries, or None when it is not one this system extracts."""
    text = normalize_header(value)
    if not text:
        return None
    core, qualified = _strip_qualifiers(text)
    if core in TAG_CORE:
        if qualified:
            return HeaderMeaning(FieldKind.ATTRIBUTE, ATTRIBUTE_KEYS[Attribute.TAG_NUMBER], Attribute.TAG_NUMBER)
        return HeaderMeaning(FieldKind.JOIN_KEY, JOIN_KEY)
    for attribute, phrases in ATTRIBUTE_CORE.items():
        if core in phrases:
            return HeaderMeaning(FieldKind.ATTRIBUTE, ATTRIBUTE_KEYS[attribute], attribute)
    words = set(text.split())
    if words & {"IDB", "DOKNR"}:
        return HeaderMeaning(FieldKind.PROVENANCE, "DOCUMENT_IDB", role="document_idb")
    if words & {"REF", "REFERENCE"}:
        return HeaderMeaning(FieldKind.PROVENANCE, "DOCUMENT_REFERENCE", role="document_reference")
    if core in PAGE_CORE:
        return HeaderMeaning(FieldKind.PROVENANCE, "PAGE_NO", role="page")
    return None


ATTRIBUTE_LABELS: dict[Attribute, str] = {
    Attribute.TAG_NUMBER: "TAG NUMBER (as per document)", Attribute.MAKE: "MAKE", Attribute.MODEL: "MODEL",
    Attribute.SERIAL_NUMBER: "SERIAL NUMBER", Attribute.PART_NUMBER: "PART NUMBER",
}
ACCEPTED_TAG_KEY = "TAG · TAG NUMBER · TAG NO"

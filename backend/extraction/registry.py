"""Adapter registry. Adding a source type = registering an adapter here; nothing else changes.

An adapter only identifies its document type; field discovery is shared (`backend.domain.fields`).
Every source document arrives as the same worker-export workbook shape, so every registered source type is
extracted by the one shared implementation:

- Data Sheet (MDS), SPIR, Cross Section (MXS), Test Certificate (MTC), O&M (MOM) — verified on real files
  (exact sheet/header evidence plus keywords);
- Asset Photo, GA — identified by the keywords of `SOURCE_TYPES` in a sheet title or the header row, or by
  the user's explicit choice of type. Their real format is not yet verified (`verified=False`).

Evidence is ranked (sheet title > verified header > keyword in a header): the type with the strongest
evidence wins, so a `TEST CERTIFICATE` sheet carrying an `ASSET SERIAL NUMBER` column is a Test Certificate.
"""

from backend.domain.sources import SOURCE_TYPES
from backend.extraction.datasheet import DATASHEET
from backend.extraction.spir import SPIR
from backend.extraction.tabular import (
    Extraction,
    Identification,
    Issue,
    Severity,
    TabularAdapter,
    TabularAdapterConfig,
    Workbook,
)
from backend.extraction.verified import MOM, MTC, MXS

VERIFIED = (DATASHEET, SPIR, MXS, MTC, MOM)
KEYWORD_ONLY = tuple(
    TabularAdapter(TabularAdapterConfig(source_type=t.code, document_label=t.label, keywords=t.keywords, verified=False))
    for t in SOURCE_TYPES.values() if t.code not in {a.source_type for a in VERIFIED})

# Registration order is the display order of SOURCE_TYPES.
ADAPTERS: dict[str, TabularAdapter] = {
    a.source_type: a for a in sorted((*VERIFIED, *KEYWORD_ONLY), key=lambda a: list(SOURCE_TYPES).index(a.source_type))}


def identify(book: Workbook, requested_type: str | None) -> Identification:
    """Decide the source type and sheet. Never guesses.

    - requested type → that adapter must find its own evidence in the file (or, for a type not yet
      verified on a real file, the explicit choice is the evidence)
    - no requested type → exactly one registered adapter must recognise the file
    """
    strength = {a.source_type: a.evidence(book)[0] for a in ADAPTERS.values()}

    if requested_type is not None:
        adapter = ADAPTERS[requested_type]
        ident = adapter.identify(book)
        # Refused when the file names another document type more strongly than the one selected.
        others = [t for t, s in strength.items() if t != requested_type and s > strength[requested_type]]
        if others and ident.source_type is not None:
            return _wrong_type(ident, book, requested_type, others)
        if ident.source_type is not None or adapter.config.verified:
            return ident
        # Explicit choice of a not-yet-verified type — refused when the file names another document type.
        others = [t for t, s in strength.items() if t != requested_type and s]
        if others:
            return _wrong_type(ident, book, requested_type, others)
        return adapter.identify(book, requested=True)

    best = max(strength.values(), default=0)
    idents = [(a, a.identify(book)) for a in ADAPTERS.values() if best and strength[a.source_type] == best]
    matches = [(a, i) for a, i in idents if i.source_type is not None]
    if len(matches) == 1:
        return matches[0][1]
    # Recognised by evidence but not safely usable (e.g. two candidate sheets): surface that specific reason.
    recognised = [i for _, i in idents if i.source_type is None
                  and not any(x.code == "NOT_THIS_SOURCE_TYPE" for x in i.issues)]
    if not matches and len(recognised) == 1:
        return recognised[0]
    ident = Identification(skipped_sheets=[{"sheet": n, "reason": "not recognised"} for n in book.sheets])
    if not matches:
        ident.issues.append(Issue(
            Severity.ERROR, "SOURCE_TYPE_UNKNOWN",
            f"'{book.file_name}' was not recognised as any supported source type "
            f"({', '.join(ADAPTERS)}): no sheet title or TAG NUMBER header row names a document type. "
            f"Select the source type explicitly. Sheets found: {', '.join(repr(n) for n in book.sheets)}."))
    else:
        ident.issues.append(Issue(
            Severity.ERROR, "SOURCE_TYPE_AMBIGUOUS",
            f"'{book.file_name}' matches several source types ({', '.join(a.source_type for a, _ in matches)}); "
            f"select the source type explicitly."))
    return ident


def _wrong_type(ident: Identification, book: Workbook, requested_type: str, others: list[str]) -> Identification:
    ident.source_type = ident.sheet_name = None
    ident.issues = [Issue(
        Severity.ERROR, "NOT_THIS_SOURCE_TYPE",
        f"'{book.file_name}' was selected as {requested_type} but its sheet titles / headers name "
        f"{', '.join(others)}. Check the file or select that source type.")]
    return ident


def extract(book: Workbook, ident: Identification) -> Extraction:
    return ADAPTERS[ident.source_type].extract(book, ident.sheet_name)

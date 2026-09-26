"""Shared keyword header discovery (backend/domain/fields.py) — one rule set for every source type.

The header lists are taken from the real Data Sheet and SPIR files.
"""

import pytest

from backend.domain.fields import FieldKind, classify_header
from backend.domain.sources import Attribute

DS_REAL = ["S.NO", "TAG NUMBER", "EQUIPMENT DESCRIPTION", "DATASHEET REFERENCE-DOC IDB", "DATASHEET REFERENCE-ORIGINAL",
           " TAG NUMBER AS PER DOC", "PAGE NO", "SIZE & RATING", "MAKE", "MODEL", "SERIAL NUMBER", "PART NUMBER", "REMARKS"]
SPIR_REAL = ["S NO", "TAG NUMBER", "EQUIPMENT DESCRIPTION", "SIZE & RATING", "VALVE SCHEDULE SIZE & RATING",
             "SPIR TAG NUMBER", "DOKNR INITIAL", "SPIR REF-INITIAL", "DOKNR NORMAL", "SPIR REF-NORMAL", "DOKNR LCS",
             "SPIR REF-LCS", "PAGE NO", "MAKE", "MODEL", "SERIAL NUMBER", "PART NUMBER", "ACQUSITION VALUE",
             "ACQUSITION CURRENCY", "WEIGHT", "COUNTRY", "MONTH OF MANUFACTURE", "YEAR OF MANUFACTURE",
             "ADDITIONAL INFORMATION", "VENDOR NAME", "VENDOR EMAIL 1", "VENDOR EMAIL 2", "VENDOR CONTACT NO",
             "VENDOR COUNTRY", "REMARKS", "NAME ", "DATE"]


def meaning(h):
    m = classify_header(h)
    return None if m is None else (m.kind, m.attribute or m.role or m.key)


def extracted(headers):
    return {h: meaning(h) for h in headers if meaning(h) is not None}


def test_real_datasheet_headers():
    assert extracted(DS_REAL) == {
        "TAG NUMBER": (FieldKind.JOIN_KEY, "TAG_KEY"),
        " TAG NUMBER AS PER DOC": (FieldKind.ATTRIBUTE, Attribute.TAG_NUMBER),
        "MAKE": (FieldKind.ATTRIBUTE, Attribute.MAKE),
        "MODEL": (FieldKind.ATTRIBUTE, Attribute.MODEL),
        "SERIAL NUMBER": (FieldKind.ATTRIBUTE, Attribute.SERIAL_NUMBER),
        "PART NUMBER": (FieldKind.ATTRIBUTE, Attribute.PART_NUMBER),
        "DATASHEET REFERENCE-DOC IDB": (FieldKind.PROVENANCE, "document_idb"),
        "DATASHEET REFERENCE-ORIGINAL": (FieldKind.PROVENANCE, "document_reference"),
        "PAGE NO": (FieldKind.PROVENANCE, "page"),
    }


def test_real_spir_headers():
    assert extracted(SPIR_REAL) == {
        "TAG NUMBER": (FieldKind.JOIN_KEY, "TAG_KEY"),
        "SPIR TAG NUMBER": (FieldKind.ATTRIBUTE, Attribute.TAG_NUMBER),
        "MAKE": (FieldKind.ATTRIBUTE, Attribute.MAKE),
        "MODEL": (FieldKind.ATTRIBUTE, Attribute.MODEL),
        "SERIAL NUMBER": (FieldKind.ATTRIBUTE, Attribute.SERIAL_NUMBER),
        "PART NUMBER": (FieldKind.ATTRIBUTE, Attribute.PART_NUMBER),
        **{f"DOKNR {s}": (FieldKind.PROVENANCE, "document_idb") for s in ("INITIAL", "NORMAL", "LCS")},
        **{f"SPIR REF-{s}": (FieldKind.PROVENANCE, "document_reference") for s in ("INITIAL", "NORMAL", "LCS")},
        "PAGE NO": (FieldKind.PROVENANCE, "page"),
    }


@pytest.mark.parametrize("header, expected", [
    # join key: bare tag phrase, any case/punctuation
    ("Tag No.", (FieldKind.JOIN_KEY, "TAG_KEY")),
    ("TAG", (FieldKind.JOIN_KEY, "TAG_KEY")),
    # tag printed on the document: tag phrase + document qualifier
    ("TAG NUMBER AS PER DOCUMENT", (FieldKind.ATTRIBUTE, Attribute.TAG_NUMBER)),
    ("MTC TAG NO", (FieldKind.ATTRIBUTE, Attribute.TAG_NUMBER)),
    ("TAG NUMBER (MXS)", (FieldKind.ATTRIBUTE, Attribute.TAG_NUMBER)),
    # controlled aliases, with or without a document qualifier
    ("MANUFACTURER", (FieldKind.ATTRIBUTE, Attribute.MAKE)),
    ("OEM", (FieldKind.ATTRIBUTE, Attribute.MAKE)),
    ("MAKE AS PER DOC", (FieldKind.ATTRIBUTE, Attribute.MAKE)),
    ("Model No", (FieldKind.ATTRIBUTE, Attribute.MODEL)),
    ("SERIAL NO.", (FieldKind.ATTRIBUTE, Attribute.SERIAL_NUMBER)),
    ("SPIR PART NO", (FieldKind.ATTRIBUTE, Attribute.PART_NUMBER)),
])
def test_header_variants(header, expected):
    assert meaning(header) == expected


@pytest.mark.parametrize("header", [
    "PART NUMBER REMARKS", "MAKE REMARKS", "MODEL DESCRIPTION", "TAG DISCRIPTION", "VENDOR NAME",
    "SIZE & RATING", "PRESSURE CLASS", "S NO", "SPIR", "REMARKS", "", None,
])
def test_non_mtl_headers_do_not_bind(header):
    """Whole-phrase matching: a header merely containing a keyword is not that field."""
    assert classify_header(header) is None

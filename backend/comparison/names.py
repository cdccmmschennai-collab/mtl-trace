"""Manufacturer-name variants (rules `manufacturer_name_attributes`, currently MAKE only).

Two differing manufacturer names are a *possible* naming variant — the same manufacturer written in a
short, full, division or legal form — when, comparing whole words only (letters and digits, case-insensitive):

    1. they are identical once spaces and punctuation are removed    SULZER … PVT. LTD.  /  SULZER … PVT. LTD
    2. every word of one name is a word of the other                 TELEDYNE  /  SIMTRONICS TELEDYNE
    3. they share all words but the last, and one last word is        Endress + Hause  /  ENDRESS+HAUSER
       the leading part of the other (a truncated name)

A variant is never declared a MATCH: the engine routes it to REVIEW REQUIRED for a human to decide.
Anything else is a genuine conflict (KAYSE TURKEY / KAYSE AS, TECHTROL / AQUATROL VALVE).
No substring, similarity score or manufacturer dictionary is used.
"""

import re

_WORD = re.compile(r"[0-9a-z]+")


def _words(name: str) -> list[str]:
    return _WORD.findall(name.casefold())


def is_name_variant(a: str, b: str) -> bool:
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return False
    if "".join(wa) == "".join(wb):
        return True
    if set(wa) <= set(wb) or set(wb) <= set(wa):
        return True
    return (len(wa) == len(wb) >= 2 and wa[:-1] == wb[:-1]
            and (wa[-1].startswith(wb[-1]) or wb[-1].startswith(wa[-1])))

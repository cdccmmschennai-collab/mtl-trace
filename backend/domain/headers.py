"""Header normalization shared by the scope reader and every source adapter."""

import re


def normalize_header(value: object) -> str:
    """Upper-case, treat punctuation other than '&' as a separator, collapse whitespace.

    `S.NO`, `s. no` and ` S NO ` all normalize to `S NO`; `SIZE&RATING` to `SIZE & RATING`;
    `" TAG NUMBER AS PER DOC"` to `TAG NUMBER AS PER DOC`. Equality on the result is exact — no
    substring matching, so `TAG NUMBER AS PER DOC` never matches `TAG NUMBER`.
    """
    if value is None:
        return ""
    text = str(value).upper().replace("&", " & ")
    text = re.sub(r"[^A-Z0-9&]+", " ", text)
    return " ".join(text.split())

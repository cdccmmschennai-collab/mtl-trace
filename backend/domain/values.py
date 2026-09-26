from datetime import date, datetime, time


def cell_text(value: object) -> str | None:
    """Render a cell as trimmed text. Blank and whitespace-only cells are None.

    Deterministic storage normalization only — no case folding, no punctuation or synonym handling.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, bool):
        return str(value).upper()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return str(value)

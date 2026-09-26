"""Consolidation: (locked scope, source records) → canonical dataset. Pure — no I/O, no openpyxl,
no database, and never the extraction package: it reads extracted *records*, not source files."""

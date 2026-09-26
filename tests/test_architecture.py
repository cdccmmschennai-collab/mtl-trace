"""Layer boundaries from CLAUDE.md, enforced by inspecting imports."""

import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"


def imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def modules():
    for path in BACKEND.rglob("*.py"):
        yield path.relative_to(BACKEND).as_posix(), imports_of(path)


def uses(imports: set[str], package: str) -> bool:
    return any(i == package or i.startswith(package + ".") for i in imports)


def test_only_api_layer_imports_fastapi():
    offenders = [m for m, imps in modules()
                 if uses(imps, "fastapi") and not (m.startswith("api/") or m == "main.py")]
    assert offenders == []


def test_only_extraction_and_output_import_openpyxl():
    offenders = [m for m, imps in modules()
                 if uses(imps, "openpyxl") and not m.startswith(("extraction/", "output/"))]
    assert offenders == []


def test_domain_is_pure():
    forbidden = ("sqlalchemy", "openpyxl", "fastapi", "backend.storage", "backend.services", "backend.api")
    offenders = [(m, i) for m, imps in modules() if m.startswith("domain/")
                 for i in imps if any(i == f or i.startswith(f + ".") for f in forbidden)]
    assert offenders == []


def test_consolidation_reads_records_not_files():
    forbidden = ("backend.extraction", "openpyxl", "sqlalchemy", "fastapi", "backend.storage", "backend.services",
                 "backend.api", "backend.output")
    offenders = [(m, i) for m, imps in modules() if m.startswith("consolidation/")
                 for i in imps if any(i == f or i.startswith(f + ".") for f in forbidden)]
    assert offenders == []


def test_comparison_reads_canonical_data_not_files():
    forbidden = ("backend.extraction", "openpyxl", "sqlalchemy", "fastapi", "backend.storage", "backend.services",
                 "backend.api", "backend.output", "backend.consolidation")
    offenders = [(m, i) for m, imps in modules() if m.startswith("comparison/")
                 for i in imps if any(i == f or i.startswith(f + ".") for f in forbidden)]
    assert offenders == []


def test_comparison_engine_hard_codes_no_source_type():
    from backend.domain.sources import SOURCE_TYPES
    text = (BACKEND / "comparison" / "engine.py").read_text(encoding="utf-8")
    assert not [c for c in SOURCE_TYPES if f'"{c}"' in text]


def test_output_does_not_reach_back_into_extraction_or_storage():
    forbidden = ("backend.extraction", "backend.storage", "backend.services", "backend.api", "sqlalchemy", "fastapi")
    offenders = [(m, i) for m, imps in modules() if m.startswith("output/")
                 for i in imps if any(i == f or i.startswith(f + ".") for f in forbidden)]
    assert offenders == []


def test_production_registry_has_no_fixture_adapter():
    from backend.domain.sources import SOURCE_TYPES
    from backend.extraction import registry
    from backend.extraction.datasheet import DATASHEET
    from backend.extraction.spir import SPIR
    assert list(registry.ADAPTERS) == list(SOURCE_TYPES)
    assert registry.ADAPTERS["MDS"] is DATASHEET and registry.ADAPTERS["SPIR"] is SPIR
    assert {c for c, a in registry.ADAPTERS.items() if a.config.verified} == {"MDS", "SPIR"}
    assert not any("fixture" in imp for m, imps in modules() for imp in imps)


def test_adapters_identify_only_and_share_field_discovery():
    """No per-source field lists: every adapter is identification config over the one shared discovery."""
    from backend.extraction import registry
    from backend.extraction.tabular import TabularAdapterConfig
    assert set(TabularAdapterConfig.__dataclass_fields__) == {"source_type", "document_label", "sheet_names",
                                                               "evidence_headers", "keywords", "verified"}
    assert all(type(a.config) is TabularAdapterConfig for a in registry.ADAPTERS.values())


def test_api_does_not_touch_storage_directly():
    offenders = [m for m, imps in modules() if m.startswith("api/") and uses(imps, "backend.storage")]
    assert offenders == []

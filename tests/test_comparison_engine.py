"""Unit tests: the pure comparison engine under rules/v1.yaml."""

import pytest

from backend.comparison.engine import (
    ComparisonInput,
    Reason,
    SourceValue,
    Status,
    compare,
)
from backend.comparison.rules import Rules, RulesError, load_rules
from backend.config import REPO_ROOT

RULES = load_rules(REPO_ROOT / "rules" / "v1.yaml")
MILESTONE = "717-T-001"
LABELS = {"MDS": "DATA SHEET (MDS)", "SPIR": "SPIR (MIR)", "MXS": "CROSS SECTION (MXS)"}


def v(source_type: str, value: str | None, state: str | None = None) -> SourceValue:
    if state is None:
        state = "PRESENT" if value is not None and value.strip() else "ABSENT_VALUE"
    return SourceValue(source_type, state, value.strip() if value else None)


def dup(source_type: str, *candidates: str | None) -> SourceValue:
    return SourceValue(source_type, "CONFLICTING_DUPLICATE", None, candidates)


def run(attribute: str, *values: SourceValue, tag: str = MILESTONE):
    return compare(ComparisonInput(1, tag, attribute, tuple(values)), RULES, LABELS)


# ---------------------------------------------------------------- rules file

def test_rules_file_defines_priority_and_exactly_three_states():
    assert RULES.version == "v1"
    assert RULES.source_priority == ("ASSET", "MDS", "SPIR", "GA", "MXS", "MTC", "MOM")
    assert RULES.milestone_anchored == frozenset({"TAG_NUMBER"})


def test_rules_with_an_extra_state_are_refused(tmp_path):
    bad = (REPO_ROOT / "rules" / "v1.yaml").read_text(encoding="utf-8").replace(
        "states: [MATCH, MISMATCH, REVIEW REQUIRED]", "states: [MATCH, MISMATCH, REVIEW REQUIRED, PENDING]")
    (tmp_path / "bad.yaml").write_text(bad, encoding="utf-8")
    with pytest.raises(RulesError):
        load_rules(tmp_path / "bad.yaml")


# ---------------------------------------------------------------- TAG NUMBER (milestone-anchored)

def test_tag_all_sources_agree_with_milestone_is_match():                       # business example 3
    r = run("TAG_NUMBER", v("MDS", MILESTONE), v("SPIR", MILESTONE), v("MXS", MILESTONE))
    assert (r.status, r.final_value, r.reason) == (Status.MATCH, MILESTONE, Reason.SOURCES_AGREE)


def test_tag_single_source_differs_from_milestone_is_review_not_mismatch():     # business example 1
    r = run("TAG_NUMBER", v("MDS", "717-T-001A"), v("SPIR", None))
    assert (r.status, r.final_value, r.reason) == (Status.REVIEW_REQUIRED, MILESTONE, Reason.DIFFERS_FROM_MILESTONE)
    assert r.remarks == "DATA SHEET (MDS) TAG differs from milestone TAG; milestone TAG retained."


def test_tag_sources_disagree_is_mismatch_and_final_is_milestone():             # business example 2
    r = run("TAG_NUMBER", v("MDS", MILESTONE), v("SPIR", "717-T-001A"), v("MXS", MILESTONE))
    assert (r.status, r.final_value, r.reason) == (Status.MISMATCH, MILESTONE, Reason.SOURCES_DISAGREE)
    assert r.remarks == "DATA SHEET (MDS), SPIR (MIR) and CROSS SECTION (MXS) values differ; milestone TAG retained."


def test_tag_sources_agree_with_each_other_but_not_milestone_is_review():
    r = run("TAG_NUMBER", v("MDS", "717-T-001A"), v("SPIR", "717-t-001a "))
    assert (r.status, r.final_value) == (Status.REVIEW_REQUIRED, MILESTONE)


def test_tag_single_source_equal_to_milestone_is_match_case_insensitively():
    r = run("TAG_NUMBER", v("SPIR", "717-t-001"))
    assert (r.status, r.final_value, r.reason, r.final_source) == (Status.MATCH, MILESTONE, Reason.SINGLE_SOURCE, "MILESTONE")


def test_tag_without_any_source_value_is_blank_not_milestone():
    r = run("TAG_NUMBER", v("MDS", None), v("SPIR", "   "))
    assert (r.status, r.final_value, r.reason) == (None, None, Reason.NO_SOURCE_VALUE)


# ---------------------------------------------------------------- other attributes

def test_all_populated_sources_agree_is_match():
    r = run("MAKE", v("MDS", "Emerson"), v("SPIR", " EMERSON "))
    assert (r.status, r.final_value, r.final_source, r.remarks) == (Status.MATCH, "Emerson", "MDS", None)


def test_sources_disagree_is_mismatch_and_the_priority_source_is_named():
    r = run("MODEL", v("MDS", "3051"), v("SPIR", "3051 CD"))                     # word containment is not a MODEL rule
    assert (r.status, r.reason, r.final_value) == (Status.MISMATCH, Reason.SOURCES_DISAGREE, "3051")
    assert r.remarks == "DATA SHEET (MDS) and SPIR (MIR) values differ; DATA SHEET (MDS) selected by source priority."


def test_highest_priority_populated_source_is_final_whatever_the_input_order():
    r = run("MODEL", v("MOM", "M-7"), v("SPIR", "M-3"), v("ASSET", None), v("MDS", "M-2"))
    assert (r.final_value, r.final_source, r.status) == ("M-2", "MDS", Status.MISMATCH)
    r = run("MODEL", v("MOM", "M-7"), v("MTC", None), v("GA", "M-4"))
    assert (r.final_value, r.final_source) == ("M-4", "GA")


def test_empty_higher_priority_source_does_not_override_a_populated_lower_one():
    r = run("SERIAL_NUMBER", v("MDS", None), v("SPIR", "665436"))
    assert (r.status, r.final_value, r.final_source, r.reason) == (Status.MATCH, "665436", "SPIR", Reason.SINGLE_SOURCE)


def test_missing_source_attribute_is_not_a_mismatch():
    """SPIR does not provide PART NUMBER at all (no cell), MDS has one value: a single-source MATCH."""
    r = run("PART_NUMBER", v("MDS", "P-1"))
    assert (r.status, r.compared_sources) == (Status.MATCH, ("MDS",))


def test_no_applicable_value_leaves_final_and_status_blank():
    for values in [(), (v("MDS", None),), (v("MDS", None), SourceValue("SPIR", "ABSENT_TAG", None))]:
        r = run("MAKE", *values)
        assert (r.status, r.final_value, r.remarks, r.reason) == (None, None, None, Reason.NO_SOURCE_VALUE)


def test_punctuation_is_not_normalized_away():
    """Only trim + case (TRD §18). A punctuation difference is a real difference outside manufacturer names."""
    r = run("MODEL", v("MDS", "EJA-110A"), v("SPIR", "EJA110A"))
    assert r.status == Status.MISMATCH


def test_raw_values_are_never_changed():
    r = run("MAKE", v("SPIR", "Emerson Automation"))
    assert r.final_value == "Emerson Automation"                              # not case-folded


# ---------------------------------------------------------------- duplicates

def test_conflicting_duplicate_is_review_required_and_no_candidate_is_chosen():
    r = run("MAKE", dup("MDS", "A", "B"), v("SPIR", "A"))
    assert (r.status, r.reason, r.final_value) == (Status.REVIEW_REQUIRED, Reason.DUPLICATE_SOURCE_RECORDS, None)
    assert r.remarks == "Several source rows for this tag; no value chosen automatically (DATA SHEET (MDS): 'A' | 'B')."


def test_duplicate_in_lower_priority_source_keeps_the_higher_final():
    r = run("MAKE", v("MDS", "A"), dup("SPIR", "A", "B"))
    assert (r.status, r.final_value, r.final_source) == (Status.REVIEW_REQUIRED, "A", "MDS")


def test_duplicate_rows_with_no_value_are_not_evidence():
    r = run("MAKE", dup("MDS", None, "  "))
    assert r.status is None


# ---------------------------------------------------------------- dynamic sources

def test_unknown_source_type_is_refused_not_ignored():
    with pytest.raises(RulesError):
        run("MAKE", v("NEWDOC", "A"))


def test_new_source_type_needs_only_a_rules_entry():
    rules = Rules("vX", ("NEWDOC", "MDS"), True, True, frozenset({"TAG_NUMBER"}))
    r = compare(ComparisonInput(1, MILESTONE, "MAKE", (v("MDS", "A"), v("NEWDOC", "B"))), rules)
    assert (r.status, r.final_source) == (Status.MISMATCH, "NEWDOC")


# ---------------------------------------------------------------- MAKE: manufacturer-name variants

NAME_VARIANT_REMARK = "MAKE values may represent the same manufacturer; human review required."


@pytest.mark.parametrize("mds, spir", [
    ("TELEDYNE", "SIMTRONICS TELEDYNE"),
    ("EMERSON", "EMERSON AUTOMATION SOLUTIONS"),
    ("ABB", "ABB CZECH REPUBLIC"),
    ("Endress + Hause", "ENDRESS+HAUSER"),
    ("SMAR", "SMAR TECHNOLOGY COMPANY"),
    ("SULZER PUMPS INDIA PVT. LTD.", "SULZER PUMPS INDIA PVT. LTD"),              # punctuation only
])
def test_make_naming_variant_is_review_required_and_unresolved(mds, spir):
    r = run("MAKE", v("MDS", mds), v("SPIR", spir))
    assert (r.status, r.reason) == (Status.REVIEW_REQUIRED, Reason.NAME_VARIANT)
    assert (r.final_value, r.final_source) == (None, None)                     # the engine did not choose one
    assert r.remarks == NAME_VARIANT_REMARK
    assert r.compared_sources == ("MDS", "SPIR")                                # both source values kept


@pytest.mark.parametrize("mds, spir", [
    ("KAYSE TURKEY", "KAYSE AS"),                                               # shared word is not containment
    ("TECHTROL", "AQUATROL VALVE"),
    ("Honeywell", "STEDPRO ENGG. & MFG LLP"),
])
def test_make_genuine_conflict_stays_mismatch(mds, spir):
    r = run("MAKE", v("MDS", mds), v("SPIR", spir))
    assert (r.status, r.reason, r.final_value, r.final_source) == (Status.MISMATCH, Reason.SOURCES_DISAGREE, mds, "MDS")
    assert r.remarks == "DATA SHEET (MDS) and SPIR (MIR) MAKE values differ; human review required."


def test_make_with_one_genuine_conflict_among_variants_is_mismatch():
    r = run("MAKE", v("MDS", "EMERSON"), v("SPIR", "EMERSON AUTOMATION SOLUTIONS"), v("MXS", "YOKOGAWA"))
    assert r.status == Status.MISMATCH


def test_make_equal_values_remain_match():
    r = run("MAKE", v("MDS", "Emerson"), v("SPIR", "EMERSON"))
    assert (r.status, r.final_value, r.remarks) == (Status.MATCH, "Emerson", None)
    assert run("MAKE", v("SPIR", "ABB CZECH REPUBLIC")).status == Status.MATCH


@pytest.mark.parametrize("attribute", ["MODEL", "SERIAL_NUMBER", "PART_NUMBER"])
def test_naming_variant_rule_applies_to_make_only(attribute):
    r = run(attribute, v("MDS", "ABB"), v("SPIR", "ABB CZECH REPUBLIC"))
    assert (r.status, r.final_value) == (Status.MISMATCH, "ABB")


def test_tag_rule_ignores_the_naming_variant_rule():
    r = run("TAG_NUMBER", v("MDS", MILESTONE), v("SPIR", MILESTONE + " A"))
    assert (r.status, r.final_value) == (Status.MISMATCH, MILESTONE)


def test_rules_file_lists_make_as_the_only_manufacturer_name_attribute():
    assert RULES.manufacturer_names == frozenset({"MAKE"})

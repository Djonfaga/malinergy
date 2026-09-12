"""The comparison must be honest about what it did and did not run."""

import pytest

from mali_benchmark.capability import (
    ABSENT,
    CAPABILITIES,
    NATIVE,
    NOT_APPLICABLE,
    PARTIAL,
    SCRIPTED,
    TOOLS,
    hand_written_work,
    matrix,
    scores,
)
from mali_benchmark.compare import RESULT_PATHS, compare, provenance
from mali_benchmark.effort import access_table, effort_table
from mali_benchmark.findings import FINDINGS, by_confidence, headline
from mali_benchmark.findings import table as findings_table


def test_every_capability_covers_every_tool():
    for capability in CAPABILITIES:
        missing = set(TOOLS) - set(capability.support)
        assert not missing, f"{capability.capability} says nothing about {missing}"


def test_support_levels_are_from_the_fixed_set():
    allowed = {NATIVE, PARTIAL, SCRIPTED, ABSENT, NOT_APPLICABLE}
    for capability in CAPABILITIES:
        assert set(capability.support.values()) <= allowed


def test_hand_written_claims_point_at_evidence():
    """A claim that a tool made us write something must name what was written."""
    for capability in CAPABILITIES:
        if SCRIPTED in capability.support.values():
            assert capability.evidence, f"{capability.capability} has no evidence"


def test_scores_exclude_capabilities_that_do_not_apply():
    """pandapipes is a fluid solver. Marking it down for not calculating
    short-circuit currents would make the score meaningless."""
    frame = scores().set_index("tool")
    assert frame.loc["pandapipes", "applicable_capabilities"] < frame.loc[
        "pandapower", "applicable_capabilities"
    ]
    assert (frame["weighted_score"] <= 1.0).all()
    assert (frame["weighted_score"] >= 0.0).all()


def test_matrix_has_a_row_per_capability():
    assert len(matrix()) == len(CAPABILITIES)


def test_hand_written_table_contrasts_two_tools():
    frame = hand_written_work()
    assert not frame.empty
    for _, row in frame.iterrows():
        assert row["written_by_hand_for"]
        assert row["built_into"]


def test_every_finding_names_a_branch_and_its_sensitivity():
    for finding in FINDINGS:
        assert finding.branch.startswith("sim/")
        assert finding.evidence
        assert finding.sensitive_to, f"{finding.finding} states no sensitivity"
        assert finding.confidence in {"measured", "derived", "modelled"}


def test_findings_are_not_all_presented_as_measured():
    """Most of this study is modelled or derived. A findings table where
    everything is measured would be the clearest possible warning sign."""
    counts = by_confidence().set_index("confidence")["findings"].to_dict()
    assert counts.get("measured", 0) == 0
    assert counts.get("modelled", 0) > 0
    assert counts.get("derived", 0) > 0


def test_headline_findings_are_a_subset():
    assert set(headline()["finding"]) <= set(findings_table()["finding"])


def test_effort_table_totals_add_up():
    frame = effort_table()
    total = frame[frame["branch"] == "total"].iloc[0]
    parts = frame[frame["branch"] != "total"]
    assert total["code_lines"] == parts["code_lines"].sum()
    assert total["files"] == parts["files"].sum()


def test_access_table_records_what_a_reader_can_reproduce():
    frame = access_table().set_index("tool")
    assert frame.loc["pandapower", "reproducible_by_a_reader"]
    assert not frame.loc["PowerFactory", "reproducible_by_a_reader"]
    assert not frame.loc["Simscape Electrical", "reproducible_by_a_reader"]


def test_comparison_declares_which_tools_ran():
    result = compare()
    assert set(result.available) >= {"pandapower", "PowerFactory"}
    for tool, present in result.available.items():
        if not present:
            assert any(tool in note for note in result.notes)


def test_missing_tools_are_never_filled_in():
    """Nothing may appear in the comparison table under a tool that did not run."""
    result = compare()
    if result.table.empty:
        pytest.skip("no tool produced results")
    ran = {tool for tool, present in result.available.items() if present}
    assert set(result.table["tool"].unique()) <= ran


def test_provenance_states_how_each_tool_was_verified():
    frame = provenance()
    assert set(frame["tool"]) >= set(RESULT_PATHS)
    assert frame["how_verified"].str.len().gt(10).all()

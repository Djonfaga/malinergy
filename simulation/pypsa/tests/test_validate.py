"""Validation against data the model did not consume.

The point of these tests is not that the model agrees with the national
statistics. It does not, on hydro and on thermal, and that disagreement is a
published result. The point is that the comparison is honest: that it is made
against figures the model never saw, that a deviation is reported rather than
tuned away, and that the one comparison which would be circular is refused.
"""

import pytest
from mali_pypsa.validate import against_national_statistics, against_sibling_model


@pytest.fixture(scope="module")
def report(result):
    return against_national_statistics(result)


def test_the_solar_check_is_independent_and_it_passes(report):
    """Nothing in the resource chain ever saw this statistic."""
    solar = next(c for c in report.comparisons if c.quantity == "solar")
    assert solar.verdict == "consistent"
    assert abs(solar.deviation_pct) < 15


def test_total_demand_is_not_offered_as_evidence(report):
    """It was calibrated on the national balance, so it proves nothing."""
    quantities = {c.quantity for c in report.comparisons}
    assert "demand" not in quantities


def test_every_comparison_states_its_basis(report):
    for comparison in report.comparisons:
        assert comparison.basis
        assert comparison.verdict in {"consistent", "deviates"}


def test_a_deviation_becomes_a_finding_with_an_explanation(report):
    deviating = [c for c in report.comparisons if c.verdict == "deviates"]
    assert deviating, "the hydro and thermal deviations are known and expected"
    for comparison in deviating:
        assert comparison.explanation
        assert any(comparison.quantity in finding for finding in report.findings)


def test_the_hydro_deviation_is_reported_not_hidden(report):
    hydro = next(c for c in report.comparisons if c.quantity == "hydro")
    assert hydro.deviation_pct > 0
    assert "availability table" in hydro.explanation


def test_the_national_net_import_line_is_explicitly_refused(report):
    """Manantali's foreign shares are Malian exports in national accounts."""
    assert any("net-import" in finding for finding in report.findings)
    assert "import" not in {c.quantity for c in report.comparisons}


def test_a_zero_reference_does_not_divide_by_zero(result):
    from mali_pypsa.validate import Comparison

    empty = Comparison(
        quantity="x", model_gwh=1.0, reference_gwh=0.0, basis="b", verdict="deviates"
    )
    assert empty.deviation_pct != empty.deviation_pct  # nan


def test_the_report_tabulates(report):
    frame = report.frame()
    assert len(frame) == len(report.comparisons)
    for column in ("quantity", "model_gwh", "reference_gwh", "deviation_pct", "basis"):
        assert column in frame.columns


def test_the_sibling_comparison_says_when_it_could_not_run(result):
    """It must never quote a remembered number in place of a run."""
    sibling = against_sibling_model(result, step_hours=12)
    assert sibling["status"] in {"compared", "not run"}
    if sibling["status"] == "not run":
        assert sibling["note"]
    else:
        assert set(sibling["pandapower"]) == set(sibling["pypsa"])
        assert sibling["note"]

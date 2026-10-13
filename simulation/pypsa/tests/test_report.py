"""The report, and the rule that no figure is quoted without its data beside it."""

import pandas as pd
import pytest
from mali_pypsa.report import markdown_report, table, write_tables


def test_every_table_is_written_as_csv(result, tmp_path):
    written = write_tables(result, tmp_path)
    assert written
    for path in written:
        assert path.exists()
        assert not pd.read_csv(path).empty


def test_the_written_carrier_table_matches_the_result(result, tmp_path):
    write_tables(result, tmp_path)
    frame = pd.read_csv(tmp_path / "energy_by_carrier.csv", index_col=0)
    for carrier, value in result.by_carrier_gwh.items():
        assert frame.loc[carrier, "energy_gwh"] == pytest.approx(value)


def test_the_report_quotes_the_headline_numbers(result):
    text = markdown_report(result)
    assert f"{result.summary['demand_gwh']:,.0f} GWh" in text
    assert "Energy by carrier" in text
    assert "Monthly balance" in text
    assert "Merit order" in text


def test_the_report_names_the_resource_provider(result):
    text = markdown_report(result)
    assert result.build.resource.provider in text
    assert "modelled" in text or "measured" in text


def test_the_report_carries_the_modelling_notes_without_repeating_them(result):
    text = markdown_report(result)
    assert "## Modelling notes" in text
    for note in result.notes:
        assert text.count(f"- {note}") == 1


def test_a_failed_result_produces_a_report_that_says_so(result):
    from dataclasses import replace

    failed = replace(result, status="warning", condition="infeasible")
    text = markdown_report(failed)
    assert "did not solve" in text
    assert "infeasible" in text


def test_an_empty_frame_renders_as_a_note_not_as_a_broken_table():
    assert table(pd.DataFrame()) == "_no rows_"


def test_the_renderer_produces_a_markdown_table():
    frame = pd.DataFrame({"a": [1.5, 2.5], "b": ["x", "y"]})
    rendered = table(frame).splitlines()
    assert rendered[0] == "| a | b |"
    assert rendered[1] == "|---|---|"
    assert len(rendered) == 4


def test_missing_values_render_as_a_dash():
    frame = pd.DataFrame({"a": [None]})
    assert "| - |" in table(frame)

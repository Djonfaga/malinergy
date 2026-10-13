"""The command line, which is how anyone else will run this.

Run coarsely: these tests are about whether each subcommand does what it says
and writes what it claims, not about the numbers, which the dispatch tests
cover at a resolution where they mean something.
"""

import json

import pytest
from mali_pypsa.cli import main


def test_solve_writes_its_tables_and_its_report(tmp_path):
    code = main(
        ["solve", "--step-hours", "12", "--no-atlite", "--output", str(tmp_path)]
    )
    assert code == 0
    assert (tmp_path / "report.md").exists()
    assert (tmp_path / "summary.csv").exists()
    assert "Mali PyPSA" in (tmp_path / "report.md").read_text(encoding="utf-8")


def test_compare_tabulates_both_import_bases(tmp_path):
    code = main(
        ["compare", "--step-hours", "24", "--no-atlite", "--output", str(tmp_path)]
    )
    assert code == 0
    path = tmp_path / "import_basis_comparison.csv"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "contracted" in text
    assert "capacity" in text


def test_validate_writes_the_comparison_and_the_findings(tmp_path):
    code = main(
        ["validate", "--step-hours", "12", "--no-atlite", "--output", str(tmp_path)]
    )
    assert code == 0
    payload = json.loads((tmp_path / "validation.json").read_text(encoding="utf-8"))
    assert payload["national"]
    assert payload["findings"]
    assert payload["sibling"]["status"] in {"compared", "not run"}


def test_the_cutout_command_reports_a_missing_copernicus_account(capsys):
    """It must fail loudly rather than leave the caller thinking it worked."""
    code = main(["cutout", "--year", "1999"])
    out = capsys.readouterr().out
    assert code == 1
    assert "failed" in out
    assert "clear-sky" in out


def test_a_subcommand_is_required():
    with pytest.raises(SystemExit):
        main([])

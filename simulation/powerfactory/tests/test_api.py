"""The environment report must be honest about what is installed."""

from mali_powerfactory.api import environment_report, powerfactory_available, run_script


def test_absence_of_powerfactory_is_reported():
    report = environment_report()
    assert "powerfactory_module" in report
    if not powerfactory_available():
        assert report["note"]
        assert "licensed software" in report["note"]


def test_running_a_script_without_powerfactory_does_not_pretend():
    if powerfactory_available():
        return
    outcome = run_script("run_loadflow.py")
    assert outcome["status"] == "not run"
    assert "not importable" in outcome["note"]


def test_unknown_script_is_rejected():
    import pytest

    with pytest.raises(FileNotFoundError):
        run_script("does_not_exist.py")

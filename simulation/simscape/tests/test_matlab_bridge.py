"""The MATLAB bridge must be explicit about what was and was not run."""

from mali_simscape.matlab import compare_results, matlab_available, run_matlab_studies
from mali_simscape.studies import step_response_study


def test_absence_of_matlab_is_reported_not_hidden():
    if matlab_available():
        return
    outcome = run_matlab_studies()
    assert outcome["status"] == "not run"
    assert "not been executed here" in outcome["note"]


def test_comparison_refuses_to_imply_agreement_without_results(tmp_path):
    frame = step_response_study()
    outcome = compare_results(frame, matlab_dir=tmp_path)
    assert outcome["status"] == "not compared"
    assert "agreement" not in outcome
    assert "should be read as agreement" in outcome["note"]

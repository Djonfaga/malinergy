"""End to end checks on the studies themselves."""

import pytest

from mali_energy.config import BUILD_DIR
from mali_energy.exchange import load_exchange

from mali_pandapower.studies.contingency import run_n1
from mali_pandapower.studies.loadflow import run_all_cases, run_case
from mali_pandapower.studies.shortcircuit import run_short_circuit


@pytest.fixture(scope="module")
def exchange():
    path = BUILD_DIR / "mali_case.json"
    if not path.exists():
        pytest.skip("run 'mali-energy build' in simulation/core first")
    return load_exchange(path)


@pytest.fixture(scope="module")
def results(exchange):
    return run_all_cases(exchange)


def test_every_case_solves(results):
    for name, result in results.items():
        assert result.converged, f"{name} did not converge"


def test_losses_are_physically_plausible(results):
    for name, result in results.items():
        pct = result.summary["losses_pct"]
        assert 1.0 < pct < 12.0, f"{name}: {pct} % losses"


def test_voltages_stay_within_a_credible_range(results):
    for name, result in results.items():
        assert 0.90 < result.summary["vm_min_pu"] < 1.00, name
        assert 1.00 <= result.summary["vm_max_pu"] < 1.08, name


def test_wet_season_hydro_causes_higher_losses_than_dry(results):
    # The western hydro has to cross the country on a single circuit, so the
    # wet season is the expensive one to transport even though demand is lower.
    assert results["wet_peak"].summary["losses_pct"] > results["dry_peak"].summary["losses_pct"]


def test_dry_peak_requires_load_shedding(results):
    assert results["dry_peak"].shed_mw > 50.0
    assert results["wet_peak"].shed_mw == 0.0


def test_capacitors_are_switched_out_at_light_load(results):
    assert results["night_min"].summary["compensation_mvar"] < results["dry_peak"].summary[
        "compensation_mvar"
    ]


def test_slack_matches_its_schedule_after_rebalancing(results):
    for name, result in results.items():
        assert abs(result.summary["slack_mismatch_mw"]) < 2.0, name


def test_reactive_shortfall_is_reported_not_hidden(results):
    wet = results["wet_peak"]
    if wet.summary["q_limits_relaxed"]:
        assert wet.summary["reactive_shortfall_mvar"] > 0
        assert any("reactive limits" in n for n in wet.notes)


def test_n1_screening_classifies_every_branch(exchange):
    frame = run_n1(exchange, "dry_peak")
    assert len(frame) > 20
    assert set(frame["status"]) <= {"secure", "violated", "non-convergent"}
    assert frame["status"].eq("secure").sum() > 0


def test_short_circuit_levels_are_in_range(exchange):
    frame = run_short_circuit(exchange, "dry_peak")
    transmission = frame[frame["vn_kv"] == 225.0]
    assert transmission["ikss_3ph_max_ka"].between(1.0, 15.0).all()
    # Minimum currents must be below maximum ones by construction.
    assert (frame["ikss_3ph_min_ka"] <= frame["ikss_3ph_max_ka"]).all()
    assert (frame["ikss_1ph_min_ka"] <= frame["ikss_1ph_max_ka"]).all()


def test_earth_fault_exceeds_three_phase_near_earthed_neutrals(exchange):
    """Not a defect: close to a solidly earthed star point the zero-sequence
    impedance is lower than the positive-sequence one, so the single-phase
    current is the higher of the two. Kodialani, where the 225/150 kV bank is
    earthed on both sides, is the clearest case in this network."""
    frame = run_short_circuit(exchange, "dry_peak").set_index("bus")
    kodialani = frame.loc["BUS_KODIALANI_225"]
    assert kodialani["ikss_1ph_max_ka"] > kodialani["ikss_3ph_max_ka"]
    # Remote from any earthing point the usual ordering holds.
    koutiala = frame.loc["BUS_FERKE_225"]
    assert koutiala["ikss_1ph_max_ka"] < koutiala["ikss_3ph_max_ka"]


def test_delta_fed_33kv_has_no_earth_fault_path(exchange):
    """The 33 kV busbars sit on the delta winding of YNd transformers, so the
    model has no zero-sequence source there and reports an earth-fault current
    of practically zero. That is what the catalogue describes; the real
    network earths its 33 kV neutral through an earthing transformer, which is
    on the verification checklist."""
    frame = run_short_circuit(exchange, "dry_peak")
    distribution = frame[frame["vn_kv"] == 33.0]
    assert (distribution["ikss_1ph_max_ka"] < 0.05).all()
    assert (distribution["ikss_3ph_max_ka"] > 1.0).all()

"""Checks on the hydrogen scenario."""

import pytest

from mali_pandapipes.hydrogen import HydrogenScenario, evaluate, sizing_sweep


def test_hydrogen_output_follows_the_electrolyser():
    scenario = HydrogenScenario()
    # 53 kWh per kilogram against the energy the stack can absorb.
    expected = scenario.electrolyser_mw * 1000.0 / 53.0
    assert scenario.hydrogen_kg_per_hour == pytest.approx(expected, rel=1e-6)
    assert 5_000 < scenario.hydrogen_tonnes_per_year < 12_000


def test_full_load_hours_are_limited_by_the_solar_plant():
    scenario = HydrogenScenario(pv_capacity_mw=200.0, electrolyser_mw=100.0)
    # 200 MW at a 23 % capacity factor cannot keep 100 MW of stack busy.
    assert scenario.electrolyser_full_load_hours < 8760.0
    assert 3_000 < scenario.electrolyser_full_load_hours < 5_000


def test_pipeline_solves_and_is_feasible_at_300mm():
    outcome = evaluate()
    assert outcome["converged"]
    assert outcome["feasible"]
    assert 0.5 < outcome["velocity_m_s"] < 5.0


def test_smaller_pipe_means_higher_velocity_and_more_pressure_drop():
    frame = sizing_sweep().set_index("diameter_mm")
    assert frame.loc[200.0, "velocity_m_s"] > frame.loc[500.0, "velocity_m_s"]
    assert frame.loc[200.0, "outlet_pressure_bar"] < frame.loc[500.0, "outlet_pressure_bar"]


def test_transmission_beats_hydrogen_for_moving_energy_to_bamako():
    outcome = evaluate()
    assert outcome["energy_penalty_gwh"] > 0
    assert 55.0 < outcome["electrolysis_efficiency_pct"] < 75.0
    assert outcome["transmission_alternative"]["delivered_gwh_per_year"] > outcome[
        "energy_in_hydrogen_gwh_per_year"
    ]


def test_water_demand_of_electrolysis_is_reported():
    scenario = HydrogenScenario()
    assert scenario.water_m3_per_year > 0
    # Roughly 15 litres per kilogram of hydrogen.
    assert scenario.water_m3_per_year == pytest.approx(
        scenario.hydrogen_tonnes_per_year * 1000.0 * 15.0 / 1000.0, rel=1e-6
    )

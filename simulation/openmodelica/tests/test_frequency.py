"""The frequency model is checked against analytical results and physics."""

import numpy as np
import pytest

from mali_openmodelica.generate import frequency_case, high_solar_case, load_default_exchange
from mali_openmodelica.reference import FrequencyCase, simulate_frequency


@pytest.fixture(scope="module")
def exchange():
    try:
        return load_default_exchange()
    except FileNotFoundError:
        pytest.skip("run 'mali-energy build' in simulation/core first")


def test_initial_rocof_matches_the_swing_equation():
    """The only closed-form result available: immediately after a trip, before
    any governor has moved, df/dt = dP x f / (2 x H x S)."""
    case = FrequencyCase(
        inertia_h_s=4.0, s_base_mw=500.0, demand_mw=400.0, hydro_mw=100.0,
        thermal_mw=210.0, solar_mw=0.0, import_mw=90.0,
        hydro_capacity_mw=100.0, thermal_capacity_mw=210.0,
        trip_mw=40.0, load_damping=0.0, underfrequency_shedding=False,
    )
    result = simulate_frequency(case, duration_s=20.0)
    analytical = -case.trip_mw * 50.0 / (2 * case.stored_energy_mws)
    # Measured over 500 ms, so governor action makes it slightly less steep.
    assert result.metrics["rocof_hz_s"] == pytest.approx(analytical, rel=0.15)


def test_cases_are_balanced_before_the_trip(exchange):
    for name in exchange["cases"]:
        case = frequency_case(exchange, name)
        imbalance = (
            case.hydro_mw + case.thermal_mw + case.solar_mw + case.import_mw - case.demand_mw
        )
        assert abs(imbalance) < 0.1, f"{name} is unbalanced by {imbalance:.2f} MW"


def test_frequency_holds_before_the_trip(exchange):
    case = frequency_case(exchange, "dry_peak", trip_mw=40.0)
    result = simulate_frequency(case)
    before = result.time_s < case.trip_time_s
    assert np.allclose(result.frequency_hz[before], 50.0, atol=1e-3)


def test_larger_trip_gives_steeper_rocof_and_lower_nadir(exchange):
    small = simulate_frequency(frequency_case(exchange, "dry_peak", trip_mw=40.0)).metrics
    large = simulate_frequency(frequency_case(exchange, "dry_peak", trip_mw=120.0)).metrics
    assert abs(large["rocof_hz_s"]) > abs(small["rocof_hz_s"])
    assert large["nadir_hz"] < small["nadir_hz"]


def test_solar_displacing_machines_worsens_rocof(exchange):
    base = simulate_frequency(frequency_case(exchange, "solar_noon")).metrics
    high = simulate_frequency(high_solar_case(exchange, solar_mw=250.0)).metrics
    assert high["stored_energy_mws"] < base["stored_energy_mws"]
    assert abs(high["rocof_hz_s"]) > abs(base["rocof_hz_s"])


def test_fast_frequency_response_helps(exchange):
    without = simulate_frequency(high_solar_case(exchange, solar_mw=250.0)).metrics
    with_ffr = simulate_frequency(
        high_solar_case(exchange, solar_mw=250.0, solar_response=True)
    ).metrics
    assert with_ffr["nadir_hz"] > without["nadir_hz"]
    assert with_ffr["shed_mw"] <= without["shed_mw"]


def test_load_shedding_latches():
    """A relay that has operated stays operated: the shed fraction can never
    fall as the frequency recovers."""
    case = FrequencyCase(
        inertia_h_s=3.0, demand_mw=400.0, hydro_mw=100.0, thermal_mw=210.0,
        import_mw=90.0, hydro_capacity_mw=140.0, thermal_capacity_mw=250.0, trip_mw=90.0,
    )
    result = simulate_frequency(case)
    assert np.all(np.diff(result.shed_fraction) >= -1e-12)


def test_inertia_is_not_scaled_by_loading(exchange):
    """A synchronised machine contributes its whole stored energy whatever its
    output, so a lightly loaded fleet is not a low-inertia fleet."""
    from mali_openmodelica.generate import stored_energy_mws

    energy, contributions = stored_energy_mws(exchange, "dry_peak")
    generators = {g["id"]: g for g in exchange["network"]["generators"]}
    for gen_id, value in contributions.items():
        record = generators[gen_id]
        assert value == pytest.approx(round(record["inertia_h_s"] * record["sn_mva"], 1), abs=1e-6)
    assert energy > 1000.0

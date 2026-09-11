"""Checks on the studies built from the real connection points."""

import pytest

from mali_simscape.studies import (
    converter_limit_study,
    grid_strength_study,
    load_default_exchange,
    load_short_circuit,
    step_response_study,
    voltage_dip_study,
)


@pytest.fixture(scope="module")
def exchange():
    try:
        return load_default_exchange()
    except FileNotFoundError:
        pytest.skip("run 'mali-energy build' in simulation/core first")


def test_short_circuit_input_is_present_and_derived():
    frame = load_short_circuit()
    assert not frame.empty
    assert set(frame["confidence"]) == {"derived"}
    assert (frame["sk_max_mva"] > 0).all()


def test_every_solar_plant_has_a_connection_point(exchange):
    frame = grid_strength_study(exchange)
    plants = {g["id"] for g in exchange["network"]["generators"] if g["technology"] == "solar"}
    assert set(frame["plant"]) == plants


def test_short_circuit_ratios_are_in_a_credible_range(exchange):
    frame = grid_strength_study(exchange)
    assert frame["scr"].between(1.0, 40.0).all()


def test_the_weakest_point_is_kita(exchange):
    """50 MW behind the weakest 33 kV busbar in the catalogue."""
    frame = grid_strength_study(exchange).sort_values("scr")
    assert frame.iloc[0]["bus"] == "BUS_KITA_33"


def test_todays_plants_are_stable_as_designed(exchange):
    frame = step_response_study(exchange)
    assert frame["stable"].all()


def test_converter_limits_leave_headroom_at_every_busbar(exchange):
    frame = converter_limit_study(exchange)
    assert (frame["headroom_to_scr_3_mw"] > 0).all()
    assert (frame["mw_at_scr_3"] > frame["connected_mw"]).all()


def test_plants_ride_through_a_deep_dip_on_their_current_limit(exchange):
    frame = voltage_dip_study(exchange)
    assert frame["stable"].all()
    assert frame["on_current_limit"].all()

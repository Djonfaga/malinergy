"""The mini-grid dispatch is checked for the behaviour it exists to produce."""

import numpy as np

from mali_openmodelica.reference import MinigridDesign, simulate_minigrid


def _day(hours: int = 24 * 30):
    """A month of a simple sinusoidal day: sun from 06:00 to 18:00."""
    hour = np.arange(hours) % 24
    irradiance = np.clip(np.sin((hour - 6) / 12 * np.pi), 0, None)
    load = 0.4 + 0.6 * np.clip(np.sin((hour - 4) / 20 * np.pi), 0, None)
    load[(hour >= 18) & (hour <= 21)] = 1.0
    return irradiance, load


def test_battery_stays_within_its_limits():
    irradiance, load = _day()
    design = MinigridDesign()
    result = simulate_minigrid(design, irradiance, load)
    assert result["soc_min"] >= design.soc_min - 1e-6
    assert result["soc_max"] <= design.soc_max + 1e-6


def test_adding_storage_cuts_fuel():
    irradiance, load = _day()
    no_battery = simulate_minigrid(
        MinigridDesign(name="no battery", battery_kw=0.0, battery_kwh=0.0,
                       soc_start_diesel=1.0, soc_stop_diesel=1.0),
        irradiance, load,
    )
    with_battery = simulate_minigrid(MinigridDesign(name="battery"), irradiance, load)
    assert with_battery["fuel_litres"] < no_battery["fuel_litres"]


def test_diesel_starts_when_the_battery_cannot_deliver_the_power():
    """The failure this rule exists to prevent: a full battery whose converter
    is rated below the evening peak, with the set standing by."""
    hours = 24 * 7
    irradiance = np.zeros(hours)
    load = np.ones(hours)
    design = MinigridDesign(
        pv_kw=0.0, battery_kw=40.0, battery_kwh=2000.0, diesel_kw=150.0,
        peak_demand_kw=120.0, soc_start_diesel=0.25, soc_stop_diesel=0.6,
    )
    result = simulate_minigrid(design, irradiance, load)
    assert result["diesel_hours"] > 0
    assert result["unserved_pct"] < 1.0


def test_no_solar_means_no_curtailment_reported():
    """Spill divided by zero photovoltaic output is not a percentage."""
    irradiance, load = _day()
    result = simulate_minigrid(
        MinigridDesign(name="diesel only", pv_kw=0.0, battery_kw=0.0, battery_kwh=0.0,
                       soc_start_diesel=1.0, soc_stop_diesel=1.0),
        irradiance, load,
    )
    assert result["pv_curtailed_pct"] == 0.0


def test_solar_without_storage_is_curtailed():
    irradiance, load = _day()
    result = simulate_minigrid(
        MinigridDesign(name="no storage", pv_kw=250.0, battery_kw=0.0, battery_kwh=0.0,
                       soc_start_diesel=1.0, soc_stop_diesel=1.0),
        irradiance, load,
    )
    assert result["pv_curtailed_pct"] > 10.0


def test_specific_fuel_consumption_is_realistic():
    irradiance, load = _day()
    result = simulate_minigrid(
        MinigridDesign(name="diesel only", pv_kw=0.0, battery_kw=0.0, battery_kwh=0.0,
                       soc_start_diesel=1.0, soc_stop_diesel=1.0),
        irradiance, load,
    )
    # A small diesel set burns 0.3 to 0.5 litres per kilowatt hour generated.
    assert 0.25 < result["specific_fuel_l_per_kwh"] < 0.60

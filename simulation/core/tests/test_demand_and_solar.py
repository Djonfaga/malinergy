"""Demand and photovoltaic models are checked against observable behaviour."""

import pytest

from mali_energy.demand.profiles import DemandModel
from mali_energy.grid import load_catalog
from mali_energy.solar.pv import design_from_generator, plant_output


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def test_system_peak_falls_in_the_evening():
    model = DemandModel(2024, "urban_mixed", "Bamako")
    series = model.series(1000.0)
    peak = series.idxmax()
    assert 18 <= peak.hour <= 21, f"peak at {peak}"


def test_system_peak_falls_in_the_hot_season():
    model = DemandModel(2024, "urban_mixed", "Bamako")
    series = model.series(1000.0)
    assert series.idxmax().month in (3, 4, 5)


def test_load_factor_is_realistic():
    model = DemandModel(2024, "urban_mixed", "Bamako")
    stats = model.statistics(1000.0)
    assert 0.55 < stats["load_factor"] < 0.80


def test_industrial_profile_is_flatter_than_residential():
    industrial = DemandModel(2024, "industrial", "Bamako").statistics(1000.0)
    residential = DemandModel(2024, "urban_residential", "Bamako").statistics(1000.0)
    assert industrial["load_factor"] > residential["load_factor"]


def test_annual_energy_is_preserved():
    model = DemandModel(2024, "urban_mixed", "Bamako")
    series = model.series(1234.0)
    assert series.sum() / 1000.0 == pytest.approx(1234.0, rel=1e-6)


def test_photovoltaic_yield_matches_published_range(catalog):
    generator = catalog.generators["GEN_PV_SEGOU"]
    result = plant_output(design_from_generator(generator), 2024)
    # Utility plants in southern Mali report 1500-1800 kWh per installed kWp.
    assert 1450 < result.specific_yield_kwh_kwp < 1850
    assert 0.18 < result.capacity_factor < 0.28


def test_irradiance_is_within_the_malian_range(catalog):
    generator = catalog.generators["GEN_PV_KITA"]
    result = plant_output(design_from_generator(generator), 2024)
    assert 1900 < result.resource.annual_ghi_kwh_m2 < 2250


def test_modelled_resource_declares_itself(catalog):
    generator = catalog.generators["GEN_PV_KITA"]
    result = plant_output(design_from_generator(generator), 2024)
    if not result.resource.is_measured:
        assert any("modelled resource" in w for w in result.resource.warnings)


def test_cell_temperature_exceeds_air_temperature(catalog):
    generator = catalog.generators["GEN_PV_SEGOU"]
    result = plant_output(design_from_generator(generator), 2024)
    assert result.diagnostics["mean_cell_temp_c"] > 35.0
    assert result.diagnostics["thermal_loss_pct"] > 3.0

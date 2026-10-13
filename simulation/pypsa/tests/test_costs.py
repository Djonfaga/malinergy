"""The cost table decides the whole dispatch, so its arithmetic is tested.

A marginal cost in this model is not a number read from a file: it is fuel
price divided by calorific value divided by electrical efficiency, plus upkeep.
Every one of those divisions has been got the wrong way round by someone, and a
heat rate inverted by mistake still produces a plausible-looking dollar figure.
"""

import pytest
from mali_pypsa.costs import (
    VALUE_OF_LOST_LOAD_USD_PER_MWH,
    cost_key,
    load_costs,
    load_interchange_costs,
    merit_order,
)


def test_every_row_carries_provenance():
    for cost in load_costs().values():
        assert cost.source, f"{cost.technology} has no source"
        assert cost.confidence in {"measured", "reported", "derived", "estimated"}


def test_marginal_cost_is_fuel_through_the_heat_rate_plus_upkeep():
    cost = load_costs()["thermal_hfo"]
    expected = (
        cost.fuel_price_usd_per_t / cost.fuel_lhv_mwh_per_t / cost.electrical_efficiency
        + cost.vom_usd_per_mwh
    )
    assert cost.marginal_cost_usd_per_mwh == pytest.approx(expected)


def test_dividing_by_efficiency_raises_the_cost():
    """The direction of the heat-rate division, stated as a test."""
    cost = load_costs()["thermal_hfo"]
    assert cost.electrical_efficiency < 1.0
    assert cost.marginal_cost_usd_per_mwh > cost.fuel_cost_usd_per_mwh_th


def test_emissions_per_electrical_unit_exceed_emissions_per_thermal_unit():
    cost = load_costs()["thermal_hfo"]
    assert cost.co2_t_per_mwh_el > cost.co2_t_per_mwh_th


def test_heavy_fuel_oil_is_cheaper_than_diesel_per_unit_sent_out():
    costs = load_costs()
    assert (
        costs["thermal_hfo"].marginal_cost_usd_per_mwh
        < costs["thermal_diesel"].marginal_cost_usd_per_mwh
    )


def test_water_and_sun_have_no_fuel_cost():
    costs = load_costs()
    for technology in ("hydro", "solar"):
        assert costs[technology].fuel_cost_usd_per_mwh_th == 0.0
        assert costs[technology].co2_t_per_mwh_el == 0.0


def test_lost_load_is_priced_above_every_generator():
    worst = max(c.marginal_cost_usd_per_mwh for c in load_costs().values())
    imports = max(load_interchange_costs().values())
    assert max(worst, imports) < VALUE_OF_LOST_LOAD_USD_PER_MWH


def test_cost_key_separates_the_two_thermal_fuels():
    assert cost_key("thermal", "hfo") == "thermal_hfo"
    assert cost_key("thermal", "diesel") == "thermal_diesel"
    assert cost_key("hydro", "water") == "hydro"


def test_merit_order_is_sorted_and_puts_water_first():
    frame = merit_order()
    costs = frame["marginal_cost_usd_per_mwh"].tolist()
    assert costs == sorted(costs)
    assert frame.iloc[0]["technology"] in {"hydro", "solar"}


def test_senegalese_entitlement_energy_is_not_priced_as_a_purchase():
    """Mali's OMVS share is settled in energy, so it carries no tariff."""
    prices = load_interchange_costs()
    assert prices["XC_SEN"] == 0.0
    assert prices["XC_CIV"] > 0.0

"""The fleet translation, where a physical limit becomes a constraint.

The errors worth testing for here are the ones that leave a working model: a
solar plant free to generate at midnight, the full output of an OMVS scheme
credited to Mali, a reservoir flattened to its monthly mean.
"""

from dataclasses import replace

import pandas as pd
import pytest
from mali_pypsa.demand import snapshots
from mali_pypsa.fleet import (
    OMVS_PLANTS,
    RESERVOIR_PLANTS,
    THERMAL_AVAILABILITY,
    build_fleet,
    check_omvs_entitlement,
    fleet_table,
    reservoir_budgets,
)


@pytest.fixture(scope="module")
def solar_profiles(catalog, index):
    """A deliberately crude profile: on by day, off by night."""
    day = pd.Series((index.hour >= 7) & (index.hour <= 18), index=index).astype(float) * 0.6
    return {
        generator.id: day
        for generator in catalog.generators.values()
        if generator.technology == "solar"
    }


@pytest.fixture(scope="module")
def fleet(catalog, index, solar_profiles):
    return build_fleet(catalog, index, solar_profiles=solar_profiles)


def test_a_solar_plant_without_a_profile_is_refused(catalog, index):
    """Silence here would give photovoltaic capacity a ceiling of one at night."""
    with pytest.raises(KeyError, match="no capacity-factor profile"):
        build_fleet(catalog, index, solar_profiles={})


def test_nameplate_is_never_derated(catalog, fleet):
    for spec in fleet:
        assert spec.p_nom_mw == catalog.generators[spec.name].capacity_mw


def test_out_of_service_plant_is_absent_from_the_base_case(catalog, index, solar_profiles):
    names = {s.name for s in build_fleet(catalog, index, solar_profiles=solar_profiles)}
    for generator in catalog.generators.values():
        if not generator.in_service:
            assert generator.id not in names


def test_scenario_assets_come_back_when_asked(catalog, index):
    profiles = {
        generator.id: pd.Series(0.2, index=index)
        for generator in catalog.generators.values()
        if generator.technology == "solar"
    }
    names = {
        s.name
        for s in build_fleet(
            catalog, index, solar_profiles=profiles, include_scenario_assets=True
        )
    }
    assert any(not g.in_service and g.id in names for g in catalog.generators.values())


def test_thermal_carries_a_forced_outage_allowance(fleet):
    thermal = [s for s in fleet if s.carrier == "thermal"]
    assert thermal
    for spec in thermal:
        assert spec.p_max_pu.max() == pytest.approx(THERMAL_AVAILABILITY)


def test_omvs_plant_never_reaches_full_nameplate(fleet):
    found = [s for s in fleet if s.name in OMVS_PLANTS]
    assert found, "the OMVS schemes are missing from the fleet"
    for spec in found:
        assert spec.mali_share < 1.0
        assert spec.p_max_pu.max() <= spec.mali_share + 1e-9


def test_the_entitlement_check_catches_a_full_share(fleet):
    spec = next(s for s in fleet if s.name in OMVS_PLANTS)
    assert check_omvs_entitlement([replace(spec, mali_share=1.0)])


def test_the_entitlement_check_catches_an_oversized_budget(fleet):
    spec = next(s for s in fleet if s.name in OMVS_PLANTS and s.is_reservoir)
    broken = replace(
        spec, monthly_energy_mwh={m: v * 10 for m, v in spec.monthly_energy_mwh.items()}
    )
    assert any("energy budget" in p for p in check_omvs_entitlement([broken]))


def test_a_clean_fleet_passes_the_entitlement_check(fleet):
    assert check_omvs_entitlement(fleet) == []


def test_run_of_river_plant_is_capped_by_the_month(fleet, catalog):
    """Felou has pondage measured in hours, so the river is a power limit."""
    felou = next(s for s in fleet if s.name == "GEN_FELOU")
    assert not felou.is_reservoir
    availability = catalog.hydro_availability["GEN_FELOU"]
    may = felou.p_max_pu[felou.p_max_pu.index.month == 5]
    assert may.max() == pytest.approx(availability[5] * felou.mali_share)


def test_reservoir_plant_may_reach_its_share_in_the_driest_month(fleet):
    """What the dry season takes is hours of full output, not the output."""
    for name in RESERVOIR_PLANTS:
        spec = next(s for s in fleet if s.name == name)
        may = spec.p_max_pu[spec.p_max_pu.index.month == 5]
        assert may.max() == pytest.approx(spec.mali_share)


def test_the_reservoir_budget_equals_the_month_it_replaces(fleet, catalog, index):
    """Swapping a ceiling for a budget must not change the energy available."""
    step = (index[1] - index[0]).total_seconds() / 3600.0
    for name in RESERVOIR_PLANTS:
        spec = next(s for s in fleet if s.name == name)
        availability = catalog.hydro_availability[name]
        for month, budget_mwh in spec.monthly_energy_mwh.items():
            hours = float((index.month == month).sum()) * step
            flat = spec.p_nom_mw * spec.mali_share * availability[month] * hours
            assert budget_mwh == pytest.approx(flat)


def test_only_the_reservoir_plants_carry_a_budget(fleet):
    budgets = reservoir_budgets(fleet)
    assert set(budgets) == set(RESERVOIR_PLANTS)
    for budget in budgets.values():
        assert sorted(budget) == list(range(1, 13))


def test_solar_is_dark_at_night(fleet):
    for spec in fleet:
        if spec.carrier != "solar":
            continue
        night = spec.p_max_pu[
            (spec.p_max_pu.index.hour >= 21) | (spec.p_max_pu.index.hour <= 4)
        ]
        assert night.max() == 0.0


def test_storage_is_not_dispatchable_in_this_version(catalog, index, solar_profiles):
    fleet = build_fleet(
        catalog, index, solar_profiles=solar_profiles, include_scenario_assets=True
    )
    storage = [s for s in fleet if s.carrier == "storage"]
    for spec in storage:
        assert spec.p_max_pu.max() == 0.0


def test_mean_availability_is_comparable_across_both_limit_kinds(fleet, catalog):
    """A reservoir has no single ceiling, so the table reports energy instead."""
    for name in RESERVOIR_PLANTS:
        spec = next(s for s in fleet if s.name == name)
        availability = catalog.hydro_availability[name]
        weighted = sum(
            availability[month] * float((spec.p_max_pu.index.month == month).sum())
            for month in range(1, 13)
        ) / len(spec.p_max_pu)
        assert spec.mean_availability == pytest.approx(weighted * spec.mali_share, rel=1e-6)


def test_available_energy_does_not_depend_on_the_sampling_interval(catalog):
    """A six-hourly year must offer the same energy as an hourly one."""
    totals = []
    for step in (1, 6):
        index = snapshots(2024, step_hours=step)
        profiles = {
            g.id: pd.Series(0.2, index=index)
            for g in catalog.generators.values()
            if g.technology == "solar"
        }
        fleet = build_fleet(catalog, index, solar_profiles=profiles)
        totals.append(sum(s.available_energy_gwh for s in fleet))
    assert totals[0] == pytest.approx(totals[1], rel=0.01)


def test_the_fleet_table_states_which_limit_binds(fleet):
    frame = fleet_table(fleet)
    assert set(frame["limited_by"]) <= {"energy budget", "hourly ceiling"}
    for name in RESERVOIR_PLANTS:
        row = frame[frame["generator"] == name].iloc[0]
        assert row["limited_by"] == "energy budget"
    assert frame["marginal_cost"].tolist() == sorted(frame["marginal_cost"].tolist())

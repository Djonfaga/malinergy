"""Assembly of the single-node network.

A copper plate is a small object, which makes it easy to assume it is right.
The things that can be wrong without the model complaining are all about what
goes in: an interconnection given the thermal rating of its line instead of the
energy actually contracted, an export obligation forgotten, unserved energy
priced below a diesel engine so the optimiser sheds load to save fuel.
"""

import pandas as pd
import pytest
from mali_pypsa.costs import VALUE_OF_LOST_LOAD_USD_PER_MWH, load_interchange_costs
from mali_pypsa.network import BUS, CARRIERS, UNSERVED, build_network


def test_the_network_is_a_single_bus(build):
    assert list(build.network.buses.index) == [BUS]


def test_every_carrier_used_is_declared(build):
    n = build.network
    assert set(n.generators.carrier) <= set(n.carriers.index)
    assert set(n.buses.carrier) <= set(n.carriers.index)
    assert set(CARRIERS) == set(n.carriers.index)


def test_snapshots_are_naive_because_mali_keeps_utc(build):
    """PyPSA refuses aware snapshots; stripping the zone is only lossless here."""
    assert build.network.snapshots.tz is None


def test_snapshot_weightings_restore_the_sampled_hours(build):
    weights = build.network.snapshot_weightings["objective"]
    assert float(weights.sum()) == pytest.approx(8784)


def test_demand_energy_matches_the_profile(build):
    n = build.network
    weights = n.snapshot_weightings["objective"]
    served = float((n.loads_t.p_set["DEMAND"] * weights).sum() / 1000.0)
    assert served == pytest.approx(build.demand.annual_energy_gwh, rel=0.01)


def test_demand_is_the_generation_required_figure_not_a_smaller_one(build):
    """The copper plate has nowhere to put losses but inside demand."""
    required = build.demand.calibration["generation_required_gwh"]
    assert build.demand.annual_energy_gwh == pytest.approx(required, rel=0.01)
    assert required > build.demand.calibration["utility_energy_gwh"]


def test_a_broken_demand_profile_stops_the_build(catalog, monkeypatch):
    """The checks run inside the build, not only in the test suite."""
    from dataclasses import replace

    import mali_pypsa.network as network

    original = network.build_demand

    def peaking_at_noon(*args, **kwargs):
        profile = original(*args, **kwargs)
        shifted = profile.series_mw.copy()
        shifted[:] = 100.0
        shifted[shifted.index.hour == 12] = 400.0
        return replace(profile, series_mw=shifted)

    monkeypatch.setattr(network, "build_demand", peaking_at_noon)
    with pytest.raises(ValueError, match="demand profile failed its checks"):
        build_network(catalog, step_hours=24, prefer_atlite=False)


def test_a_broken_resource_stops_the_build(catalog, monkeypatch):
    import mali_pypsa.network as network
    from mali_pypsa.resource import ResourceResult

    def always_on(cat, year, index, **kwargs):
        return ResourceResult(
            profiles={
                g.id: pd.Series(0.5, index=index)
                for g in cat.generators.values()
                if g.technology == "solar"
            },
            provider="test",
        )

    monkeypatch.setattr(network, "capacity_factors", always_on)
    with pytest.raises(ValueError, match="solar resource failed its checks"):
        build_network(catalog, step_hours=1, prefer_atlite=False)


def test_the_omvs_share_is_not_deducted_twice(build, catalog):
    """The defect this guards against doubled the published unserved energy.

    Manantali, Gouina and Felou are already capped at Mali's 52 per cent, so
    Mali never receives the foreign share. The catalogue describes the Senegal
    link as the exchange *of that share*, so carrying it as a firm export on
    top deducts the same entitlement a second time -- and prices it at zero
    against Malian load valued at the cost of lost load.
    """
    assert "EXPORT_XC_SEN" not in build.network.loads.index
    assert list(build.network.loads.index) == ["DEMAND"]
    assert any("twice" in note for note in build.notes)


def test_the_other_reading_is_available_and_says_what_it_assumes(catalog):
    """The catalogue is ambiguous, so the alternative stays reachable."""
    both = build_network(
        catalog, step_hours=12, prefer_atlite=False,
        omvs_settlement="and_again_on_the_link",
    )
    assert "EXPORT_XC_SEN" in both.network.loads.index
    assert any("export obligation" in note for note in both.notes)


def test_the_two_settlements_differ_by_the_export_energy(catalog):
    plant = build_network(catalog, step_hours=12, prefer_atlite=False)
    link = catalog.interconnections["XC_SEN"]
    both = build_network(
        catalog, step_hours=12, prefer_atlite=False,
        omvs_settlement="and_again_on_the_link",
    )
    weights = both.network.snapshot_weightings["objective"]
    added = float((both.network.loads_t.p_set["EXPORT_XC_SEN"] * weights).sum())
    assert added == pytest.approx(abs(link.typical_import_mw) * 8784, rel=1e-6)
    assert float((plant.network.loads_t.p_set.sum(axis=1) * weights).sum()) == pytest.approx(
        float((both.network.loads_t.p_set.sum(axis=1) * weights).sum()) - added, rel=1e-6
    )


def test_an_unknown_settlement_is_refused(catalog):
    with pytest.raises(ValueError, match="omvs_settlement"):
        build_network(
            catalog, step_hours=24, prefer_atlite=False, omvs_settlement="whichever"
        )


def test_imports_default_to_what_is_contracted_not_what_the_line_can_carry(catalog):
    """The gap is large, and taking the larger number silently is the easy error."""
    contracted = build_network(catalog, step_hours=12, prefer_atlite=False)
    rated = build_network(
        catalog, step_hours=12, prefer_atlite=False, import_basis="capacity"
    )
    imports = contracted.network.generators.carrier == "import"
    assert (
        contracted.network.generators.p_nom[imports].sum()
        < rated.network.generators.p_nom[rated.network.generators.carrier == "import"].sum()
    )
    for link in catalog.interconnections.values():
        if link.in_service and link.typical_import_mw > 0:
            assert contracted.network.generators.at[link.id, "p_nom"] == pytest.approx(
                link.typical_import_mw
            )


def test_an_unknown_import_basis_is_refused(catalog):
    with pytest.raises(ValueError, match="import_basis"):
        build_network(catalog, step_hours=24, prefer_atlite=False, import_basis="guess")


def test_import_prices_come_from_the_table(build):
    prices = load_interchange_costs()
    for name, price in prices.items():
        if name in build.network.generators.index:
            assert build.network.generators.at[name, "marginal_cost"] == pytest.approx(price)


def test_unserved_energy_is_the_most_expensive_thing_on_the_bus(build):
    n = build.network
    assert UNSERVED in n.generators.index
    others = n.generators.drop(index=UNSERVED)
    assert n.generators.at[UNSERVED, "marginal_cost"] > others["marginal_cost"].max()
    assert n.generators.at[UNSERVED, "marginal_cost"] == VALUE_OF_LOST_LOAD_USD_PER_MWH


def test_unserved_capacity_cannot_itself_be_the_binding_limit(build):
    """If it were, infeasibility would masquerade as a shortage of shedding."""
    n = build.network
    peak = float(n.loads_t.p_set.sum(axis=1).max())
    assert n.generators.at[UNSERVED, "p_nom"] > peak


def test_the_reservoir_budgets_travel_with_the_build(build):
    assert build.reservoir_budgets
    for budget in build.reservoir_budgets.values():
        assert sorted(budget) == list(range(1, 13))
        assert all(v > 0 for v in budget.values())


def test_storage_is_not_added_as_a_generator(build):
    assert "storage" not in set(build.network.generators.carrier)


def test_the_build_states_what_it_assumed(build):
    joined = " ".join(build.notes)
    assert "unserved energy priced" in joined
    assert "reservoir" in joined
    assert "minimum stable generation" in joined
    assert "net-import" in joined


def test_a_coarse_run_says_it_cannot_check_the_solar_day(catalog):
    build = build_network(catalog, step_hours=12, prefer_atlite=False)
    assert any("do not resolve the solar day" in note for note in build.notes)


def test_a_fine_run_makes_no_such_excuse(build):
    assert not any("do not resolve the solar day" in note for note in build.notes)

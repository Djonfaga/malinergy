"""Assembly of the single-node network.

A copper plate is a small object, which makes it easy to assume it is right.
The things that can be wrong without the model complaining are all about what
goes in: an interconnection given the thermal rating of its line instead of the
energy actually contracted, an export obligation forgotten, unserved energy
priced below a diesel engine so the optimiser sheds load to save fuel.
"""

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


def test_an_export_obligation_is_carried_as_a_fixed_load(build, catalog):
    exporting = [
        link
        for link in catalog.interconnections.values()
        if link.in_service and link.typical_import_mw < 0
    ]
    for link in exporting:
        assert f"EXPORT_{link.id}" in build.network.loads.index


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

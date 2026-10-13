"""The dispatch itself, and the checks a result has to pass before it is quoted.

A linear programme almost always solves. That is the danger: a wrong model
returns a clean optimum with no indication that anything is amiss. So the
tests here are mostly about the properties the answer must have — energy
balance, merit order, the reservoir budgets — and about whether the checking
code actually catches a violation when one is introduced.
"""

import pandas as pd
import pytest
from mali_pypsa.dispatch import (
    DispatchResult,
    check_results,
    duration_curve,
    monthly_balance,
    reservoir_constraints,
    solve,
)
from mali_pypsa.fleet import RESERVOIR_PLANTS
from mali_pypsa.network import UNSERVED, build_network


def test_the_dispatch_solves(result):
    assert result.ok
    assert result.condition == "optimal"


def test_it_passes_its_own_checks(result):
    assert check_results(result) == []


def test_generation_equals_demand_at_every_snapshot(result):
    n = result.n
    worst = float((n.generators_t.p.sum(axis=1) - n.loads_t.p_set.sum(axis=1)).abs().max())
    assert worst < 1e-4


def test_the_objective_equals_the_cost_of_what_was_dispatched(result):
    n = result.n
    weights = n.snapshot_weightings["objective"]
    energy = n.generators_t.p.mul(weights, axis=0)
    recomputed = float(energy.mul(n.generators.marginal_cost, axis=1).sum().sum())
    assert recomputed == pytest.approx(float(n.objective), rel=1e-6)


def test_water_and_sun_are_taken_before_fuel(result):
    """The merit order, read back out of the answer."""
    n = result.n
    costs = n.generators.marginal_cost
    hydro = n.generators.index[n.generators.carrier == "hydro"]
    thermal = n.generators.index[n.generators.carrier == "thermal"]
    assert costs[hydro].max() < costs[thermal].min()
    hydro_cf = result.generation_gwh[hydro].sum() / max(
        sum(s.available_energy_gwh for s in result.build.fleet if s.carrier == "hydro"), 1e-9
    )
    assert hydro_cf > 0.95, "cheap water was left in the river"


def test_no_generator_exceeds_its_availability(result):
    n = result.n
    for name in n.generators.index:
        ceiling = (
            n.generators_t.p_max_pu[name]
            if name in n.generators_t.p_max_pu
            else n.generators.at[name, "p_max_pu"]
        )
        limit = n.generators.at[name, "p_nom"] * ceiling
        assert float((n.generators_t.p[name] - limit).max()) < 1e-6


def test_every_reservoir_month_spends_its_budget_and_no_more(result):
    """Equality, not inequality: water is the cheapest energy in the country."""
    n = result.n
    weights = n.snapshot_weightings["objective"]
    energy = n.generators_t.p.mul(weights, axis=0)
    for name, budget in result.build.reservoir_budgets.items():
        produced = energy[name].groupby(n.snapshots.month).sum()
        for month, allowed in budget.items():
            assert float(produced[month]) == pytest.approx(allowed, rel=1e-6)


def test_a_reservoir_plant_exceeds_its_monthly_mean_at_the_peak(result):
    """The whole point of the budget: full output in a dry-season evening."""
    n = result.n
    for name in RESERVOIR_PLANTS:
        if name not in n.generators_t.p:
            continue
        may = n.generators_t.p[name][n.snapshots.month == 5]
        assert may.max() > may.mean() * 1.5


def test_a_run_of_river_plant_does_not(result):
    n = result.n
    felou = n.generators_t.p["GEN_FELOU"]
    may = felou[n.snapshots.month == 5]
    assert may.max() == pytest.approx(may.mean(), rel=1e-6)


def test_the_budget_check_catches_a_constraint_that_was_never_added(fresh_build):
    """Solve without the extra functionality and the checker must object.

    This is the failure mode with no symptom: the model solves, the dispatch
    looks reasonable, and the reservoirs have quietly produced more energy than
    the river carries. Only the checker stands between that and a published
    number, so the checker is tested against it directly.
    """
    n = fresh_build.network
    n.optimize(solver_name="highs", log_to_console=False)
    result = DispatchResult(build=fresh_build, status="ok", condition="optimal")
    assert any("budget" in p for p in check_results(result))


def test_the_constraint_builder_adds_one_constraint_per_plant_and_month(fresh_build):
    """An empty dict adding nothing is not evidence that a full one adds something."""
    n = fresh_build.network
    n.optimize.create_model()
    before = len(n.model.constraints)

    reservoir_constraints({}, n.snapshot_weightings["objective"])(n, n.snapshots)
    assert len(n.model.constraints) == before

    reservoir_constraints(
        fresh_build.reservoir_budgets, n.snapshot_weightings["objective"]
    )(n, n.snapshots)
    added = len(n.model.constraints) - before
    assert added == 12 * len(fresh_build.reservoir_budgets)


def test_solar_does_not_generate_at_night(result):
    n = result.n
    solar = n.generators.index[n.generators.carrier == "solar"]
    night = n.generators_t.p[solar][(n.snapshots.hour >= 21) | (n.snapshots.hour <= 4)]
    assert float(night.max().max()) < 0.1


def test_load_is_shed_only_when_nothing_else_is_left(result):
    assert not any("still available" in p for p in check_results(result))


def test_shedding_is_reported_rather_than_hidden(result):
    if result.summary["unserved_gwh"] > 0:
        assert any("unserved" in note for note in result.notes)
        assert result.summary["snapshot_hours_with_unserved"] > 0


def test_the_cost_of_lost_load_is_reported_apart_from_the_fuel_bill(result):
    """And the operating cost must be the fuel bill, not the fuel bill plus it."""
    s = result.summary
    n = result.n
    weights = n.snapshot_weightings["objective"]
    energy = n.generators_t.p.mul(weights, axis=0)
    fuel = energy.drop(columns=[UNSERVED]).mul(n.generators.marginal_cost, axis=1)
    assert s["operating_cost_musd"] == pytest.approx(
        float(fuel.sum().sum()) / 1e6, abs=0.01  # the summary rounds to 0.01 MUSD
    )
    assert s["unserved_cost_musd"] > 0
    assert s["system_cost_musd"] > s["operating_cost_musd"]


def test_emissions_come_only_from_fuel(result):
    n = result.n
    weights = n.snapshot_weightings["objective"]
    thermal_gwh = float(
        n.generators_t.p[n.generators.index[n.generators.carrier == "thermal"]]
        .mul(weights, axis=0)
        .sum()
        .sum()
        / 1000.0
    )
    implied = result.summary["co2_kt"] * 1000.0 / max(thermal_gwh * 1000.0, 1e-9)
    assert 0.55 < implied < 0.95, "implied emission factor is not that of oil plant"


def test_a_modelled_resource_is_never_reported_as_measured(result):
    """The field exists to stop a clear-sky run being cited as observation."""
    assert result.summary["resource_provider"] == result.build.resource.provider
    assert result.summary["resource_measured"] is result.build.resource.is_measured
    if result.summary["resource_provider"].startswith("core/clear-sky"):
        assert result.summary["resource_measured"] is False


def test_monthly_balance_adds_up_to_the_year(result):
    monthly = monthly_balance(result)
    assert len(monthly) == 12
    assert monthly["load_gwh"].sum() == pytest.approx(
        result.summary["total_load_gwh"], rel=0.01
    )
    carriers = [c for c in result.by_carrier_gwh.index if c in monthly.columns]
    for carrier in carriers:
        assert monthly[carrier].sum() == pytest.approx(
            result.by_carrier_gwh[carrier], rel=0.01
        )


def test_the_dry_season_burns_more_fuel_than_the_rains(result):
    monthly = monthly_balance(result)
    assert monthly.loc[5, "thermal"] > monthly.loc[9, "thermal"]


def test_the_price_duration_curve_is_monotonic(result):
    curve = duration_curve(result, "price")
    assert curve.tolist() == sorted(curve.tolist(), reverse=True)
    assert len(curve) == len(result.n.snapshots)


def test_residual_load_is_lower_than_demand_by_day(result):
    """Solar can only subtract, and it does.

    Not a comparison of the two minima: the lightest hour of the year is in the
    middle of the night, where there is no sun to take off, so those two
    numbers coincide and would coincide just as well if solar were ignored
    entirely. The claim with content is snapshot by snapshot.
    """
    n = result.n
    load = n.loads_t.p_set.sum(axis=1)
    solar = n.generators.index[n.generators.carrier == "solar"]
    residual = load - n.generators_t.p[solar].sum(axis=1)

    assert float((residual - load).max()) <= 1e-6, "solar added to the load"
    assert float((load - residual).max()) > 50.0, "solar subtracted nothing at all"

    curve = duration_curve(result, "residual_load")
    assert len(curve) == len(n.snapshots)
    assert curve.max() == pytest.approx(float(residual.max()))
    assert curve.min() == pytest.approx(float(residual.min()))


def test_an_unknown_duration_curve_is_refused(result):
    with pytest.raises(ValueError, match="unknown duration curve"):
        duration_curve(result, "vibes")


def test_a_failed_solve_reports_rather_than_raises(fresh_build):
    """Infeasibility must come back as a result that says so."""
    n = fresh_build.network
    n.generators.loc[UNSERVED, "p_nom"] = 0.0
    n.generators["p_max_pu"] = 0.0
    n.generators_t.p_max_pu = pd.DataFrame(
        0.0, index=n.snapshots, columns=n.generators_t.p_max_pu.columns
    )
    broken = solve(fresh_build)
    assert not broken.ok
    assert any("did not solve" in note for note in broken.notes)
    assert check_results(broken)


def test_the_inputs_are_invariant_to_the_sampling_interval(catalog):
    """What interval averaging guarantees: the energy that goes in.

    Demand alone would pass this if solve returned a constant, so the solar
    energy the optimiser was offered is checked too -- that is the quantity
    the defect this was written for corrupted.
    """
    rows = []
    for step in (6, 12):
        build = build_network(catalog, step_hours=step, prefer_atlite=False)
        solved = solve(build)
        assert solved.ok
        rows.append(
            (
                solved.summary["demand_gwh"],
                float(solved.by_carrier_gwh.get("solar", 0.0)),
            )
        )
    assert rows[0][0] == pytest.approx(rows[1][0], rel=0.005)
    assert rows[0][1] == pytest.approx(rows[1][1], rel=0.01)


def test_the_outputs_are_only_approximately_invariant(catalog):
    """And the README must not claim more than that.

    Shedding is an outcome of the optimisation, not an input to it. Coarse
    sampling averages a short deep shortfall into a long shallow one, so the
    energy moves a little and the hour count moves a great deal. Both are
    pinned here so that a claim of exact invariance cannot be made quietly.
    """
    energy, hours = [], []
    for step in (1, 4):
        build = build_network(catalog, step_hours=step, prefer_atlite=False)
        solved = solve(build)
        assert solved.ok
        energy.append(solved.summary["unserved_gwh"])
        hours.append(solved.summary["snapshot_hours_with_unserved"])
    # Measured: 70.68 GWh hourly against 66.51 GWh four-hourly, a spread of
    # 6 %. The bound is set a little wider than that so the test pins the
    # order of magnitude of the error rather than one solver's exact answer.
    assert energy[0] == pytest.approx(energy[1], rel=0.10)
    assert energy[0] != energy[1], "exact equality here would be suspicious"
    assert abs(hours[0] - hours[1]) > 0.05 * hours[0], (
        "the hour count is a resolution artefact and the model says so; "
        "if it has become stable, the claim needs revisiting"
    )

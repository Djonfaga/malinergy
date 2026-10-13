"""Least-cost dispatch, and the results worth reading from it.

Two things here are not stock PyPSA. The reservoir plants are limited by a
monthly energy budget added to the optimisation model directly, because no
generator attribute expresses "this much energy this month, at any power up to
nameplate". And every result is run through :func:`check_results` before a
number is quoted from it, including a check that those budgets held.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd
import pypsa
import xarray as xr

from .network import BUS, UNSERVED, BuildResult, emission_factors


@dataclass
class DispatchResult:
    build: BuildResult
    status: str
    condition: str
    objective_usd: float = 0.0
    generation_gwh: pd.Series = field(default_factory=pd.Series)
    by_carrier_gwh: pd.Series = field(default_factory=pd.Series)
    cost_usd: pd.Series = field(default_factory=pd.Series)
    prices: pd.Series = field(default_factory=pd.Series)
    summary: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    @property
    def n(self) -> pypsa.Network:
        return self.build.network


def reservoir_constraints(
    budgets: dict[str, dict[int, float]], weights: pd.Series
) -> Callable[[pypsa.Network, pd.Index], None]:
    """Build the extra_functionality that caps each reservoir month.

    One constraint per plant and month: the weighted sum of output over the
    month's snapshots may not exceed the water's energy. Nothing limits the
    power within the month beyond the generator's own ceiling, which is the
    point — this is what a reservoir does and what an hourly cap cannot say.
    """

    def add(n: pypsa.Network, snapshots: pd.Index) -> None:
        if not budgets:
            return
        power = n.model["Generator-p"]
        month_of = pd.DatetimeIndex(snapshots).month
        for name, budget in budgets.items():
            if name not in n.generators.index:
                continue
            for month, energy_mwh in sorted(budget.items()):
                chosen = snapshots[month_of == month]
                if not len(chosen):
                    continue
                hours = xr.DataArray(
                    weights.loc[chosen].to_numpy(),
                    coords={"snapshot": chosen},
                    dims="snapshot",
                )
                produced = (power.loc[chosen, name] * hours).sum()
                n.model.add_constraints(
                    produced <= float(energy_mwh),
                    name=f"reservoir-energy-{name}-{month:02d}",
                )

    return add


def solve(
    build: BuildResult,
    *,
    solver_name: str = "highs",
    log_to_console: bool = False,
) -> DispatchResult:
    """Solve the dispatch and reduce it to the quantities a report needs."""
    n = build.network
    status, condition = n.optimize(
        solver_name=solver_name,
        log_to_console=log_to_console,
        extra_functionality=reservoir_constraints(
            build.reservoir_budgets, n.snapshot_weightings["objective"]
        ),
    )

    result = DispatchResult(build=build, status=str(status), condition=str(condition))
    result.notes.extend(build.notes)
    if result.status != "ok":
        result.notes.append(
            f"the optimisation did not solve: status {status}, condition {condition}"
        )
        return result

    weights = n.snapshot_weightings["objective"]
    dispatch_mw = n.generators_t.p
    energy_mwh = dispatch_mw.mul(weights, axis=0)

    result.generation_gwh = (energy_mwh.sum() / 1000.0).round(3)
    carriers = n.generators.carrier
    result.by_carrier_gwh = (
        result.generation_gwh.groupby(carriers).sum().sort_values(ascending=False).round(3)
    )
    result.cost_usd = (
        energy_mwh.mul(n.generators.marginal_cost, axis=1).sum().round(2)
    )
    result.prices = n.buses_t.marginal_price[BUS]

    demand_mwh = float(
        (n.loads_t.p_set.sum(axis=1) * weights).sum()
    )
    unserved_mwh = float(energy_mwh[UNSERVED].sum()) if UNSERVED in energy_mwh else 0.0
    served_mwh = demand_mwh - unserved_mwh

    unserved_hours = int(
        (dispatch_mw[UNSERVED] > 0.1).mul(weights).sum() if UNSERVED in dispatch_mw else 0
    )
    unserved_cost = float(result.cost_usd.get(UNSERVED, 0.0))

    factors = emission_factors()
    emissions_t = sum(
        float(energy_mwh[name].sum()) * factors.get(name, 0.0)
        for name in energy_mwh.columns
        if name in factors
    )

    fuel_cost = float(result.cost_usd.sum()) - unserved_cost
    result.objective_usd = float(n.objective)
    result.summary = {
        "year": build.demand.calibration.get("year"),
        "solver_status": result.status,
        "demand_gwh": round(demand_mwh / 1000.0, 1),
        "served_gwh": round(served_mwh / 1000.0, 1),
        "unserved_gwh": round(unserved_mwh / 1000.0, 2),
        "unserved_pct": round(100.0 * unserved_mwh / demand_mwh, 2) if demand_mwh else 0.0,
        "hours_with_unserved": unserved_hours,
        "system_cost_musd": round(float(result.cost_usd.sum()) / 1e6, 2),
        "operating_cost_musd": round(fuel_cost / 1e6, 2),
        "unserved_cost_musd": round(unserved_cost / 1e6, 2),
        "unserved_share_of_cost_pct": round(
            100.0 * unserved_cost / max(float(result.cost_usd.sum()), 1e-9), 1
        ),
        "average_cost_usd_per_mwh": round(fuel_cost / max(served_mwh, 1e-9), 2),
        "co2_kt": round(emissions_t / 1000.0, 1),
        "co2_kg_per_kwh": round(emissions_t / max(served_mwh, 1e-9), 3),
        "mean_price_usd_per_mwh": round(float(result.prices.mean()), 2),
        "median_price_usd_per_mwh": round(float(result.prices.median()), 2),
        "solar_curtailed_gwh": round(_curtailment(n, weights, "solar") / 1000.0, 2),
        "resource_provider": build.resource.provider,
        "resource_measured": build.resource.is_measured,
    }

    if unserved_mwh > 0:
        result.notes.append(
            f"{unserved_mwh / 1000.0:.0f} GWh unserved over {unserved_hours} hours, "
            f"{result.summary['unserved_share_of_cost_pct']:.0f} % of the objective. "
            "That share is set by the value of lost load, which is an assumption: "
            "read the operating cost separately."
        )
    return result


def _curtailment(n: pypsa.Network, weights: pd.Series, carrier: str) -> float:
    """Energy a carrier could have produced and did not, in megawatt hours."""
    names = n.generators.index[n.generators.carrier == carrier]
    if not len(names):
        return 0.0
    available = n.generators_t.p_max_pu[
        [c for c in names if c in n.generators_t.p_max_pu]
    ]
    if available.empty:
        return 0.0
    potential = available.mul(n.generators.p_nom[available.columns], axis=1)
    actual = n.generators_t.p[available.columns]
    return float((potential - actual).clip(lower=0).mul(weights, axis=0).sum().sum())


def monthly_balance(result: DispatchResult) -> pd.DataFrame:
    """Energy by carrier and month, which is where the Malian year shows."""
    n = result.n
    weights = n.snapshot_weightings["objective"]
    energy = n.generators_t.p.mul(weights, axis=0)
    by_carrier = energy.T.groupby(n.generators.carrier).sum().T
    monthly = by_carrier.groupby(by_carrier.index.month).sum() / 1000.0

    demand = (n.loads_t.p_set.sum(axis=1) * weights).groupby(
        n.snapshots.month
    ).sum() / 1000.0
    monthly["demand_gwh"] = demand
    if UNSERVED in n.generators_t.p:
        hours = (n.generators_t.p[UNSERVED] > 0.1).mul(weights, axis=0)
        monthly["hours_unserved"] = hours.groupby(n.snapshots.month).sum().astype(int)
    return monthly.round(2).rename_axis("month")


def duration_curve(result: DispatchResult, column: str = "price") -> pd.Series:
    """Sorted price or residual-load duration curve."""
    n = result.n
    if column == "price":
        series = result.prices
    elif column == "residual_load":
        solar = n.generators.index[n.generators.carrier == "solar"]
        series = n.loads_t.p_set.sum(axis=1) - n.generators_t.p[solar].sum(axis=1)
    else:
        raise ValueError(f"unknown duration curve {column!r}")
    return pd.Series(sorted(series.to_numpy(), reverse=True), name=column)


def check_results(result: DispatchResult) -> list[str]:
    """Checks a dispatch result has to pass before anything is quoted from it."""
    problems: list[str] = []
    if not result.ok:
        return [f"the optimisation did not solve: {result.condition}"]

    n = result.n
    weights = n.snapshot_weightings["objective"]

    # Energy balance: generation must equal demand at every snapshot.
    generated = n.generators_t.p.sum(axis=1)
    consumed = n.loads_t.p_set.sum(axis=1)
    worst = float((generated - consumed).abs().max())
    if worst > 1e-4:
        problems.append(f"energy balance violated by up to {worst:.4f} MW")

    # No generator may exceed its availability.
    for name in n.generators.index:
        ceiling = (
            n.generators_t.p_max_pu[name]
            if name in n.generators_t.p_max_pu
            else n.generators.at[name, "p_max_pu"]
        )
        limit = n.generators.at[name, "p_nom"] * ceiling
        excess = float((n.generators_t.p[name] - limit).max())
        if excess > 1e-6:
            problems.append(f"{name} exceeds its availability by {excess:.4f} MW")

    # Every reservoir month must respect its energy budget. The solver reports
    # these as ordinary constraints, so a silent violation would mean the
    # constraint was never added -- which is exactly the failure to catch.
    energy_by_snapshot = n.generators_t.p.mul(weights, axis=0)
    for name, budget in result.build.reservoir_budgets.items():
        if name not in energy_by_snapshot:
            problems.append(f"{name} has an energy budget but is not in the dispatch")
            continue
        produced = energy_by_snapshot[name].groupby(n.snapshots.month).sum()
        for month, allowed in budget.items():
            got = float(produced.get(month, 0.0))
            if got > allowed + max(1e-6, 1e-9 * allowed):
                problems.append(
                    f"{name} produced {got / 1000:,.1f} GWh in month {month}, above its "
                    f"{allowed / 1000:,.1f} GWh budget"
                )

    # The objective must equal the cost of what was dispatched.
    recomputed = float(
        energy_by_snapshot.mul(n.generators.marginal_cost, axis=1).sum().sum()
    )
    if abs(recomputed - float(n.objective)) > max(1.0, 1e-6 * abs(float(n.objective))):
        problems.append(
            f"objective {n.objective:,.0f} does not match the dispatched cost "
            f"{recomputed:,.0f}"
        )

    # Solar must not run at night.
    solar = n.generators.index[n.generators.carrier == "solar"]
    if len(solar):
        night = n.generators_t.p[solar][
            (n.snapshots.hour >= 21) | (n.snapshots.hour <= 4)
        ]
        if float(night.max().max()) > 0.1:
            problems.append("a solar plant generates at night")

    # Unserved energy is priced above everything, so it must be the last resort.
    if UNSERVED in n.generators_t.p:
        shedding = n.generators_t.p[UNSERVED] > 0.1
        if shedding.any():
            others = [c for c in n.generators_t.p.columns if c != UNSERVED]
            available = sum(
                n.generators.at[c, "p_nom"]
                * (
                    n.generators_t.p_max_pu[c]
                    if c in n.generators_t.p_max_pu
                    else n.generators.at[c, "p_max_pu"]
                )
                for c in others
            )
            # A reservoir plant with an exhausted monthly budget still shows
            # headroom under its power ceiling, and counting that as available
            # capacity would turn a correct dispatch into a false alarm.
            exhausted = pd.Series(0.0, index=n.snapshots)
            for name, budget in result.build.reservoir_budgets.items():
                if name not in energy_by_snapshot:
                    continue
                produced = energy_by_snapshot[name].groupby(n.snapshots.month).sum()
                spent = {
                    month
                    for month, allowed in budget.items()
                    if float(produced.get(month, 0.0)) >= allowed - max(1.0, 1e-6 * allowed)
                }
                ceiling = (
                    n.generators_t.p_max_pu[name]
                    if name in n.generators_t.p_max_pu
                    else pd.Series(n.generators.at[name, "p_max_pu"], index=n.snapshots)
                )
                headroom_mw = (n.generators.at[name, "p_nom"] * ceiling
                               - n.generators_t.p[name])
                exhausted += headroom_mw.where(
                    pd.Series(n.snapshots.month, index=n.snapshots).isin(spent), 0.0
                )

            headroom = (
                available - n.generators_t.p[others].sum(axis=1) - exhausted
            )[shedding]
            if float(headroom.max()) > 1.0:
                problems.append(
                    "load was shed while generation capacity was still available"
                )
    return problems

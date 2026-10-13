"""Assembly of the single-node PyPSA network.

One bus, called ``MALI``. Everything else hangs off it: the demand, the
generation fleet, the interconnections, and an explicit unserved-energy
generator.

Three assembly decisions carry the model, and each is written out rather than
left to a default.

**Unserved energy is a generator, not a solver failure.** Mali does not meet
its dry-season peak. A model without somewhere for that to go is simply
infeasible in April, which tells a reader nothing. An expensive generator named
``UNSERVED`` absorbs it, so the deficit comes out as a quantity with hours and
a month attached. Its price is a modelling parameter, and the report states how
much of total system cost it accounts for.

**Interconnections are priced generators limited to what is contracted, not to
what the wire can carry.** Imports from Côte d'Ivoire enter the merit order at
their contract price, which is where they belong: cheaper than Malian
distillate, dearer than Malian hydro. The ceiling matters more than the price.
Given the 200 MW thermal rating of the line, the optimiser imports 1630 GWh a
year — it holds the interconnection at its rating almost continuously, because
Ivorian energy is cheaper than anything Mali can burn. That is not a forecast,
it is an artefact of treating a transfer limit as an energy entitlement.
``import_basis`` therefore defaults to the contracted exchange the catalogue
records, and the capacity basis is kept available so a study can show the gap
between the two.

The Senegal exchange is an OMVS entitlement settled in energy rather than a
purchase, so it appears as a fixed export obligation on the demand side.

**Minimum stable generation is recorded and not bound.** A linear dispatch
without unit commitment cannot represent a machine that is off; binding
``p_min_pu`` would force output from plant the optimiser never started. The
value travels with the fleet specification for a later version that models
commitment, and v0.1 says that the limit is absent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import pypsa

from mali_energy.config import StudyConfig
from mali_energy.grid.schema import GridCatalog

from .costs import (
    VALUE_OF_LOST_LOAD_USD_PER_MWH,
    load_costs,
    load_interchange_costs,
)
from .demand import DemandProfile, build_demand, snapshots
from .fleet import GeneratorSpec, build_fleet, check_omvs_entitlement, reservoir_budgets
from .resource import ResourceResult, capacity_factors

BUS = "MALI"
UNSERVED = "UNSERVED"


def _naive(obj):
    """Drop the timezone before handing anything to PyPSA.

    PyPSA refuses timezone-aware snapshots. Dropping the zone is lossless here
    for one specific reason: Mali keeps UTC all year and observes no daylight
    saving, so local time and UTC never diverge and the solar position stays
    aligned with the clock. The same step applied to a country with a summer
    shift would move every profile by an hour twice a year.
    """
    if isinstance(obj, pd.DatetimeIndex):
        return obj.tz_localize(None) if obj.tz is not None else obj
    if getattr(obj.index, "tz", None) is not None:
        obj = obj.copy()
        obj.index = obj.index.tz_localize(None)
    return obj

#: Carrier colours and emission factors are attached to the network so that
#: results can be grouped without the report re-deriving them.
CARRIERS = {
    "AC": 0.0,           # the bus and the loads sit on it; declared so the
                         # network passes its own consistency check
    "hydro": 0.0,
    "solar": 0.0,
    "thermal": 0.0,      # emissions are set per generator, from its own fuel
    "import": 0.0,
    "unserved": 0.0,
    "storage": 0.0,
}


@dataclass
class BuildResult:
    network: pypsa.Network
    demand: DemandProfile
    resource: ResourceResult
    fleet: list[GeneratorSpec]
    notes: list[str]
    #: Monthly energy, in megawatt hours, that each reservoir plant may produce.
    #: Carried on the build because it is enforced as a constraint added to the
    #: optimisation model rather than as a component attribute.
    reservoir_budgets: dict[str, dict[int, float]] = field(default_factory=dict)

    @property
    def n(self) -> pypsa.Network:
        return self.network


def build_network(
    catalog: GridCatalog | None = None,
    config: StudyConfig | None = None,
    *,
    year: int | None = None,
    step_hours: int = 1,
    demand_basis: str = "generation_required",
    prefer_atlite: bool = True,
    include_scenario_assets: bool = False,
    value_of_lost_load: float = VALUE_OF_LOST_LOAD_USD_PER_MWH,
    import_basis: str = "contracted",
) -> BuildResult:
    """Build the v0.1 network.

    ``import_basis`` selects the ceiling on each import: ``contracted`` uses the
    typical exchange the catalogue records, ``capacity`` uses the thermal rating
    of the interconnection. The difference is large and is a result in itself.
    """
    if import_basis not in {"contracted", "capacity"}:
        raise ValueError(f"import_basis must be 'contracted' or 'capacity', not {import_basis!r}")
    from mali_energy.grid import load_catalog

    catalog = catalog or load_catalog()
    config = config or StudyConfig()
    year = year or config.year
    notes: list[str] = []

    index = snapshots(year, step_hours=step_hours)
    demand = build_demand(catalog, config, basis=demand_basis)
    demand_series = demand.series_mw.reindex(index).interpolate(limit_direction="both")

    resource = capacity_factors(catalog, year, index, prefer_atlite=prefer_atlite)
    notes.extend(resource.warnings)

    fleet = build_fleet(
        catalog,
        index,
        solar_profiles=resource.profiles,
        include_scenario_assets=include_scenario_assets,
    )
    entitlement = check_omvs_entitlement(fleet)
    if entitlement:
        raise ValueError("OMVS entitlement check failed: " + "; ".join(entitlement))

    n = pypsa.Network()
    n.set_snapshots(_naive(index))
    # Each snapshot stands for step_hours of real time. Without this the
    # objective and every energy total come out divided by the sampling
    # interval, and a six-hourly run silently reports a sixth of the fuel bill.
    n.snapshot_weightings.loc[:, :] = float(step_hours)

    for carrier, emissions in CARRIERS.items():
        n.add("Carrier", carrier, co2_emissions=emissions)

    n.add("Bus", BUS, v_nom=225.0, carrier="AC")
    n.add("Load", "DEMAND", bus=BUS, p_set=_naive(demand_series), carrier="AC")

    for spec in fleet:
        if spec.carrier == "storage":
            notes.append(f"{spec.name}: storage is not dispatched in v0.1")
            continue
        n.add(
            "Generator",
            spec.name,
            bus=BUS,
            carrier=spec.carrier,
            p_nom=spec.p_nom_mw,
            p_max_pu=_naive(spec.p_max_pu),
            marginal_cost=spec.marginal_cost_usd_per_mwh,
            efficiency=1.0,
        )

    # -- interconnections --------------------------------------------------
    prices = load_interchange_costs()
    for link in catalog.interconnections.values():
        if not link.in_service:
            continue
        price = prices.get(link.id, 0.0)
        if link.typical_import_mw >= 0:
            ceiling = (
                link.typical_import_mw if import_basis == "contracted" else link.capacity_mw
            )
            n.add(
                "Generator",
                link.id,
                bus=BUS,
                carrier="import",
                p_nom=ceiling,
                marginal_cost=price,
                efficiency=1.0,
            )
            notes.append(
                f"{link.id}: import of up to {ceiling:.0f} MW at ${price:.0f}/MWh "
                f"({import_basis} basis; the line is rated {link.capacity_mw:.0f} MW "
                f"and the contracted exchange is {link.typical_import_mw:.0f} MW)"
            )
        else:
            export_mw = abs(link.typical_import_mw)
            n.add(
                "Load",
                f"EXPORT_{link.id}",
                bus=BUS,
                p_set=pd.Series(export_mw, index=_naive(index)),
                carrier="AC",
            )
            notes.append(
                f"{link.id}: {export_mw:.0f} MW export obligation, carried as a fixed load "
                "because the OMVS exchange is an entitlement settled in energy rather "
                "than a purchase"
            )

    # -- unserved energy ---------------------------------------------------
    n.add(
        "Generator",
        UNSERVED,
        bus=BUS,
        carrier="unserved",
        p_nom=float(demand_series.max()) * 1.5,
        marginal_cost=value_of_lost_load,
        efficiency=1.0,
    )
    notes.append(
        f"unserved energy priced at ${value_of_lost_load:.0f}/MWh, above every "
        "generator so the optimiser sheds only when nothing else is available"
    )
    notes.append(
        "minimum stable generation is recorded in the fleet specification but not "
        "bound: a linear dispatch without unit commitment cannot represent a "
        "machine that is off"
    )
    budgets = reservoir_budgets(fleet)
    for name, budget in budgets.items():
        notes.append(
            f"{name}: reservoir plant, limited by a monthly energy budget "
            f"({sum(budget.values()) / 1000:,.0f} GWh over the year) and free to reach "
            "its Malian share of nameplate in any hour, rather than capped hour by "
            "hour at the month's mean"
        )
    notes.append(
        "run-of-river plant is limited hour by hour, because there is no storage to "
        "move energy with; reservoir plant is limited by energy within the month but "
        "not across months, so the model may not carry water from the wet season into "
        "the dry one the way the real operator does"
    )
    notes.append(
        "no minimum release is imposed on the reservoir plants. In reality water is "
        "passed for irrigation and navigation whether or not the power is wanted; "
        "here hydro is the cheapest energy available, so the budget is spent in full "
        "regardless, and only its placement within the month is affected"
    )
    notes.append(
        "the model's import variable is not comparable with the national net-import "
        "statistic: Manantali stands on Malian soil and its Senegalese and "
        "Mauritanian shares are counted as Malian exports in national accounts, "
        "whereas this model simply never gives Mali that energy"
    )

    return BuildResult(
        network=n,
        demand=demand,
        resource=resource,
        fleet=fleet,
        notes=notes,
        reservoir_budgets=budgets,
    )


def emission_factors(catalog: GridCatalog | None = None) -> dict[str, float]:
    """Tonnes of carbon dioxide per megawatt hour, per generator."""
    from mali_energy.grid import load_catalog

    from .costs import cost_key

    catalog = catalog or load_catalog()
    costs = load_costs()
    factors: dict[str, float] = {}
    for generator in catalog.generators.values():
        key = cost_key(generator.technology, generator.fuel)
        if key in costs:
            factors[generator.id] = costs[key].co2_t_per_mwh_el
    return factors

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
Given the 200 MW thermal rating of the line the optimiser holds the
interconnection at that rating almost continuously, because Ivorian energy is
cheaper than anything Mali can burn; the figure the model then reports is in
``results/import_basis_comparison.csv`` rather than quoted here, so that it
cannot drift away from the run that produced it. That is not a forecast, it is
an artefact of treating a transfer limit as an energy entitlement.
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

from dataclasses import dataclass, field, replace

import pandas as pd
import pypsa

from mali_energy.config import StudyConfig
from mali_energy.grid.schema import GridCatalog

from .costs import (
    VALUE_OF_LOST_LOAD_USD_PER_MWH,
    load_costs,
    load_interchange_costs,
)
from .demand import (
    DemandProfile,
    build_demand,
    check_energy_balance,
    resample,
    snapshot_weightings,
    snapshots,
)
from .fleet import GeneratorSpec, build_fleet, check_omvs_entitlement, reservoir_budgets
from .resource import ResourceResult, capacity_factors, check_profiles
from .sampling import resolves_day

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
#: Interconnections whose catalogue entry describes the settlement of the OMVS
#: hydro shares rather than a commercial trade. For these, and only these, the
#: export may already be accounted for at the plant.
OMVS_SETTLEMENT_LINKS = ("XC_SEN",)
OMVS_SHARE_DISPLAY = "52 % entitlement"

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
    #: The catalogue this network was built from. Carried so that anything
    #: derived afterwards -- emission factors above all -- is derived from the
    #: same data, rather than quietly reloading the default one.
    catalog: GridCatalog | None = None
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
    omvs_settlement: str = "at_the_plant",
) -> BuildResult:
    """Build the v0.1 network.

    ``import_basis`` selects the ceiling on each import: ``contracted`` uses the
    typical exchange the catalogue records, ``capacity`` uses the thermal rating
    of the interconnection. The difference is large and is a result in itself.

    ``omvs_settlement`` says where Mali's share of the OMVS cascade is taken
    off, and the choice matters more than it looks:

    ``at_the_plant`` (default)
        Manantali, Gouina and Felou never produce more than Mali's entitlement,
        and the Senegal interconnection carries no export load. The catalogue
        records that link as "exchange of the OMVS hydro shares", so carrying
        it *as well* would deduct the same entitlement twice.
    ``and_again_on_the_link``
        The entitlement is withheld at the plant and the catalogue's exchange
        is carried as a firm export on top. This is only right if that exchange
        is a separate commercial sale rather than the share settlement, which
        the catalogue does not say. Kept selectable because the question is
        open and the answer moves the headline numbers by a factor of two.
    """
    if import_basis not in {"contracted", "capacity"}:
        raise ValueError(f"import_basis must be 'contracted' or 'capacity', not {import_basis!r}")
    if omvs_settlement not in {"at_the_plant", "and_again_on_the_link"}:
        raise ValueError(
            "omvs_settlement must be 'at_the_plant' or 'and_again_on_the_link', "
            f"not {omvs_settlement!r}"
        )
    from mali_energy.grid import load_catalog

    catalog = catalog or load_catalog()
    config = config or StudyConfig()
    year = year or config.year
    # The year has to reach the demand model as well as the snapshot index.
    # Without this, --year 2023 builds 2023 snapshots around a 2024 demand
    # series: the two indices share no timestamp, so the profile resamples to
    # all-NaN hourly or to a single flat value when sampled, and the model
    # solves cleanly with the right annual energy and no shape at all.
    if config.year != year:
        config = replace(config, year=year)
    notes: list[str] = []

    index = snapshots(year, step_hours=step_hours)
    demand = build_demand(catalog, config, basis=demand_basis)
    # Checked here rather than left for a test to find. A demand profile on the
    # wrong basis, or with its evening peak in the wrong place, produces a
    # model that solves cleanly and answers a different question.
    problems = check_energy_balance(demand)
    if problems:
        raise ValueError("the demand profile failed its checks: " + "; ".join(problems))
    demand_series = resample(demand, index)

    resource = capacity_factors(catalog, year, index, prefer_atlite=prefer_atlite)
    notes.extend(resource.warnings)
    problems = check_profiles(resource)
    if problems:
        raise ValueError("the solar resource failed its checks: " + "; ".join(problems))

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
    # Taken from snapshot_weightings rather than written inline so that the
    # model and the function the tests check cannot drift apart.
    n.snapshot_weightings.loc[:, :] = snapshot_weightings(
        index, step_hours=step_hours
    ).to_numpy()[:, None]

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
        if link.id not in prices:
            # Defaulting to zero would place the link below hydro in the merit
            # order and run it flat out. build_fleet refuses the analogous case
            # for a generator; this is the same refusal.
            raise KeyError(
                f"{link.id} has no row in interchange_costs.csv. A missing price "
                "is not a free import."
            )
        price = prices[link.id]
        # Keyed off the direction the catalogue records, not off the sign of a
        # number. A bidirectional link with a net export happens to have a
        # negative typical exchange today; reading the sign makes the model's
        # treatment of it an accident of this year's data.
        if link.direction == "import":
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
        elif link.direction == "bidirectional" and link.typical_import_mw >= 0:
            # Recorded as able to flow either way, with no net exchange. The
            # model offers nothing on it: claiming import headroom on a link
            # the catalogue does not say delivers energy would invent supply.
            notes.append(
                f"{link.id}: bidirectional with no net exchange recorded, so no "
                "energy is offered on it in either direction"
            )
        elif link.id in OMVS_SETTLEMENT_LINKS and omvs_settlement == "at_the_plant":
            notes.append(
                f"{link.id}: the catalogue records this as the exchange of the OMVS "
                f"hydro shares ({abs(link.typical_import_mw):.0f} MW out). It is not "
                "carried as a load, because the same entitlement is already withheld "
                "at Manantali, Gouina and Felou, which never produce more than Mali's "
                f"{OMVS_SHARE_DISPLAY}. Deducting it twice would charge Mali for "
                "energy it was never given"
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
    if not resolves_day(index):
        notes.append(
            f"snapshots of {step_hours} hours do not resolve the solar day. Every "
            "profile is averaged over its interval, so annual energy is right, but a "
            "single snapshot straddles sunrise and the diurnal checks are not applied"
        )
    notes.append(
        "imported energy is counted as carbon free. It is not: the Ivorian system "
        "is largely gas fired. Every emission figure here is therefore the carbon "
        "of Malian plant, diluted over Malian and imported energy alike, and any "
        "saving that comes from importing more is overstated"
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
        catalog=catalog,
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

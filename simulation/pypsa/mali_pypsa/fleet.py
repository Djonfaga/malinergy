"""The EDM-SA generation fleet, as PyPSA generator specifications.

The catalogue in ``simulation/core`` describes each plant physically: a
capacity, a technology, a fuel, a minimum stable output, a Malian share where
the plant is shared with Senegal and Mauritania, and a monthly availability
where the river decides. This module turns that into what a dispatch optimiser
needs, and the whole job is to keep each physical limit visible as its own
constraint rather than collapsing them into one derated number.

Three limits, kept separate because they behave differently:

``p_nom``
    Nameplate capacity. Never reduced, so the model always states what is
    actually installed.
``p_max_pu``
    An hourly ceiling carrying what the plant can deliver *now*: the river's
    seasonal limit, Mali's entitlement on the OMVS schemes, the sun, and a
    forced-outage allowance on thermal plant.
``p_min_pu``
    Minimum stable generation, applied only where a plant is committed. In a
    pure economic dispatch without unit commitment a minimum is a trap: it
    forces output from a machine the optimiser would rather not run at all. So
    v0.1 records the value and does not bind it, and says so.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from mali_energy.grid.schema import GridCatalog

from .costs import TechnologyCost, cost_key, load_costs

#: Forced-outage and maintenance allowance on thermal plant, applied as a flat
#: ceiling on availability. A fleet of medium-speed engines in Mali does not
#: deliver its nameplate for 8760 hours; 8 % is the usual planning allowance.
THERMAL_AVAILABILITY = 0.92

#: Hydro plants whose output Mali shares with Senegal and Mauritania. The share
#: itself lives in the catalogue; this is only the check that it was applied.
OMVS_PLANTS = ("GEN_MANANTALI", "GEN_GOUINA", "GEN_FELOU")


@dataclass
class GeneratorSpec:
    """One PyPSA generator, with the provenance of its limits attached."""

    name: str
    carrier: str
    p_nom_mw: float
    marginal_cost_usd_per_mwh: float
    co2_t_per_mwh: float
    p_max_pu: pd.Series                 # hourly, 0..1
    p_min_pu_recorded: float = 0.0      # recorded, not bound: see the module docstring
    mali_share: float = 1.0
    fuel: str = ""
    source: str = ""
    confidence: str = ""
    limits: list[str] = field(default_factory=list)

    @property
    def available_energy_gwh(self) -> float:
        """Energy the plant could deliver over the year if always called."""
        return float(self.p_nom_mw * self.p_max_pu.sum() / 1000.0)

    @property
    def mean_availability(self) -> float:
        return float(self.p_max_pu.mean())


def _hydro_availability(
    catalog: GridCatalog, generator_id: str, index: pd.DatetimeIndex, mali_share: float
) -> pd.Series:
    """Monthly river availability, times Mali's entitlement, as an hourly ceiling."""
    monthly = catalog.hydro_availability.get(generator_id, {})
    if not monthly:
        return pd.Series(mali_share, index=index)
    values = np.array([monthly.get(month, 1.0) for month in index.month], dtype=float)
    return pd.Series(values * mali_share, index=index)


def build_fleet(
    catalog: GridCatalog,
    index: pd.DatetimeIndex,
    *,
    solar_profiles: dict[str, pd.Series] | None = None,
    costs: dict[str, TechnologyCost] | None = None,
    include_scenario_assets: bool = False,
) -> list[GeneratorSpec]:
    """Translate the catalogue fleet into generator specifications.

    Parameters
    ----------
    solar_profiles:
        Per-plant capacity factor, indexed like ``index``. A solar plant without
        a profile is an error rather than a plant that runs flat out: silently
        giving photovoltaic capacity a ceiling of one would let it generate at
        midnight.
    include_scenario_assets:
        Include plant marked out of service in the catalogue — the Safo and
        Sikasso photovoltaic projects, the Bamako battery. Off by default, so
        the base case is the fleet that exists.
    """
    costs = costs or load_costs()
    solar_profiles = solar_profiles or {}
    specs: list[GeneratorSpec] = []

    for generator in catalog.generators.values():
        if not generator.in_service and not include_scenario_assets:
            continue
        key = cost_key(generator.technology, generator.fuel)
        if key not in costs:
            raise KeyError(
                f"{generator.id}: no cost row for technology {generator.technology!r} "
                f"and fuel {generator.fuel!r}"
            )
        cost = costs[key]
        limits: list[str] = []

        if generator.technology == "hydro":
            ceiling = _hydro_availability(catalog, generator.id, index, generator.mali_share)
            limits.append("monthly river availability")
            if generator.mali_share < 1.0:
                limits.append(f"Malian share of an OMVS scheme ({generator.mali_share:.0%})")
        elif generator.technology == "solar":
            if generator.id not in solar_profiles:
                raise KeyError(
                    f"{generator.id} is a solar plant with no capacity-factor profile. "
                    "Without one it would be free to generate at midnight."
                )
            ceiling = solar_profiles[generator.id].reindex(index).fillna(0.0).clip(0.0, 1.0)
            limits.append("hourly solar resource")
        elif generator.technology == "storage":
            # v0.1 has no storage optimisation; a battery is carried as an
            # out-of-service scenario asset and excluded from the base case.
            ceiling = pd.Series(0.0, index=index)
            limits.append("storage not modelled in v0.1")
        else:
            ceiling = pd.Series(THERMAL_AVAILABILITY, index=index)
            limits.append(f"forced-outage allowance ({1 - THERMAL_AVAILABILITY:.0%})")

        specs.append(
            GeneratorSpec(
                name=generator.id,
                carrier=generator.technology,
                p_nom_mw=generator.capacity_mw,
                marginal_cost_usd_per_mwh=cost.marginal_cost_usd_per_mwh,
                co2_t_per_mwh=cost.co2_t_per_mwh_el,
                p_max_pu=ceiling,
                p_min_pu_recorded=(
                    generator.min_load_mw / generator.capacity_mw
                    if generator.capacity_mw > 0
                    else 0.0
                ),
                mali_share=generator.mali_share,
                fuel=generator.fuel,
                source=generator.source,
                confidence=generator.confidence,
                limits=limits,
            )
        )
    return specs


def fleet_table(specs: list[GeneratorSpec]) -> pd.DataFrame:
    """The fleet as a table, for the report and for eyeballing."""
    rows = [
        {
            "generator": s.name,
            "carrier": s.carrier,
            "fuel": s.fuel,
            "p_nom_mw": s.p_nom_mw,
            "mali_share": s.mali_share,
            "mean_availability": round(s.mean_availability, 3),
            "available_gwh": round(s.available_energy_gwh, 1),
            "marginal_cost": round(s.marginal_cost_usd_per_mwh, 2),
            "min_stable_pu": round(s.p_min_pu_recorded, 3),
            "limits": "; ".join(s.limits),
            "confidence": s.confidence,
        }
        for s in specs
    ]
    frame = pd.DataFrame(rows)
    return frame.sort_values("marginal_cost").reset_index(drop=True)


def check_omvs_entitlement(specs: list[GeneratorSpec]) -> list[str]:
    """Confirm the OMVS plants are limited to Mali's share.

    Treating the full output of Manantali, Gouina and Felou as Malian is the
    single largest error available in a study of this system; it is worth a
    dedicated check rather than trusting that a column was read.
    """
    problems = []
    for spec in specs:
        if spec.name in OMVS_PLANTS:
            if spec.mali_share >= 1.0:
                problems.append(f"{spec.name} is an OMVS scheme but carries a full Malian share")
            if spec.p_max_pu.max() > spec.mali_share + 1e-9:
                problems.append(
                    f"{spec.name} reaches {spec.p_max_pu.max():.3f} of nameplate, above "
                    f"Mali's {spec.mali_share:.2f} entitlement"
                )
    return problems

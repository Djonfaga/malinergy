"""Ordre de mérite: quel kWh est appelé, à quel coût, et lequel on déplace.

Le parc malien est fortement segmente: une base hydraulique très bon marché mais
saisonniere, puis un empilement thermique dont le coût variable double d'un cran a
l'autre. Toute la question économique du secteur tient dans le haut de cette pile —
c'est le seul endroit ou un kWh évité vaut plus de 200 FCFA.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from malinergy.datasets import Registry

HOURS_PER_YEAR = 8760.0


@dataclass(frozen=True)
class StackEntry:
    id: str
    name: str
    technology: str
    available_mw: float
    cumulative_mw: float
    variable_cost_xof_per_kwh: float
    dispatched_mw: float


def _unit_cost(plant: dict) -> float:
    """Coût variable retenu pour le classement (PPA pour les contrats d'achat)."""
    if plant.get("ppa_xof_per_kwh") is not None:
        return float(plant["ppa_xof_per_kwh"])
    return float(plant["variable_cost_xof_per_kwh"])


def available_capacity(registry: Registry, *, include_isolated: bool = False) -> list[dict]:
    plants = []
    for plant in registry["generation"]["plants"]:
        if plant["type"] == "thermal_isolated" and not include_isolated:
            continue
        plants.append(plant)
    return plants


def merit_order(
    registry: Registry, demand_mw: float | None = None, *, solar_available: bool = True
) -> list[StackEntry]:
    """Empile le parc par coût variable croissant jusqu'à couvrir la demande.

    ``solar_available=False`` représente la pointe du soir, ou le PV sans stockage
    ne contribue pas — c'est dans cet État de réseau que se décide le besoin de
    capacité ferme.
    """
    if demand_mw is None:
        demand_mw = registry.value("sector", "aggregates", "peak_demand_mw")

    plants = available_capacity(registry)
    ranked = sorted(plants, key=_unit_cost)

    stack: list[StackEntry] = []
    cumulative = 0.0
    remaining = demand_mw
    for plant in ranked:
        available = float(plant["capacity_mw"]) * float(plant["availability"])
        if plant["type"] == "solar_pv" and not solar_available:
            available = 0.0
        cumulative += available
        dispatched = max(0.0, min(available, remaining))
        remaining -= dispatched
        stack.append(
            StackEntry(
                id=plant["id"],
                name=plant["name"],
                technology=plant["type"],
                available_mw=available,
                cumulative_mw=cumulative,
                variable_cost_xof_per_kwh=_unit_cost(plant),
                dispatched_mw=dispatched,
            )
        )
    return stack


def marginal_cost(
    registry: Registry, demand_mw: float | None = None, *, solar_available: bool = False
) -> float:
    """Coût variable de la derniere unite appelée.

    Par defaut on se place à la pointe du soir sans solaire: c'est l'État de réseau
    qui dimensionne le système et qui fixe la valeur d'un kWh économisé.
    """
    stack = merit_order(registry, demand_mw, solar_available=solar_available)
    dispatched = [e for e in stack if e.dispatched_mw > 0]
    if not dispatched:
        return 0.0
    return dispatched[-1].variable_cost_xof_per_kwh


def capacity_balance(registry: Registry) -> dict[str, float]:
    """Confronte la capacité reellement disponible à la demande, pointe comprise."""
    peak = registry.value("sector", "aggregates", "peak_demand_mw")
    suppressed = registry.value("sector", "aggregates", "suppressed_peak_mw")

    stack_day = merit_order(registry, peak, solar_available=True)
    stack_evening = merit_order(registry, peak, solar_available=False)

    firm = sum(e.available_mw for e in stack_evening)
    total = sum(e.available_mw for e in stack_day)
    return {
        "peak_demand_mw": peak,
        "suppressed_demand_mw": suppressed,
        "latent_peak_mw": peak + suppressed,
        "available_daytime_mw": total,
        "available_firm_mw": firm,
        "firm_margin_mw": firm - peak,
        "latent_firm_gap_mw": (peak + suppressed) - firm,
    }


def annual_fuel_bill(registry: Registry) -> dict[str, float]:
    """Dépense annuelle de combustible et d'achats d'énergie, par filière."""
    generation_kwh = registry.value("sector", "aggregates", "generation_gwh_year") * 1e6
    plants = available_capacity(registry, include_isolated=True)

    # Repartition de la production selon la capacite disponible x facteur de charge,
    # renormalisee sur la production totale observee.
    weights = {
        p["id"]: float(p["capacity_mw"])
        * float(p["availability"])
        * float(p["capacity_factor"])
        for p in plants
    }
    total_weight = sum(weights.values())

    by_tech: dict[str, float] = {}
    total_cost = 0.0
    for plant in plants:
        kwh = generation_kwh * weights[plant["id"]] / total_weight
        cost = kwh * _unit_cost(plant)
        fixed = (
            float(plant.get("fixed_cost_xof_per_kw_month", 0.0))
            * float(plant["capacity_mw"])
            * 12
        )
        cost += fixed
        by_tech[plant["type"]] = by_tech.get(plant["type"], 0.0) + cost
        total_cost += cost

    return {
        "total_xof": total_cost,
        "by_technology_xof": by_tech,
        "average_generation_cost_xof_per_kwh": total_cost / generation_kwh,
    }


def displacement_value(
    registry: Registry, mw: float, *, site: str = "segou", hours_available: float = 5.2
) -> dict[str, float]:
    """Valeur annuelle du carburant déplace par ``mw`` de solaire raccordé.

    Le solaire ne remplace pas de la capacité ferme: il remplace du carburant, aux
    heures ou il produit. ``hours_available`` est le nombre d'heures equivalentes
    pleine puissance par jour au site retenu.
    """
    from malinergy.analysis import solar as solar_analysis

    yield_kwh_per_kw = solar_analysis.specific_yield(registry, site)
    annual_kwh = mw * 1000.0 * yield_kwh_per_kw

    # Le solaire deplace le haut de pile en journee: on se place a la demande de
    # jour, solaire exclu, pour identifier l'unite marginale reellement evincee.
    day_demand = registry.value("sector", "aggregates", "peak_demand_mw") * 0.9
    displaced_cost = marginal_cost(registry, day_demand, solar_available=False)

    ppa = None
    for plant in registry["generation"]["plants"]:
        if plant["type"] == "solar_pv":
            ppa = float(plant["ppa_xof_per_kwh"])
            break
    ppa = ppa if ppa is not None else 0.0

    return {
        "installed_mw": mw,
        "annual_kwh": annual_kwh,
        "equivalent_full_load_hours": hours_available * 365,
        "displaced_cost_xof_per_kwh": displaced_cost,
        "ppa_xof_per_kwh": ppa,
        "net_saving_xof_per_kwh": displaced_cost - ppa,
        "annual_saving_xof": annual_kwh * (displaced_cost - ppa),
        "note": (
            "Économie de carburant uniquement. Sans stockage, cette capacité ne "
            "réduit pas le délestage du soir."
        ),
    }


def loss_reduction_value(registry: Registry, points: float = 1.0) -> dict[str, float]:
    """Valeur d'un point de pertes réseau récupère.

    Un kWh non perdu est un kWh qu'il n'a pas fallu produire au coût marginal, et
    qui est en plus facture. C'est le seul levier du secteur dont le rendement est
    immédiat et qui ne demande aucune capacité nouvelle.
    """
    generation_kwh = registry.value("sector", "aggregates", "generation_gwh_year") * 1e6
    recovered_kwh = generation_kwh * points / 100.0

    marginal = marginal_cost(registry)
    from malinergy.analysis import tariff as tariff_analysis

    revenue = tariff_analysis.average_revenue_per_kwh(registry)
    collection = registry.value("sector", "aggregates", "collection_rate")

    return {
        "points": points,
        "recovered_kwh": recovered_kwh,
        "avoided_generation_xof": recovered_kwh * marginal,
        "additional_billed_revenue_xof": recovered_kwh * revenue * collection,
        "total_value_xof": recovered_kwh * (marginal + revenue * collection),
    }

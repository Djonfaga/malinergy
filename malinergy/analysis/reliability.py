"""Délestage: mesurer, dater, et chiffrer ce qu'il coûte.

Le délestage est traite ici comme une grandeur économique et non comme un incident.
Chaque kWh non fourni à un coût pour l'usager (production de secours, activite
perdue) qui excede de loin le coût de l'avoir produit. C'est ce rapport qui justifie
d'investir avant que la penurie ne soit résorbée par la seule croissance de l'offre.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from malinergy.datasets import Registry

DAYS_PER_MONTH = 30.4


@dataclass(frozen=True)
class YearStats:
    year: int
    shedding_hours_per_day: float
    unserved_gwh: float
    worst_month: str
    worst_month_hours: float


def series(registry: Registry) -> list[dict]:
    return registry["outages"]["series"]


def by_year(registry: Registry) -> list[YearStats]:
    grouped: dict[int, list[dict]] = {}
    for row in series(registry):
        grouped.setdefault(int(row["month"][:4]), []).append(row)

    stats = []
    for year, rows in sorted(grouped.items()):
        worst = max(rows, key=lambda r: r["shedding_hours_per_day"])
        stats.append(
            YearStats(
                year=year,
                shedding_hours_per_day=mean(r["shedding_hours_per_day"] for r in rows),
                unserved_gwh=sum(r["unserved_gwh"] for r in rows),
                worst_month=worst["month"],
                worst_month_hours=worst["shedding_hours_per_day"],
            )
        )
    return stats


def seasonality(registry: Registry) -> list[dict]:
    """Profil moyen par mois calendaire, tous millesimes confondus.

    Le pic de mars à juin combine l'étiage des fleuves — donc la baisse de
    l'hydroélectricité — et la pointe de climatisation. Les deux contraintes tombent
    au même moment: c'est la fenêtre que toute solution doit viser.
    """
    buckets: dict[int, list[dict]] = {}
    for row in series(registry):
        buckets.setdefault(int(row["month"][5:7]), []).append(row)
    profile = []
    for month, rows in sorted(buckets.items()):
        profile.append(
            {
                "month": month,
                "shedding_hours_per_day": mean(r["shedding_hours_per_day"] for r in rows),
                "avg_shed_mw": mean(r["avg_shed_mw"] for r in rows),
                "peak_demand_mw": mean(r["peak_demand_mw"] for r in rows),
            }
        )
    return profile


def critical_window(registry: Registry, threshold_share: float = 0.75) -> list[int]:
    """Mois où le délestage dépasse ``threshold_share`` du pire mois moyen."""
    profile = seasonality(registry)
    worst = max(p["shedding_hours_per_day"] for p in profile)
    return [
        p["month"] for p in profile if p["shedding_hours_per_day"] >= threshold_share * worst
    ]


def latest_twelve_months(registry: Registry) -> list[dict]:
    return series(registry)[-12:]


def unserved_energy(registry: Registry) -> dict[str, float]:
    """Énergie non distribuee sur douze mois glissants et son poids relatif."""
    window = latest_twelve_months(registry)
    ens_gwh = sum(r["unserved_gwh"] for r in window)
    sales_gwh = registry.value("sector", "aggregates", "sales_gwh_year")
    return {
        "unserved_gwh": ens_gwh,
        "sales_gwh": sales_gwh,
        "share_of_sales": ens_gwh / sales_gwh,
        "avg_shedding_hours_per_day": mean(r["shedding_hours_per_day"] for r in window),
        "peak_month": max(window, key=lambda r: r["unserved_gwh"])["month"],
    }


def cost_of_unreliability(registry: Registry) -> dict[str, float]:
    """Coût économique annuel du délestage, valorise au coût du kWh non fourni.

    La ventilation ménages / entreprises suit la structure des ventes: le délestage
    est applique par depart, il frappe donc les deux segments dans des proportions
    voisines de leur part de consommation.
    """
    ens = unserved_energy(registry)
    ens_kwh = ens["unserved_gwh"] * 1e6

    mix = {row["category"]: row["share_of_sales"] for row in registry["tariffs"]["sales_mix"]}
    household_share = mix.get("bt_social", 0) + mix.get("bt_domestique", 0)
    business_share = 1.0 - household_share

    voll_h = registry.value("sector", "value_of_lost_load", "menages_xof_per_kwh")
    voll_b = registry.value("sector", "value_of_lost_load", "entreprises_xof_per_kwh")

    cost_h = ens_kwh * household_share * voll_h
    cost_b = ens_kwh * business_share * voll_b
    return {
        "unserved_kwh": ens_kwh,
        "household_cost_xof": cost_h,
        "business_cost_xof": cost_b,
        "total_cost_xof": cost_h + cost_b,
        "average_voll_xof_per_kwh": (cost_h + cost_b) / ens_kwh if ens_kwh else 0.0,
    }


def backup_generation_cost(registry: Registry) -> dict[str, float]:
    """Ce que coûte l'autoproduction de secours qui se substitue au réseau.

    Un groupe electrogene privé consomme environ 0,32 litre de gasoil par kWh, hors
    amortissement et entretien. C'est la référence implicite de tout arbitrage fait
    par un abonné: tant que le réseau est indisponible, il paie ce prix-la.
    """
    gasoil = registry.value("sector", "fuel_prices", "gasoil_xof_per_litre")
    litres_per_kwh = 0.32
    fuel = gasoil * litres_per_kwh
    om_and_capital = 45.0  # amortissement + entretien d'un petit groupe, FCFA/kWh
    unit = fuel + om_and_capital

    ens = unserved_energy(registry)
    # Une partie seulement de l'energie non fournie est effectivement rattrapee par
    # un groupe de secours; le reste est de l'activite simplement perdue.
    substituted_share = 0.45
    return {
        "genset_cost_xof_per_kwh": unit,
        "fuel_component_xof_per_kwh": fuel,
        "substituted_share": substituted_share,
        "annual_private_fuel_spend_xof": ens["unserved_gwh"] * 1e6 * substituted_share * unit,
    }


def reliability_gap_vs_supply_cost(registry: Registry) -> dict[str, float]:
    """Rapport entre le coût de subir le délestage et celui de l'éviter.

    C'est le chiffre qui tranche le debat budgétaire: si éviter un kWh de délestage
    coûte moins cher que le subir, la dépense d'investissement est un gain net pour
    l'économie, même lorsqu'elle creuse le déficit d'EDM-SA à court terme.
    """
    from malinergy.analysis import dispatch

    cost = cost_of_unreliability(registry)
    marginal = dispatch.marginal_cost(registry)
    return {
        "cost_of_unserved_xof_per_kwh": cost["average_voll_xof_per_kwh"],
        "marginal_supply_cost_xof_per_kwh": marginal,
        "ratio": cost["average_voll_xof_per_kwh"] / marginal if marginal else 0.0,
    }

"""Ressource solaire: du GHI au kWh, puis du kWh au site à retenir.

L'irradiation est la variable la moins contraignante au Mali: elle varie d'environ
10 % entre Sikasso et Kidal, alors que le coût d'évacuation, lui, varie d'un facteur
dix. Le classement des sites croise donc ressource, proximite du réseau et charge
locale — dans cet ordre d'importance croissante.
"""

from __future__ import annotations

from dataclasses import dataclass

from malinergy.datasets import DataError, Registry

DAYS_PER_YEAR = 365.0
HOURS_PER_YEAR = 8760.0


def site(registry: Registry, site_id: str) -> dict:
    for entry in registry["solar"]["sites"]:
        if entry["id"] == site_id:
            return entry
    raise DataError(f"site solaire inconnu: {site_id}")


def performance_ratio(registry: Registry, site_id: str) -> float:
    """Ratio de performance corrige de l'empoussièrement au nord."""
    base = registry.value("solar", "pv_assumptions", "performance_ratio")
    if site(registry, site_id)["arid_north"]:
        base -= registry.value("solar", "pv_assumptions", "soiling_extra_loss_north")
    return base


def specific_yield(registry: Registry, site_id: str) -> float:
    """Productible annuel en kWh par kWc installe."""
    entry = site(registry, site_id)
    tilt = registry.value("solar", "pv_assumptions", "tilt_gain")
    return entry["ghi_kwh_m2_day"] * tilt * DAYS_PER_YEAR * performance_ratio(registry, site_id)


def capacity_factor(registry: Registry, site_id: str) -> float:
    return specific_yield(registry, site_id) / HOURS_PER_YEAR


@dataclass(frozen=True)
class SiteScore:
    id: str
    name: str
    region: str
    ghi: float
    specific_yield: float
    capacity_factor: float
    grid_km: float
    local_peak_mw: float
    interconnection_cost_xof_per_kw: float
    resource_score: float
    evacuation_score: float
    absorption_score: float
    score: float
    verdict: str


def interconnection_cost(registry: Registry, site_id: str) -> float:
    """Coût de raccordement par kW installe, fonction de la distance au réseau.

    Un site isolé n'est pas raccordable à un coût raisonnable: il relevé du système
    isolé, pas du réseau interconnecté, et son PV se compare au diesel local — un
    barreau bien plus haut. On le signale par un coût élevé plutôt que par une
    exclusion, pour que le classement reste lisible.
    """
    entry = site(registry, site_id)
    km = float(entry["grid_km"])
    if entry["grid_voltage"] == "isole":
        return 900000.0
        # Ligne d'evacuation ~ 45 MFCFA/km pour un parc de reference de 50 MW.
    return km * 45_000_000.0 / 50_000.0


def rank_sites(registry: Registry) -> list[SiteScore]:
    """Classe les sites sur trois critères explicites et ponderes.

    - *ressource* (poids 0,25): le productible, normalise sur la plage observee.
    - *évacuation* (poids 0,40): coût de raccordement, l'écart dominant.
    - *absorption* (poids 0,35): la charge locale capable d'absorber l'injection
      sans renforcement supplémentaire.
    """
    entries = registry["solar"]["sites"]
    yields_ = {e["id"]: specific_yield(registry, e["id"]) for e in entries}
    costs = {e["id"]: interconnection_cost(registry, e["id"]) for e in entries}
    peaks = {e["id"]: float(e["local_peak_mw"]) for e in entries}

    y_lo, y_hi = min(yields_.values()), max(yields_.values())
    c_lo, c_hi = min(costs.values()), max(costs.values())
    p_hi = max(peaks.values())

    scored = []
    for entry in entries:
        sid = entry["id"]
        resource = (yields_[sid] - y_lo) / (y_hi - y_lo) if y_hi > y_lo else 1.0
        evacuation = 1.0 - (costs[sid] - c_lo) / (c_hi - c_lo) if c_hi > c_lo else 1.0
        absorption = (peaks[sid] / p_hi) ** 0.5  # rendement decroissant de la taille
        score = 0.25 * resource + 0.40 * evacuation + 0.35 * absorption

        if entry["grid_voltage"] == "isole":
            verdict = "hybride PV-diesel-stockage en système isolé"
        elif entry["grid_km"] > 30 or entry["grid_voltage"] == "33 kV":
            # Une antenne 33 kV ne transporte pas un parc a l'echelle utile, quelle
            # que soit la qualite de la ressource: le raccordement est le prealable.
            verdict = "conditionné au renforcement de l'antenne"
        elif score >= 0.55:
            verdict = "priorité réseau interconnecté"
        else:
            verdict = "second rang"

        scored.append(
            SiteScore(
                id=sid,
                name=entry["name"],
                region=entry["region"],
                ghi=entry["ghi_kwh_m2_day"],
                specific_yield=yields_[sid],
                capacity_factor=capacity_factor(registry, sid),
                grid_km=float(entry["grid_km"]),
                local_peak_mw=peaks[sid],
                interconnection_cost_xof_per_kw=costs[sid],
                resource_score=resource,
                evacuation_score=evacuation,
                absorption_score=absorption,
                score=score,
                verdict=verdict,
            )
        )
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored


def resource_spread(registry: Registry) -> dict[str, float]:
    """Mesure l'écart de ressource entre le meilleur et le moins bon site.

    Sert à etayer un point contre-intuitif: au Mali, choisir un site pour son
    irradiation plutôt que pour son raccordement est une erreur d'un ordre de
    grandeur.
    """
    yields_ = {e["id"]: specific_yield(registry, e["id"]) for e in registry["solar"]["sites"]}
    costs = {
        e["id"]: interconnection_cost(registry, e["id"]) for e in registry["solar"]["sites"]
    }
    best, worst = max(yields_.values()), min(yields_.values())
    # Bamako est a 0 km du reseau: on prend le plus petit cout strictement positif
    # pour que le rapport reste interpretable.
    positive = [c for c in costs.values() if c > 0]
    floor = min(positive) if positive else 1.0
    return {
        "yield_spread_share": best / worst - 1.0,
        "interconnection_spread_ratio": max(costs.values()) / floor,
        "cheapest_interconnection_xof_per_kw": floor,
        "dearest_interconnection_xof_per_kw": max(costs.values()),
        "best_site": max(yields_, key=yields_.get),
        "worst_site": min(yields_, key=yields_.get),
    }

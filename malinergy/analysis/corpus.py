"""Corpus externe: ce que le reste du monde publie sur l'énergie au Mali.

Le Mali apparaît rarement comme sujet principal d'un jeu de données. Il est le
plus souvent une ligne dans une base mondiale — indicateurs de la Banque
mondiale, statistiques IRENA, suivi ODD 7, enquêtes entreprises, registres de
centrales. Ce module rassemble ces observations, mesure la couverture du corpus,
et surtout **confronte chaque observation publiée à la grandeur correspondante
calculée par Malinergy**.

La réconciliation est le point important. Une plateforme de connaissances qui se
contente d'empiler des chiffres accumule des contradictions sans le savoir. En
comparant systématiquement ses propres hypothèses aux valeurs publiées, elle
transforme chaque divergence en question explicite: laquelle des deux sources a
tort, et qu'est-ce que cela change aux conclusions.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from malinergy.datasets import DataError, Registry


@dataclass(frozen=True)
class Observation:
    id: str
    label: str
    value: float
    unit: str
    year: int
    scope: str
    source: str
    caveat: str = ""

    @property
    def is_mali(self) -> bool:
        return self.scope.startswith("Mali") or self.scope in ("Bamako", "OMVS")


@dataclass(frozen=True)
class Reconciliation:
    observation: str
    label: str
    published: float
    internal: float
    unit: str
    relative_gap: float
    tolerance: float
    source: str
    resolution: str = ""

    @property
    def agrees(self) -> bool:
        return abs(self.relative_gap) <= self.tolerance

    @property
    def verdict(self) -> str:
        if self.agrees:
            return "concordant"
        return "divergent"


def observations(registry: Registry) -> list[Observation]:
    return [
        Observation(
            id=o["id"],
            label=o["label"],
            value=float(o["value"]),
            unit=o["unit"],
            year=int(o["year"]),
            scope=o["scope"],
            source=o["source"],
            caveat=o.get("caveat", ""),
        )
        for o in registry["observations"]["observations"]
    ]


def observation(registry: Registry, obs_id: str) -> Observation:
    for obs in observations(registry):
        if obs.id == obs_id:
            return obs
    raise DataError(f"observation inconnue: {obs_id}")


def coverage(registry: Registry) -> dict:
    """Ce que le corpus couvre, et par quelle qualité de source."""
    obs = observations(registry)
    by_source = Counter(o.source for o in obs)
    by_confidence = Counter(registry.source(o.source).confidence for o in obs)
    by_scope = Counter(o.scope for o in obs)
    years = [o.year for o in obs]
    return {
        "count": len(obs),
        "distinct_sources": len(by_source),
        "by_confidence": dict(by_confidence),
        "by_scope": dict(by_scope),
        "year_span": (min(years), max(years)),
        "comparators": sorted({o.scope for o in obs if not o.is_mali}),
        "reconcilable": sum(
            1 for o in registry["observations"]["observations"] if "reconcile" in o
        ),
    }


# ------------------------------------------------------- grandeurs comparables


def _computed_metric(registry: Registry, metric: str) -> float:
    from malinergy.analysis import dispatch, tariff

    if metric == "average_revenue_per_kwh":
        return tariff.average_revenue_per_kwh(registry)
    if metric == "annual_subsidy_xof":
        return tariff.cost_of_supply(registry)["annual_subsidy_xof"]
    if metric == "mt_price":
        # Prix moyen toutes taxes comprises d'un client moyenne tension, base de
        # comparaison des relevés de prix internationaux.
        bill = tariff.bill(registry, "mt_industriel", 120000.0)
        return bill.total / bill.kwh
    if metric == "total_installed_mw":
        plants = registry["generation"]["plants"]
        mines = registry["mines"]["sites"]
        grid = sum(float(p["capacity_mw"]) for p in plants if p["type"] != "import")
        captive = sum(
            float(m["thermal_mw"]) + float(m["solar_mw"])
            for m in mines
            if int(m["commissioned"]) <= 2026
        )
        return grid + captive
    if metric == "generation_gwh":
        return registry.value("sector", "aggregates", "generation_gwh_year")
    if metric == "marginal_cost":
        return dispatch.marginal_cost(registry)
    raise DataError(f"grandeur calculée inconnue: {metric}")


def _internal_value(registry: Registry, spec: dict) -> float:
    kind = spec["kind"]
    if kind == "dataset":
        return registry.value(spec["dataset"], *spec["path"])
    if kind == "computed":
        return _computed_metric(registry, spec["metric"])
    if kind == "plant":
        for plant in registry["generation"]["plants"]:
            if plant["id"] == spec["plant"]:
                return float(plant[spec["field"]])
        raise DataError(f"centrale inconnue: {spec['plant']}")
    if kind == "plant_energy":
        for plant in registry["generation"]["plants"]:
            if plant["id"] == spec["plant"]:
                mali_gwh = (
                    float(plant["capacity_mw"])
                    * float(plant["capacity_factor"])
                    * 8760.0
                    / 1000.0
                )
                # L'observation porte sur l'ouvrage entier: on remonte à 100 %.
                return mali_gwh / float(spec["divide_by_share"])
        raise DataError(f"centrale inconnue: {spec['plant']}")
    raise DataError(f"type de réconciliation inconnu: {kind}")


def reconcile(registry: Registry) -> list[Reconciliation]:
    """Confronte chaque observation réconciliable à la grandeur interne."""
    results = []
    for raw in registry["observations"]["observations"]:
        spec = raw.get("reconcile")
        if not spec:
            continue
        published = float(raw["value"]) * float(spec.get("scale", 1.0))
        internal = _internal_value(registry, spec)
        gap = (internal - published) / published if published else 0.0
        results.append(
            Reconciliation(
                observation=raw["id"],
                label=raw["label"],
                published=published,
                internal=internal,
                unit=raw["unit"],
                relative_gap=gap,
                tolerance=float(spec.get("tolerance", 0.10)),
                source=raw["source"],
                resolution=raw.get("resolution", ""),
            )
        )
    results.sort(key=lambda r: abs(r.relative_gap), reverse=True)
    return results


def divergences(registry: Registry) -> list[Reconciliation]:
    return [r for r in reconcile(registry) if not r.agrees]


def confirmations(registry: Registry) -> list[Reconciliation]:
    return [r for r in reconcile(registry) if r.agrees]


def reconciliation_score(registry: Registry) -> float:
    """Part des grandeurs internes confirmées par une source externe."""
    rows = reconcile(registry)
    return len([r for r in rows if r.agrees]) / len(rows) if rows else 0.0


# ---------------------------------------------------------------- comparaisons


def benchmark(registry: Registry, metric_prefix: str) -> list[dict]:
    """Compare le Mali à ses comparateurs pour une famille d'observations."""
    rows = [
        {
            "scope": o.scope,
            "value": o.value,
            "unit": o.unit,
            "year": o.year,
            "source": o.source,
        }
        for o in observations(registry)
        if o.id.startswith(metric_prefix)
    ]
    mali = next((r for r in rows if r["scope"] == "Mali"), None)
    for row in rows:
        row["ratio_to_mali"] = row["value"] / mali["value"] if mali and mali["value"] else None
    rows.sort(key=lambda r: r["value"])
    return rows


def energy_poverty_gap(registry: Registry) -> dict:
    """Écart de consommation par habitant entre le Mali et ses comparateurs.

    Cette grandeur situe l'ambition: rejoindre la moyenne africaine ne demande
    pas un ajustement mais une multiplication de la consommation par plus de
    cinq, à population constante.
    """
    rows = benchmark(registry, "conso_par_habitant")
    mali = next(r for r in rows if r["scope"] == "Mali")
    out = {"mali_kwh_per_capita": mali["value"], "comparators": {}}
    for row in rows:
        if row["scope"] == "Mali":
            continue
        out["comparators"][row["scope"]] = {
            "kwh_per_capita": row["value"],
            "multiple": row["value"] / mali["value"],
        }
    return out


def tariff_inequity(registry: Registry) -> dict:
    """Ce que paie un ménage selon qu'il est raccordé au réseau ou non.

    La subvention publique porte sur le kWh vendu par EDM-SA. Un ménage rural
    desservi par un mini-réseau n'en reçoit rien et paie plusieurs fois le tarif
    d'un abonné de Bamako. C'est le constat le plus direct que le corpus externe
    ajoute au reste de la plateforme.
    """
    from malinergy.analysis import tariff

    grid_bill = tariff.bill(registry, "bt_domestique", 100.0)
    grid_price = grid_bill.average_price
    social_price = tariff.bill(registry, "bt_social", 40.0).average_price
    mini_grid = observation(registry, "minireseau_tarif_tout_compris").value
    households = observation(registry, "minireseaux_menages").value
    costs = tariff.cost_of_supply(registry)

    return {
        "grid_household_xof_per_kwh": grid_price,
        "social_tranche_xof_per_kwh": social_price,
        "mini_grid_xof_per_kwh": mini_grid,
        "ratio_mini_grid_to_grid": mini_grid / grid_price,
        "ratio_mini_grid_to_social": mini_grid / social_price,
        "mini_grid_households": households,
        "subsidy_per_kwh_to_grid_customers": costs["subsidy_xof_per_kwh"],
        "note": (
            "Le ménage le moins bien servi paie le prix le plus élevé et ne reçoit "
            "aucune subvention. Toute réforme du tarif qui ignore cette asymétrie "
            "protège les mieux raccordés au nom des plus pauvres."
        ),
    }


def captive_capacity(registry: Registry) -> dict:
    """Autoproduction minière: taille, mix, et ce qu'elle démontre.

    Les mines ont fait, sur fonds privés et sans subvention, l'arbitrage que le
    secteur public discute encore: remplacer du fioul importé par du solaire avec
    stockage. Leur parc est de l'ordre de grandeur de la capacité thermique
    d'EDM-SA.
    """
    sites = [m for m in registry["mines"]["sites"] if int(m["commissioned"]) <= 2026]
    planned = [m for m in registry["mines"]["sites"] if int(m["commissioned"]) > 2026]
    thermal = sum(float(m["thermal_mw"]) for m in sites)
    solar = sum(float(m["solar_mw"]) for m in sites)
    storage = sum(float(m["storage_mw"]) for m in sites)
    fuel_saved = sum(float(m["fuel_saved_litres_year"] or 0) for m in sites)

    edm_thermal = sum(
        float(p["capacity_mw"])
        for p in registry["generation"]["plants"]
        if p["type"] in ("thermal_hfo", "thermal_rental", "thermal_isolated")
    )
    gasoil = registry.value("sector", "fuel_prices", "gasoil_xof_per_litre")

    return {
        "operating_thermal_mw": thermal,
        "operating_solar_mw": solar,
        "operating_storage_mw": storage,
        "total_operating_mw": thermal + solar + storage,
        "planned_solar_mw": sum(float(m["solar_mw"]) for m in planned),
        "solar_share": solar / (thermal + solar) if (thermal + solar) else 0.0,
        "edm_thermal_mw": edm_thermal,
        "ratio_to_edm_thermal": (thermal + solar) / edm_thermal if edm_thermal else 0.0,
        "documented_fuel_saved_litres_year": fuel_saved,
        "documented_fuel_saving_xof_year": fuel_saved * gasoil,
    }


def fuel_security(registry: Registry) -> dict:
    """Exposition du parc thermique à la rupture d'approvisionnement en carburant.

    Le blocus des convois entamé en septembre 2025 transforme une question de
    coût en question de disponibilité: un parc qui dépend du carburant acheminé
    par route depuis Dakar ou Abidjan n'est pas seulement cher, il est
    interruptible par un tiers.
    """
    from malinergy.analysis import dispatch

    plants = registry["generation"]["plants"]
    fuel_dependent = [
        p for p in plants if p["type"] in ("thermal_hfo", "thermal_rental", "thermal_isolated")
    ]
    fuel_mw = sum(float(p["capacity_mw"]) * float(p["availability"]) for p in fuel_dependent)
    balance = dispatch.capacity_balance(registry)
    trucks = observation(registry, "blocus_camions_detruits").value
    price_surge = observation(registry, "blocus_hausse_prix").value

    return {
        "fuel_dependent_mw": fuel_mw,
        "share_of_firm_capacity": fuel_mw / balance["available_firm_mw"],
        "trucks_destroyed": trucks,
        "parallel_market_price_surge_pct": price_surge,
        "note": (
            "La part du parc qui dépend d'un convoi routier est aussi la part "
            "qu'un blocus peut arrêter. Le solaire et l'hydraulique n'ont pas "
            "cette exposition: leur intrant ne traverse pas de route."
        ),
    }

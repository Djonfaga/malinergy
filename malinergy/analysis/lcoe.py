"""Coût complet actualisé de l'énergie (LCOE) et coût évité.

Le LCOE repond à une seule question: *pour un kWh livre pendant toute la durée de
vie de l'ouvrage, combien coûte chaque technologie, capital compris?* Il ne dit
rien de la valeur du kWh au moment ou il est produit — c'est le role du module
:mod:`malinergy.analysis.dispatch`. Les deux se lisent ensemble.
"""

from __future__ import annotations

from dataclasses import dataclass

from malinergy.analysis import solar as solar_analysis
from malinergy.datasets import DataError, Registry

HOURS_PER_YEAR = 8760.0


def capital_recovery_factor(rate: float, years: int) -> float:
    """Annuité constante amortissant 1 FCFA de capital sur ``years`` années."""
    if years <= 0:
        raise ValueError("la durée de vie doit être positive")
    if rate == 0:
        return 1.0 / years
    return rate * (1 + rate) ** years / ((1 + rate) ** years - 1)


@dataclass(frozen=True)
class Lcoe:
    id: str
    name: str
    technology: str
    capacity_factor: float
    capital_component: float
    fixed_opex_component: float
    fuel_component: float
    lead_time_months: int
    source: str

    @property
    def total(self) -> float:
        return self.capital_component + self.fixed_opex_component + self.fuel_component

    @property
    def fuel_share(self) -> float:
        return self.fuel_component / self.total if self.total else 0.0

    @property
    def is_import_exposed(self) -> bool:
        """Le coût depend-il d'un intrant importé payé en devises?"""
        return self.fuel_share > 0.25


def candidate(registry: Registry, candidate_id: str) -> dict:
    for entry in registry["generation"]["candidates"]:
        if entry["id"] == candidate_id:
            return entry
    raise DataError(f"technologie candidate inconnue: {candidate_id}")


def compute(
    registry: Registry,
    candidate_id: str,
    *,
    site: str = "bamako",
    capacity_factor: float | None = None,
) -> Lcoe:
    """LCOE d'une technologie candidate, en FCFA/kWh."""
    spec = candidate(registry, candidate_id)
    if spec["type"] == "efficiency":
        raise DataError(
            "la maitrise des pertes ne produit pas de kWh: son économie se calculé "
            "dans malinergy.analysis.dispatch, pas en LCOE"
        )

    cf = capacity_factor if capacity_factor is not None else spec.get("capacity_factor")
    if cf is None:
        cf = solar_analysis.capacity_factor(registry, site)
        if spec["type"] == "solar_bess":
            # Le stockage restitue une partie de l'energie: pertes de cycle sur la
            # fraction stockee, mais facteur de charge exprime sur la meme puissance
            # de raccordement.
            cf *= 0.94
    if not 0 < cf <= 1:
        raise DataError(f"facteur de charge invalide pour {candidate_id}: {cf}")

    rate = registry.value("sector", "finance", spec["wacc_key"])
    years = int(spec["lifetime_years"])
    crf = capital_recovery_factor(rate, years)

    annual_kwh_per_kw = cf * HOURS_PER_YEAR
    capital = float(spec["capex_xof_per_kw"]) * crf / annual_kwh_per_kw
    fixed = float(spec["opex_xof_per_kw_year"]) / annual_kwh_per_kw
    fuel = float(spec["fuel_cost_xof_per_kwh"])

    return Lcoe(
        id=candidate_id,
        name=spec["name"],
        technology=spec["type"],
        capacity_factor=cf,
        capital_component=capital,
        fixed_opex_component=fixed,
        fuel_component=fuel,
        lead_time_months=int(spec["lead_time_months"]),
        source=spec["source"],
    )


def ranking(registry: Registry, *, site: str = "bamako") -> list[Lcoe]:
    """Classement des technologies candidates par coût croissant."""
    results = []
    for spec in registry["generation"]["candidates"]:
        if spec["type"] == "efficiency":
            continue
        results.append(compute(registry, spec["id"], site=site))
    results.sort(key=lambda r: r.total)
    return results


def sensitivity(registry: Registry, candidate_id: str, *, site: str = "bamako") -> dict:
    """Sensibilité du LCOE aux deux variables reellement incertaines au Mali.

    Le coût du capital (donc la solvabilité de l'acheteur) et le prix du carburant
    importé expliquent l'essentiel de la dispersion. Les faire varier montre lequel
    des deux leviers mérite l'effort de réforme.
    """
    spec = candidate(registry, candidate_id)
    base = compute(registry, candidate_id, site=site)
    base_rate = registry.value("sector", "finance", spec["wacc_key"])

    wacc_rows = []
    for delta in (-0.03, 0.0, 0.03, 0.06):
        rate = max(0.01, base_rate + delta)
        crf = capital_recovery_factor(rate, int(spec["lifetime_years"]))
        annual_kwh = base.capacity_factor * HOURS_PER_YEAR
        capital = float(spec["capex_xof_per_kw"]) * crf / annual_kwh
        wacc_rows.append(
            {"wacc": rate, "lcoe": capital + base.fixed_opex_component + base.fuel_component}
        )

    fuel_rows = []
    for factor in (0.7, 1.0, 1.3, 1.6):
        fuel_rows.append(
            {
                "fuel_factor": factor,
                "lcoe": base.capital_component
                + base.fixed_opex_component
                + base.fuel_component * factor,
            }
        )

    spread = lambda rows, key: max(r["lcoe"] for r in rows) - min(
        r["lcoe"] for r in rows
    )  # noqa: E731
    wacc_spread = spread(wacc_rows, "wacc")
    fuel_spread = spread(fuel_rows, "fuel_factor")
    return {
        "candidate": candidate_id,
        "base_lcoe": base.total,
        "wacc": wacc_rows,
        "fuel": fuel_rows,
        "dominant_driver": (
            "coût du capital" if wacc_spread >= fuel_spread else "prix du carburant"
        ),
        "wacc_spread": wacc_spread,
        "fuel_spread": fuel_spread,
    }


def avoided_cost(registry: Registry, candidate_id: str, *, site: str = "bamako") -> dict:
    """Écart entre le LCOE d'une option et le coût variable qu'elle déplace.

    La référence n'est pas le tarif — c'est le coût marginal du parc, c'est-a-dire
    le kWh thermique le plus cher effectivement appelé.
    """
    from malinergy.analysis import dispatch  # import tardif: dependance croisee

    marginal = dispatch.marginal_cost(registry)
    lc = compute(registry, candidate_id, site=site)
    return {
        "candidate": candidate_id,
        "lcoe_xof_per_kwh": lc.total,
        "marginal_cost_xof_per_kwh": marginal,
        "saving_xof_per_kwh": marginal - lc.total,
        "profitable": marginal > lc.total,
    }

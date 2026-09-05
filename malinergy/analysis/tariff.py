"""Tarifs EDM-SA: facture, vérité des coûts, subventions croisees.

Trois questions decisionnelles sont traitees ici:

1. *Combien paie reellement un abonné donne?* — la grille est progressive par
   palier, donc le prix moyen d'un ménage dépend fortement de son niveau de
   consommation.
2. *De combien le tarif s'ecarte-t-il du coût de fourniture?* — c'est l'écart qui
   se transforme mecaniquement en subvention budgétaire puis, quand elle n'est pas
   versee, en arriérés envers les fournisseurs.
3. *Qui capte la subvention?* — une subvention adossée au kWh se répartit comme la
   consommation, pas comme le besoin social.
"""

from __future__ import annotations

from dataclasses import dataclass

from malinergy.datasets import DataError, Registry


@dataclass(frozen=True)
class Bill:
    category: str
    kwh: float
    energy_charge: float
    fixed_charge: float
    vat: float

    @property
    def total(self) -> float:
        return self.energy_charge + self.fixed_charge + self.vat

    @property
    def average_price(self) -> float:
        """Prix moyen reellement payé, toutes composantes comprises."""
        return self.total / self.kwh if self.kwh else 0.0


def category(registry: Registry, category_id: str) -> dict:
    for entry in registry["tariffs"]["categories"]:
        if entry["id"] == category_id:
            return entry
    raise DataError(f"catégorie tarifaire inconnue: {category_id}")


def energy_charge(registry: Registry, category_id: str, kwh: float) -> float:
    """Facture d'énergie hors taxes, calculée palier par palier."""
    if kwh < 0:
        raise ValueError("la consommation ne peut pas être negative")
    cat = category(registry, category_id)
    total = 0.0
    for block in cat["blocks"]:
        lower = float(block["from_kwh"])
        upper = block["to_kwh"]
        if kwh <= lower:
            break
        span = kwh - lower if upper is None else min(kwh, float(upper)) - lower
        total += span * float(block["price"])
    return total


def bill(registry: Registry, category_id: str, kwh: float, demand_kw: float = 0.0) -> Bill:
    """Facture mensuelle complete: énergie, prime fixe, prime de puissance, TVA."""
    cat = category(registry, category_id)
    energy = energy_charge(registry, category_id, kwh)
    fixed = float(cat.get("fixed_charge_month", 0.0))
    fixed += float(cat.get("demand_charge_kw_month", 0.0)) * demand_kw

    exempt = category_id in registry["tariffs"].get("vat_exempt_categories", [])
    rate = 0.0 if exempt else float(registry["tariffs"]["vat_rate"])
    vat = (energy + fixed) * rate
    return Bill(category_id, kwh, energy, fixed, vat)


def average_revenue_per_kwh(registry: Registry) -> float:
    """Recette moyenne hors taxes par kWh vendu, ponderee par le mix de ventes.

    La TVA est exclue: elle transite vers l'État et n'entre pas dans l'équilibre
    d'exploitation d'EDM-SA.
    """
    total = 0.0
    for row in registry["tariffs"]["sales_mix"]:
        cat_id = row["category"]
        share = float(row["share_of_sales"])
        # Consommation de reference par categorie, choisie au milieu de la plage
        # ou la categorie est effectivement facturee.
        reference_kwh = _reference_consumption(registry, cat_id)
        b = bill(registry, cat_id, reference_kwh)
        total += share * (b.energy_charge + b.fixed_charge) / reference_kwh
    return total


def _reference_consumption(registry: Registry, category_id: str) -> float:
    """Consommation mensuelle representative servant à ponderer la grille."""
    reference = {
        "bt_social": 40.0,
        "bt_domestique": 165.0,
        "bt_professionnel": 900.0,
        "mt_industriel": 120000.0,
        "ep_bt": 4000.0,
        "ep_mt": 25000.0,
    }
    if category_id not in reference:
        raise DataError(f"pas de consommation de référence pour {category_id}")
    return reference[category_id]


def cost_of_supply(registry: Registry) -> dict[str, float]:
    """Decompose le coût moyen de fourniture par kWh vendu.

    Le coût est reconstruit par le bas — recette moyenne plus subvention par kWh —
    de sorte que la subvention publiée et la grille tarifaire restent les deux
    seules entrées exogènes.

    Deux niveaux de coût sont rendus, parce que deux sources mesurent deux choses
    différentes. La **subvention budgétaire** est la ligne votée, documentée par le
    FMI. La **ponction budgétaire totale** y ajoute les arriérés et les emprunts
    garantis auprès des banques régionales. L'écart entre les deux n'est pas une
    incertitude: c'est la part du déficit du secteur qui échappe au budget voté.
    """
    sales_kwh = registry.value("sector", "aggregates", "sales_gwh_year") * 1e6
    subsidy_xof = registry.value("sector", "aggregates", "state_subsidy_xof_year")
    drain_xof = registry.value(
        "sector", "aggregates", "fiscal_drain_usd_year"
    ) * registry.value("sector", "fx", "xof_per_usd")
    revenue = average_revenue_per_kwh(registry)
    subsidy_per_kwh = subsidy_xof / sales_kwh
    drain_per_kwh = drain_xof / sales_kwh
    return {
        "average_revenue_xof_per_kwh": revenue,
        "subsidy_xof_per_kwh": subsidy_per_kwh,
        "average_cost_xof_per_kwh": revenue + subsidy_per_kwh,
        "cost_recovery_ratio": revenue / (revenue + subsidy_per_kwh),
        "annual_subsidy_xof": subsidy_xof,
        "annual_fiscal_drain_xof": drain_xof,
        "drain_xof_per_kwh": drain_per_kwh,
        "off_budget_xof": drain_xof - subsidy_xof,
        "full_cost_xof_per_kwh": revenue + drain_per_kwh,
        "sales_kwh": sales_kwh,
    }


def subsidy_incidence(registry: Registry) -> list[dict]:
    """Répartition de la subvention entre catégories.

    Une subvention adossée au kWh suit la consommation. Le tableau confronte la
    part de subvention captee à la part de clients concernes: l'écart mesure à quel
    point l'instrument manque sa cible sociale.
    """
    costs = cost_of_supply(registry)
    rows = []
    for row in registry["tariffs"]["sales_mix"]:
        cat_id = row["category"]
        cat = category(registry, cat_id)
        share = float(row["share_of_sales"])
        kwh = share * costs["sales_kwh"]
        reference_kwh = _reference_consumption(registry, cat_id)
        b = bill(registry, cat_id, reference_kwh)
        unit_revenue = (b.energy_charge + b.fixed_charge) / reference_kwh
        gap = costs["average_cost_xof_per_kwh"] - unit_revenue
        rows.append(
            {
                "category": cat_id,
                "label": cat["label"],
                "segment": cat["segment"],
                "share_of_sales": share,
                "customers_share": float(row["customers_share"]),
                "unit_revenue_xof_per_kwh": unit_revenue,
                "unit_gap_xof_per_kwh": gap,
                "annual_subsidy_xof": gap * kwh,
                "share_of_subsidy": 0.0,
            }
        )
    total = sum(r["annual_subsidy_xof"] for r in rows)
    for r in rows:
        r["share_of_subsidy"] = r["annual_subsidy_xof"] / total if total else 0.0
    rows.sort(key=lambda r: r["annual_subsidy_xof"], reverse=True)
    return rows


def targeting_efficiency(registry: Registry) -> dict[str, float]:
    """Part de la subvention qui atteint les ménages, et concentration du reste."""
    rows = subsidy_incidence(registry)
    to_households = sum(r["share_of_subsidy"] for r in rows if r["segment"] == "menages")
    to_social = sum(r["share_of_subsidy"] for r in rows if r["category"] == "bt_social")
    social_customers = sum(r["customers_share"] for r in rows if r["category"] == "bt_social")
    return {
        "share_to_households": to_households,
        "share_to_social_tranche": to_social,
        "social_customers_share": social_customers,
        "targeting_ratio": (to_social / social_customers) if social_customers else 0.0,
    }


def bill_ladder(registry: Registry, category_id: str = "bt_domestique") -> list[dict]:
    """Facture et prix moyen le long de l'échelle de consommation."""
    ladder = []
    for kwh in (25, 50, 75, 100, 150, 200, 300, 500, 1000):
        b = bill(registry, category_id, float(kwh))
        ladder.append(
            {
                "kwh": kwh,
                "total_xof": b.total,
                "average_price_xof_per_kwh": b.average_price,
            }
        )
    return ladder

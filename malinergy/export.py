"""Export JSON: alimenter le site à partir des mêmes calculs que le rapport.

Le site ne contient aucun chiffre en dur. Il lit les fichiers produits ici, ce qui
garantit qu'une correction dans ``malinergy/data`` se propage à la page publiée sans
edition manuelle — et qu'aucune donnée affichee ne circule sans sa source.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from malinergy import __version__
from malinergy.analysis import (
    corpus,
    decisions,
    dispatch,
    lcoe,
    reforms,
    reliability,
    solar,
    tariff,
)
from malinergy.datasets import Registry

DEFAULT_OUT = Path("public/data")


def _plain(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _plain(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    if isinstance(obj, float) and obj != obj:  # NaN
        return None
    return obj


def headline_metrics(registry: Registry) -> list[dict]:
    """Les quatre chiffres de tete du site, chacun avec sa source."""
    costs = tariff.cost_of_supply(registry)
    ens = reliability.unserved_energy(registry)
    balance = dispatch.capacity_balance(registry)
    access = registry.scalar("sector", "aggregates", "access_rate_national")
    losses = registry.scalar("sector", "aggregates", "network_losses_share")

    return [
        {
            "id": "cost_gap",
            "label": "Écart coût-tarif",
            "value": f"{costs['subsidy_xof_per_kwh']:.0f}",
            "unit": "FCFA/kWh",
            "detail": f"{costs['annual_subsidy_xof'] / 1e9:.0f} Md FCFA par an à la charge du budget",
            "source": registry.source("wb-mali-esrap").cite(),
            "confidence": "haute",
        },
        {
            "id": "firm_margin",
            "label": "Marge de puissance ferme",
            "value": f"{balance['firm_margin_mw']:+.0f}",
            "unit": "MW à la pointe du soir",
            "detail": f"{balance['available_firm_mw']:.0f} MW disponibles pour {balance['peak_demand_mw']:.0f} MW appelés",
            "source": registry.source("malinergy-estimation").cite(),
            "confidence": "faible",
        },
        {
            "id": "unserved",
            "label": "Énergie non fournie",
            "value": f"{ens['unserved_gwh']:.0f}",
            "unit": "GWh sur douze mois",
            "detail": f"{ens['share_of_sales']:.1%} des ventes, {ens['avg_shedding_hours_per_day']:.1f} h de délestage par jour",
            "source": registry.source("malinergy-estimation").cite(),
            "confidence": "faible",
        },
        {
            "id": "access",
            "label": "Accès à l'électricité",
            "value": f"{access.value:.0%}",
            "unit": "de la population",
            "detail": f"pertes réseau {losses.value:.1%}",
            "source": registry.source(access.source).cite(),
            "confidence": access.confidence,
        },
    ]


def build_payloads(registry: Registry) -> dict[str, Any]:
    """Tous les documents exportes, indexes par nom de fichier."""
    return {
        "metrics": {
            "snapshot": registry["sector"]["snapshot"],
            "metrics": headline_metrics(registry),
        },
        "tariffs": {
            "cost_of_supply": tariff.cost_of_supply(registry),
            "bill_ladder": tariff.bill_ladder(registry),
            "subsidy_incidence": tariff.subsidy_incidence(registry),
            "targeting": tariff.targeting_efficiency(registry),
        },
        "supply": {
            "balance": dispatch.capacity_balance(registry),
            "merit_order": _plain(dispatch.merit_order(registry, solar_available=False)),
            "fuel_bill": dispatch.annual_fuel_bill(registry),
            "lcoe": _plain(
                [
                    {**_plain(r), "total": r.total, "fuel_share": r.fuel_share}
                    for r in lcoe.ranking(registry, site="segou")
                ]
            ),
        },
        "solar": {
            "sites": _plain(solar.rank_sites(registry)),
            "spread": solar.resource_spread(registry),
            "assumptions": registry["solar"]["pv_assumptions"],
        },
        "outages": {
            "series": reliability.series(registry),
            "by_year": _plain(reliability.by_year(registry)),
            "seasonality": reliability.seasonality(registry),
            "critical_window": reliability.critical_window(registry),
            "cost": reliability.cost_of_unreliability(registry),
            "caveat": registry["outages"]["note"],
        },
        "grid": {
            "nodes": registry["grid"]["nodes"],
            "lines": registry["grid"]["lines"],
            "constraints": registry["grid"]["constraints"],
        },
        "reforms": {
            "timeline": reforms.timeline(registry),
            "cadence": reforms.cadence(registry),
            "gaps": _plain(reforms.gaps(registry)),
            "critical_path": reforms.critical_path(registry),
            "completion_index": reforms.completion_index(registry),
            "lessons": reforms.lessons(registry),
        },
        "decisions": {
            "findings": decisions.headline_findings(registry),
            "options": [
                {
                    **_plain(o),
                    "risk_adjusted_benefit": o.risk_adjusted_benefit,
                    "payback_years": o.payback_years,
                    "category": o.category,
                }
                for o in decisions.portfolio(registry)
            ],
            "plan": decisions.sequenced_plan(registry),
        },
        "corpus": {
            "coverage": corpus.coverage(registry),
            "observations": _plain(corpus.observations(registry)),
            "reconciliation": [
                {**_plain(r), "agrees": r.agrees, "verdict": r.verdict}
                for r in corpus.reconcile(registry)
            ],
            "score": corpus.reconciliation_score(registry),
            "energy_poverty_gap": corpus.energy_poverty_gap(registry),
            "tariff_inequity": corpus.tariff_inequity(registry),
            "captive_capacity": corpus.captive_capacity(registry),
            "fuel_security": corpus.fuel_security(registry),
        },
        "sources": {
            "sources": registry["sources"]["sources"],
            "summary": registry.provenance_summary(),
        },
    }


def write(registry: Registry, out_dir: Path | str = DEFAULT_OUT) -> list[Path]:
    """Ecrit les documents JSON et retourne la liste des fichiers produits."""
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    payloads = build_payloads(registry)
    for name, payload in payloads.items():
        document = {
            "generated_by": f"malinergy {__version__}",
            "snapshot": registry["sector"]["snapshot"],
            "data": _plain(payload),
        }
        path = directory / f"{name}.json"
        path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        written.append(path)
    return written

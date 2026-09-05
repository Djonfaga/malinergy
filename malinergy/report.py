"""Restitution: le rapport de décision en Markdown.

Le rapport suit l'ordre dans lequel un décideur à besoin des elements: d'abord ce
que les données imposent, ensuite d'ou vient chaque chiffre, enfin ce qu'il reste
a arbitrer.
"""

from __future__ import annotations

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

RISK_LABEL = {"faible": "faible", "moyen": "moyen", "eleve": "élevé"}

MONTHS = [
    "",
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
]


def _md(value: float, unit: str = "Md FCFA") -> str:
    return f"{value / 1e9:,.1f} {unit}".replace(",", " ")


def _table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(out)


def section_findings(registry: Registry) -> str:
    lines = ["## Ce que les données imposent", ""]
    for i, finding in enumerate(decisions.headline_findings(registry), start=1):
        lines.append(f"{i}. {finding}")
        lines.append("")
    return "\n".join(lines)


def section_tariff(registry: Registry) -> str:
    costs = tariff.cost_of_supply(registry)
    incidence = tariff.subsidy_incidence(registry)
    eff = tariff.targeting_efficiency(registry)

    rows = [
        [
            r["label"],
            f"{r['share_of_sales']:.0%}",
            f"{r['customers_share']:.0%}",
            f"{r['unit_revenue_xof_per_kwh']:.0f}",
            f"{r['unit_gap_xof_per_kwh']:.0f}",
            f"{r['share_of_subsidy']:.0%}",
        ]
        for r in incidence
    ]
    ladder = tariff.bill_ladder(registry)
    ladder_rows = [
        [
            f"{r['kwh']}",
            f"{r['total_xof']:,.0f}".replace(",", " "),
            f"{r['average_price_xof_per_kwh']:.0f}",
        ]
        for r in ladder
    ]

    return "\n".join(
        [
            "## Tarifs, coûts et subventions",
            "",
            f"- Recette moyenne hors taxes : **{costs['average_revenue_xof_per_kwh']:.0f} FCFA/kWh**",
            f"- Coût moyen de fourniture : **{costs['average_cost_xof_per_kwh']:.0f} FCFA/kWh**",
            f"- Écart couvert par le budget : **{costs['subsidy_xof_per_kwh']:.0f} FCFA/kWh**, "
            f"soit {_md(costs['annual_subsidy_xof'])} par an",
            f"- Taux de couverture des coûts : **{costs['cost_recovery_ratio']:.0%}**",
            "",
            "### Facture d'un abonné domestique",
            "",
            "La grille est progressive par palier: le prix moyen payé dépend fortement du "
            "niveau de consommation, ce qui rend trompeuse toute comparaison fondée sur un "
            "tarif unique.",
            "",
            _table(["kWh/mois", "Facture (FCFA)", "Prix moyen (FCFA/kWh)"], ladder_rows),
            "",
            "### Qui capte la subvention",
            "",
            _table(
                [
                    "Catégorie",
                    "Part des ventes",
                    "Part des abonnés",
                    "Recette (FCFA/kWh)",
                    "Écart au coût",
                    "Part de la subvention",
                ],
                rows,
            ),
            "",
            f"La tranche sociale représente {eff['social_customers_share']:.0%} des abonnés et "
            f"capte {eff['share_to_social_tranche']:.0%} de la subvention. Une aide adossée au kWh "
            "se répartit comme la consommation, donc à l'inverse du besoin social.",
            "",
        ]
    )


def section_supply(registry: Registry) -> str:
    balance = dispatch.capacity_balance(registry)
    stack = dispatch.merit_order(registry, solar_available=False)
    bill_ = dispatch.annual_fuel_bill(registry)

    rows = [
        [
            e.name,
            e.technology,
            f"{e.available_mw:.0f}",
            f"{e.cumulative_mw:.0f}",
            f"{e.variable_cost_xof_per_kwh:.0f}",
        ]
        for e in stack
    ]
    return "\n".join(
        [
            "## Offre: ordre de mérite et équilibre de puissance",
            "",
            "L'empilement ci-dessous est calculé à la pointe du soir, solaire absent. C'est "
            "l'état de réseau qui dimensionne le système et qui fixe la valeur économique d'un "
            "kWh économisé.",
            "",
            _table(
                [
                    "Moyen",
                    "Filière",
                    "Disponible (MW)",
                    "Cumul (MW)",
                    "Coût variable (FCFA/kWh)",
                ],
                rows,
            ),
            "",
            f"- Pointe appelée : **{balance['peak_demand_mw']:.0f} MW**",
            f"- Puissance ferme disponible le soir : **{balance['available_firm_mw']:.0f} MW** "
            f"(marge : {balance['firm_margin_mw']:+.0f} MW)",
            f"- Demande latente, délestage compris : **{balance['latent_peak_mw']:.0f} MW** "
            f"(déficit ferme : {balance['latent_firm_gap_mw']:.0f} MW)",
            f"- Coût moyen de production : **{bill_['average_generation_cost_xof_per_kwh']:.0f} FCFA/kWh**, "
            f"soit {_md(bill_['total_xof'])} par an",
            "",
            "Le déficit est un déficit de **puissance ferme**, pas d'énergie. Toute solution qui "
            "n'ajoute pas de capacité disponible après le coucher du soleil laisse le délestage "
            "du soir inchangé, quel que soit le volume d'énergie qu'elle produit.",
            "",
        ]
    )


def section_solar(registry: Registry) -> str:
    ranking = solar.rank_sites(registry)
    spread = solar.resource_spread(registry)
    rows = [
        [
            s.name,
            f"{s.ghi:.2f}",
            f"{s.specific_yield:,.0f}".replace(",", " "),
            f"{s.capacity_factor:.1%}",
            "isole" if s.grid_km > 500 else f"{s.grid_km:.0f}",
            f"{s.score:.2f}",
            s.verdict,
        ]
        for s in ranking
    ]
    return "\n".join(
        [
            "## Ressource solaire et choix des sites",
            "",
            _table(
                [
                    "Site",
                    "GHI (kWh/m2/j)",
                    "Productible (kWh/kWc/an)",
                    "Facteur de charge",
                    "Distance réseau (km)",
                    "Score",
                    "Orientation",
                ],
                rows,
            ),
            "",
            f"L'écart de productible entre le meilleur et le moins bon site est de "
            f"**{spread['yield_spread_share']:.0%}**. L'écart de coût de raccordement est d'un "
            f"facteur **{spread['interconnection_spread_ratio']:.0f}**. La ressource n'est donc pas "
            "le critère de sélection: le raccordement et la charge locale le sont.",
            "",
            "Corollaire opérationnel: les sites du nord, où l'irradiation est la meilleure, ne "
            "relèvent pas du réseau interconnecté mais de l'hybridation des systèmes isolés, où "
            "leur concurrent n'est pas le tarif mais un diesel à plus de 280 FCFA/kWh.",
            "",
        ]
    )


def section_reliability(registry: Registry) -> str:
    ens = reliability.unserved_energy(registry)
    cost = reliability.cost_of_unreliability(registry)
    ratio = reliability.reliability_gap_vs_supply_cost(registry)
    backup = reliability.backup_generation_cost(registry)
    window = reliability.critical_window(registry)
    years = reliability.by_year(registry)

    year_rows = [
        [
            str(y.year),
            f"{y.shedding_hours_per_day:.1f}",
            f"{y.unserved_gwh:.0f}",
            y.worst_month,
            f"{y.worst_month_hours:.1f}",
        ]
        for y in years
    ]
    return "\n".join(
        [
            "## Délestage: mesure et coût économique",
            "",
            _table(
                [
                    "Année",
                    "Heures/jour (moy.)",
                    "Énergie non fournie (GWh)",
                    "Pire mois",
                    "Heures/jour",
                ],
                year_rows,
            ),
            "",
            f"- Sur douze mois glissants : **{ens['unserved_gwh']:.0f} GWh** non fournis, "
            f"soit {ens['share_of_sales']:.1%} des ventes",
            f"- Coût pour l'économie : **{_md(cost['total_cost_xof'])}** par an "
            f"({_md(cost['business_cost_xof'])} pour les entreprises)",
            f"- Coût moyen d'un kWh non fourni : **{cost['average_voll_xof_per_kwh']:.0f} FCFA**, "
            f"soit **{ratio['ratio']:.1f} fois** le coût marginal de production",
            f"- Autoproduction de secours : **{backup['genset_cost_xof_per_kwh']:.0f} FCFA/kWh**, "
            f"soit environ {_md(backup['annual_private_fuel_spend_xof'])} de carburant privé par an",
            "",
            "Fenêtre critique : " + ", ".join(MONTHS[m] for m in window) + ". "
            "L'étiage des fleuves — donc la baisse de l'hydroélectricité — coïncide avec la pointe "
            "de climatisation. Les deux contraintes tombent au même moment: c'est cette fenêtre, "
            "et non la moyenne annuelle, que toute solution doit viser.",
            "",
        ]
    )


def section_lcoe(registry: Registry) -> str:
    ranking = lcoe.ranking(registry, site="segou")
    marginal = dispatch.marginal_cost(registry)
    rows = [
        [
            r.name,
            f"{r.capacity_factor:.0%}",
            f"{r.capital_component:.0f}",
            f"{r.fixed_opex_component:.0f}",
            f"{r.fuel_component:.0f}",
            f"**{r.total:.0f}**",
            f"{r.lead_time_months}",
        ]
        for r in ranking
    ]
    sens = lcoe.sensitivity(registry, "pv_utility", site="segou")
    return "\n".join(
        [
            "## Coût complet des options de production",
            "",
            _table(
                [
                    "Technologie",
                    "Facteur de charge",
                    "Capital",
                    "Exploitation",
                    "Combustible",
                    "LCOE (FCFA/kWh)",
                    "Délai (mois)",
                ],
                rows,
            ),
            "",
            f"Référence de comparaison: le coût marginal du parc à la pointe est de "
            f"**{marginal:.0f} FCFA/kWh**. Toute option dont le LCOE est inférieur à ce niveau "
            "dégage un gain net des sa mise en service.",
            "",
            f"Sensibilité du solaire raccordé: le facteur dominant est **{sens['dominant_driver']}** "
            f"(amplitude {sens['wacc_spread']:.0f} FCFA/kWh pour le capital contre "
            f"{sens['fuel_spread']:.0f} pour le carburant). Autrement dit, le prix du kWh solaire "
            "malien des vingt prochaines années se décide dans la solvabilité de l'acheteur, pas "
            "dans le choix du site ni dans la technologie des modules.",
            "",
        ]
    )


def section_reforms(registry: Registry) -> str:
    stats = reforms.cadence(registry)
    gaps = reforms.gaps(registry)
    path = reforms.critical_path(registry)
    labels = {c["id"]: c["label"] for c in registry["reforms"]["structural_conditions"]}

    gap_rows = [[g.label, g.status, str(g.leverage), g.why_it_matters] for g in gaps]
    return "\n".join(
        [
            "## Séquence des réformes: acquis, défaits, manquants",
            "",
            f"{stats['count']} décisions recensées entre {stats['span'][0]} et {stats['span'][1]}. "
            f"**{stats['reversal_rate']:.0%}** ont été annulées ou ont régressé — "
            + ", ".join(f"{e['title']} ({e['year']})" for e in stats["reversed"])
            + ".",
            "",
            "### Conditions structurelles non acquises",
            "",
            _table(["Condition", "Statut", "Levier", "Pourquoi elle compte"], gap_rows),
            "",
            "### Ordre de traitement",
            "",
            "Les dépendances imposent un ordre: une condition ne produit son effet qu'après "
            "celles dont elle dépend.",
            "",
            "\n".join(f"{i}. {labels.get(cid, cid)}" for i, cid in enumerate(path, start=1)),
            "",
            "\n\n".join(f"> {lesson}" for lesson in reforms.lessons(registry)),
            "",
        ]
    )


def section_decisions(registry: Registry) -> str:
    groups = decisions.by_category(registry)
    plan = decisions.sequenced_plan(registry)
    labels = {c["id"]: c["label"] for c in registry["reforms"]["structural_conditions"]}
    lines = ["## Que faire, dans quel ordre", ""]

    titles = {
        "sans regret": (
            "Sans regret",
            "Rentables, réalisables, sans prérequis de réforme non acquis.",
        ),
        "conditionnel": (
            "Conditionnel",
            "Le gain est réel mais suppose une condition structurelle aujourd'hui absente.",
        ),
        "a preparer": (
            "À préparer",
            "Le délai ou le retour sur investissement dépasse le cycle de la crise courante.",
        ),
    }
    for key, (title, blurb) in titles.items():
        options = groups[key]
        if not options:
            continue
        lines += [f"### {title}", "", blurb, ""]
        rows = []
        for o in options:
            payback = (
                "immediat"
                if o.payback_years == 0
                else ("n/a" if o.payback_years is None else f"{o.payback_years:.1f} ans")
            )
            blockers = ", ".join(labels.get(c, c) for c in o.blocking_conditions) or "—"
            rows.append(
                [
                    o.name,
                    _md(o.risk_adjusted_benefit),
                    _md(o.capex_xof),
                    payback,
                    f"{o.lead_time_months} mois",
                    RISK_LABEL.get(o.risk, o.risk),
                    blockers,
                ]
            )
        lines.append(
            _table(
                [
                    "Option",
                    "Gain annuel (ajusté du risque)",
                    "Investissement",
                    "Retour",
                    "Délai",
                    "Risque",
                    "Condition bloquante",
                ],
                rows,
            )
        )
        lines.append("")
        for o in options:
            lines.append(f"- **{o.name}** — {o.rationale}")
        lines.append("")

    lines += ["### Séquence", ""]
    for step in plan:
        lines += [
            f"**{step['horizon']}**",
            "",
            step["logic"],
            "",
            f"Gain annuel cumulé : {_md(step['annual_benefit_xof'])} — "
            f"investissement : {_md(step['capex_xof'])}.",
            "",
        ]
    return "\n".join(lines)


def section_provenance(registry: Registry) -> str:
    counts = registry.provenance_summary()
    total = sum(counts.values())
    rows = []
    for src in sorted(registry.sources.values(), key=lambda s: (s.confidence, s.year)):
        rows.append([src.id, src.publisher, str(src.year), src.confidence, src.kind])
    return "\n".join(
        [
            "## Provenance et limites",
            "",
            f"{total} références de source dans les jeux de données : "
            f"{counts['haute']} de confiance haute, {counts['moyenne']} moyenne, "
            f"{counts['faible']} faible.",
            "",
            _table(["Identifiant", "Éditeur", "Année", "Confiance", "Nature"], rows),
            "",
            "Les valeurs marquées `malinergy-estimation` sont des hypothèses de travail "
            "explicites, jamais des relevés officiels. Elles sont concentrées sur les agrégats "
            "d'exploitation d'EDM-SA, qui ne sont pas publiés de façon régulière, et sur la série "
            "de délestage, qui est une reconstruction. Chaque conclusion de ce rapport reste "
            "valable tant que l'ordre de grandeur de ces hypothèses tient; remplacer une valeur "
            "dans `malinergy/data` suffit à recalculer l'ensemble.",
            "",
        ]
    )


def section_corpus(registry: Registry) -> str:
    cov = corpus.coverage(registry)
    rec = corpus.reconcile(registry)
    diverging = corpus.divergences(registry)

    rows = [
        [
            r.label[:52],
            f"{r.published:,.2f}".replace(",", " "),
            f"{r.internal:,.2f}".replace(",", " "),
            f"{r.relative_gap:+.1%}",
            r.verdict,
            registry.source(r.source).publisher[:26],
        ]
        for r in rec
    ]
    lines = [
        "## Corpus externe et réconciliation",
        "",
        f"{cov['count']} observations publiées, issues de {cov['distinct_sources']} sources "
        f"distinctes, couvrant {cov['year_span'][0]} à {cov['year_span'][1]}. "
        f"{cov['by_confidence'].get('haute', 0)} proviennent de sources de confiance haute. "
        "Une partie vient de jeux de données mondiaux où le Mali n'est qu'une ligne parmi "
        "deux cents pays — indicateurs de la Banque mondiale, suivi ODD 7, enquêtes "
        "entreprises, registres régionaux de centrales.",
        "",
        f"Comparateurs disponibles : {', '.join(cov['comparators'])}.",
        "",
        "### Confrontation aux grandeurs calculées",
        "",
        "Chaque observation réconciliable est confrontée à la grandeur correspondante "
        "calculée par Malinergy. Une plateforme qui empile des chiffres sans les confronter "
        "accumule des contradictions sans le savoir.",
        "",
        _table(
            ["Grandeur", "Valeur publiée", "Valeur Malinergy", "Écart", "Verdict", "Source"],
            rows,
        ),
        "",
        f"**Taux de concordance : {corpus.reconciliation_score(registry):.0%}.**",
        "",
    ]
    resolved = [r for r in rec if r.resolution]
    if resolved:
        lines += ["### Ce que les divergences ont appris", ""]
        for r in resolved:
            lines.append(f"- **{r.label}** — {r.resolution}")
        lines.append("")
    if diverging:
        lines += [
            "Divergences non résolues : "
            + ", ".join(f"{d.label} ({d.relative_gap:+.0%})" for d in diverging)
            + ". Elles restent affichées plutôt que corrigées: une divergence signalée est "
            "une question ouverte, une divergence lissée est une erreur cachée.",
            "",
        ]
    return "\n".join(lines)


def section_comparison(registry: Registry) -> str:
    gap = corpus.energy_poverty_gap(registry)
    inequity = corpus.tariff_inequity(registry)
    captive = corpus.captive_capacity(registry)
    security = corpus.fuel_security(registry)

    rows = [["Mali", f"{gap['mali_kwh_per_capita']:.0f}", "1,0"]]
    for scope, data in sorted(
        gap["comparators"].items(), key=lambda kv: kv[1]["kwh_per_capita"]
    ):
        rows.append(
            [
                scope,
                f"{data['kwh_per_capita']:.0f}",
                f"{data['multiple']:.1f}".replace(".", ","),
            ]
        )

    return "\n".join(
        [
            "## Le Mali dans son voisinage",
            "",
            "### Consommation d'électricité par habitant",
            "",
            _table(["Périmètre", "kWh/habitant/an", "Multiple du Mali"], rows),
            "",
            "### Qui paie quoi",
            "",
            f"- Abonné domestique raccordé au réseau : **{inequity['grid_household_xof_per_kwh']:.0f} FCFA/kWh**, "
            f"dont {inequity['subsidy_per_kwh_to_grid_customers']:.0f} FCFA/kWh de subvention publique",
            f"- Tranche sociale : **{inequity['social_tranche_xof_per_kwh']:.0f} FCFA/kWh**",
            f"- Ménage d'un mini-réseau rural : **{inequity['mini_grid_xof_per_kwh']:.0f} FCFA/kWh**, "
            f"sans subvention, soit {inequity['ratio_mini_grid_to_grid']:.1f} fois le tarif urbain",
            "",
            inequity["note"],
            "",
            "### Autoproduction minière",
            "",
            f"- Puissance en exploitation : **{captive['total_operating_mw']:.0f} MW** "
            f"({captive['operating_thermal_mw']:.0f} MW thermique, {captive['operating_solar_mw']:.0f} MW "
            f"solaire, {captive['operating_storage_mw']:.0f} MW de stockage)",
            f"- Rapport à la capacité thermique d'EDM-SA : **{captive['ratio_to_edm_thermal']:.0%}**",
            f"- Solaire déjà prévu en plus : **{captive['planned_solar_mw']:.0f} MW**",
            f"- Carburant économisé documenté : **{captive['documented_fuel_saved_litres_year'] / 1e6:.0f} millions "
            f"de litres par an**, soit environ {_md(captive['documented_fuel_saving_xof_year'])}",
            "",
            "Ces installations ne sont raccordées à rien. Elles constituent néanmoins la seule "
            "démonstration à l'échelle industrielle, sur le sol malien, que le solaire avec "
            "stockage remplace économiquement du fioul importé — arbitrage rendu sur fonds privés, "
            "sans subvention et sans garantie publique.",
            "",
            "### Exposition à la rupture d'approvisionnement",
            "",
            f"- Puissance ferme dépendant d'un carburant acheminé par route : "
            f"**{security['fuel_dependent_mw']:.0f} MW**, soit "
            f"**{security['share_of_firm_capacity']:.0%}** du disponible",
            f"- Camions-citernes détruits depuis septembre 2025 : **{security['trucks_destroyed']:.0f}**",
            f"- Flambée du prix au marché parallèle : **+{security['parallel_market_price_surge_pct']:.0f} %**",
            "",
            security["note"],
            "",
        ]
    )


def build(registry: Registry) -> str:
    """Rapport complet en Markdown."""
    parts = [
        "# Malinergy — rapport de décision sur le secteur électrique malien",
        "",
        f"Instantané des données : {registry['sector']['snapshot']}. "
        f"Toutes les valeurs monétaires sont en francs CFA ({registry['sector']['currency']}).",
        "",
        section_findings(registry),
        section_corpus(registry),
        section_tariff(registry),
        section_supply(registry),
        section_reliability(registry),
        section_solar(registry),
        section_lcoe(registry),
        section_comparison(registry),
        section_reforms(registry),
        section_decisions(registry),
        section_provenance(registry),
    ]
    return "\n".join(parts)

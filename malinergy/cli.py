"""Interface en ligne de commande.

python -m malinergy rapport            # rapport de décision complet
python -m malinergy décisions          # options classees
python -m malinergy facture 150        # facture d'un abonné
python -m malinergy export             # JSON pour le site
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from malinergy import __version__, load_registry
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
from malinergy.datasets import DataError, Registry
from malinergy.export import DEFAULT_OUT, write as export_write
from malinergy.report import RISK_LABEL, build as build_report


def _print_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [
        max(len(headers[i]), *(len(r[i]) for r in rows)) if rows else len(headers[i])
        for i in range(len(headers))
    ]
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print("  ".join(row[i].ljust(widths[i]) for i in range(len(headers))))


def cmd_sources(registry: Registry, args: argparse.Namespace) -> int:
    rows = [
        [s.id, s.publisher[:34], str(s.year), s.confidence, s.kind]
        for s in sorted(registry.sources.values(), key=lambda s: s.id)
    ]
    _print_table(["id", "éditeur", "année", "confiance", "nature"], rows)
    counts = registry.provenance_summary()
    print(
        f"\n{sum(counts.values())} références — "
        + ", ".join(f"{k}: {v}" for k, v in counts.items())
    )
    return 0


def cmd_valider(registry: Registry, args: argparse.Namespace) -> int:
    warnings = registry.validate()
    if not warnings:
        print("Jeux de données cohérents, toutes les sources sont déclarées.")
        return 0
    for w in warnings:
        print(f"avertissement: {w}", file=sys.stderr)
    return 1 if args.strict else 0


def cmd_facture(registry: Registry, args: argparse.Namespace) -> int:
    b = tariff.bill(registry, args.categorie, args.kwh, demand_kw=args.puissance)
    print(f"Catégorie      : {tariff.category(registry, args.categorie)['label']}")
    print(f"Consommation   : {args.kwh:,.0f} kWh/mois".replace(",", " "))
    print(f"Énergie        : {b.energy_charge:,.0f} FCFA".replace(",", " "))
    print(f"Prime fixe     : {b.fixed_charge:,.0f} FCFA".replace(",", " "))
    print(f"TVA            : {b.vat:,.0f} FCFA".replace(",", " "))
    print(f"Total          : {b.total:,.0f} FCFA".replace(",", " "))
    print(f"Prix moyen     : {b.average_price:,.1f} FCFA/kWh")
    costs = tariff.cost_of_supply(registry)
    print(
        f"Coût de fourniture : {costs['average_cost_xof_per_kwh']:.0f} FCFA/kWh "
        f"— écart supporte par le budget : "
        f"{costs['average_cost_xof_per_kwh'] - b.average_price:+.0f} FCFA/kWh"
    )
    return 0


def cmd_tarifs(registry: Registry, args: argparse.Namespace) -> int:
    costs = tariff.cost_of_supply(registry)
    print(f"Recette moyenne HT : {costs['average_revenue_xof_per_kwh']:.0f} FCFA/kWh")
    print(f"Coût de fourniture : {costs['average_cost_xof_per_kwh']:.0f} FCFA/kWh")
    print(
        f"Subvention         : {costs['subsidy_xof_per_kwh']:.0f} FCFA/kWh "
        f"({costs['annual_subsidy_xof'] / 1e9:.0f} Md FCFA/an)"
    )
    print(f"Couverture         : {costs['cost_recovery_ratio']:.0%}\n")
    rows = [
        [
            r["label"][:44],
            f"{r['share_of_sales']:.0%}",
            f"{r['customers_share']:.0%}",
            f"{r['unit_revenue_xof_per_kwh']:.0f}",
            f"{r['share_of_subsidy']:.0%}",
        ]
        for r in tariff.subsidy_incidence(registry)
    ]
    _print_table(["catégorie", "ventes", "abonnes", "FCFA/kWh", "subvention"], rows)
    return 0


def cmd_offre(registry: Registry, args: argparse.Namespace) -> int:
    stack = dispatch.merit_order(registry, args.demande, solar_available=args.solaire)
    rows = [
        [
            e.name[:40],
            e.technology,
            f"{e.available_mw:.0f}",
            f"{e.cumulative_mw:.0f}",
            f"{e.dispatched_mw:.0f}",
            f"{e.variable_cost_xof_per_kwh:.0f}",
        ]
        for e in stack
    ]
    _print_table(["moyen", "filière", "dispo MW", "cumul MW", "appele MW", "FCFA/kWh"], rows)
    balance = dispatch.capacity_balance(registry)
    print(
        f"\nPointe {balance['peak_demand_mw']:.0f} MW — ferme disponible "
        f"{balance['available_firm_mw']:.0f} MW — marge "
        f"{balance['firm_margin_mw']:+.0f} MW"
    )
    print(
        f"Coût marginal à la pointe du soir : {dispatch.marginal_cost(registry):.0f} FCFA/kWh"
    )
    return 0


def cmd_lcoe(registry: Registry, args: argparse.Namespace) -> int:
    rows = [
        [
            r.name[:38],
            f"{r.capacity_factor:.0%}",
            f"{r.capital_component:.0f}",
            f"{r.fixed_opex_component:.0f}",
            f"{r.fuel_component:.0f}",
            f"{r.total:.0f}",
            f"{r.lead_time_months}",
        ]
        for r in lcoe.ranking(registry, site=args.site)
    ]
    _print_table(["technologie", "fc", "capital", "exploit.", "combust.", "LCOE", "mois"], rows)
    print(
        f"\nRéférence : coût marginal du parc {dispatch.marginal_cost(registry):.0f} FCFA/kWh"
    )
    sens = lcoe.sensitivity(registry, "pv_utility", site=args.site)
    print(f"Facteur dominant du LCOE solaire : {sens['dominant_driver']}")
    return 0


def cmd_solaire(registry: Registry, args: argparse.Namespace) -> int:
    rows = [
        [
            s.name[:16],
            f"{s.ghi:.2f}",
            f"{s.specific_yield:.0f}",
            f"{s.capacity_factor:.1%}",
            "isole" if s.grid_km > 500 else f"{s.grid_km:.0f}",
            f"{s.score:.2f}",
            s.verdict[:42],
        ]
        for s in solar.rank_sites(registry)
    ]
    _print_table(["site", "GHI", "kWh/kWc", "fc", "km", "score", "orientation"], rows)
    spread = solar.resource_spread(registry)
    print(
        f"\nEcart de productible : {spread['yield_spread_share']:.0%} — "
        f"écart de coût de raccordement : facteur {spread['interconnection_spread_ratio']:.0f}"
    )
    return 0


def cmd_delestage(registry: Registry, args: argparse.Namespace) -> int:
    rows = [
        [
            str(y.year),
            f"{y.shedding_hours_per_day:.1f}",
            f"{y.unserved_gwh:.0f}",
            y.worst_month,
            f"{y.worst_month_hours:.1f}",
        ]
        for y in reliability.by_year(registry)
    ]
    _print_table(["année", "h/jour", "GWh non fournis", "pire mois", "h/jour"], rows)
    cost = reliability.cost_of_unreliability(registry)
    ratio = reliability.reliability_gap_vs_supply_cost(registry)
    print(
        f"\nCout économique : {cost['total_cost_xof'] / 1e9:.0f} Md FCFA/an "
        f"({cost['average_voll_xof_per_kwh']:.0f} FCFA/kWh non fourni)"
    )
    print(f"Rapport au coût marginal de production : {ratio['ratio']:.1f}x")
    print("Note : " + registry["outages"]["note"])
    return 0


def cmd_reformes(registry: Registry, args: argparse.Namespace) -> int:
    rows = [
        [str(e["year"]), e["title"][:52], e["category"], e["status"]]
        for e in reforms.timeline(registry)
    ]
    _print_table(["année", "decision", "catégorie", "statut"], rows)
    print(f"\nIndice de complétude : {reforms.completion_index(registry):.0%}")
    print("Ordre de traitement des lacunes :")
    labels = {c["id"]: c["label"] for c in registry["reforms"]["structural_conditions"]}
    for i, cid in enumerate(reforms.critical_path(registry), start=1):
        print(f"  {i}. {labels.get(cid, cid)}")
    for lesson in reforms.lessons(registry):
        print(f"\n> {lesson}")
    return 0


def cmd_decisions(registry: Registry, args: argparse.Namespace) -> int:
    for finding in decisions.headline_findings(registry):
        print(f"* {finding}\n")
    groups = decisions.by_category(registry)
    for label, options in groups.items():
        if not options:
            continue
        print(f"\n=== {label.upper()} ===")
        rows = []
        for o in options:
            payback = (
                "immediat"
                if o.payback_years == 0
                else ("n/a" if o.payback_years is None else f"{o.payback_years:.1f} ans")
            )
            rows.append(
                [
                    o.name[:46],
                    f"{o.risk_adjusted_benefit / 1e9:.1f}",
                    f"{o.capex_xof / 1e9:.0f}",
                    payback,
                    f"{o.lead_time_months}",
                    RISK_LABEL.get(o.risk, o.risk),
                ]
            )
        _print_table(["option", "gain Md/an", "capex Md", "retour", "mois", "risque"], rows)
    return 0


def cmd_corpus(registry: Registry, args: argparse.Namespace) -> int:
    cov = corpus.coverage(registry)
    print(
        f"{cov['count']} observations, {cov['distinct_sources']} sources, "
        f"{cov['year_span'][0]}-{cov['year_span'][1]} — "
        f"{cov['reconcilable']} réconciliables\n"
    )
    rows = [
        [
            o.label[:48],
            f"{o.value:,.2f}".replace(",", " "),
            o.unit[:18],
            str(o.year),
            o.scope[:20],
            o.source[:22],
        ]
        for o in corpus.observations(registry)
    ]
    _print_table(["observation", "valeur", "unité", "année", "périmètre", "source"], rows)
    return 0


def cmd_reconcilier(registry: Registry, args: argparse.Namespace) -> int:
    rows = [
        [
            r.label[:44],
            f"{r.published:,.2f}".replace(",", " "),
            f"{r.internal:,.2f}".replace(",", " "),
            f"{r.relative_gap:+.1%}",
            r.verdict,
        ]
        for r in corpus.reconcile(registry)
    ]
    _print_table(["grandeur", "publiée", "Malinergy", "écart", "verdict"], rows)
    print(f"\nConcordance : {corpus.reconciliation_score(registry):.0%}")
    for r in corpus.reconcile(registry):
        if r.resolution:
            print(f"\n> {r.label} — {r.resolution}")
    return 0


def cmd_comparer(registry: Registry, args: argparse.Namespace) -> int:
    gap = corpus.energy_poverty_gap(registry)
    print(f"Mali : {gap['mali_kwh_per_capita']:.0f} kWh/habitant/an")
    for scope, data in sorted(
        gap["comparators"].items(), key=lambda kv: kv[1]["kwh_per_capita"]
    ):
        print(f"  {scope:24s} {data['kwh_per_capita']:6.0f}  (x{data['multiple']:.1f})")

    inequity = corpus.tariff_inequity(registry)
    print("\nPrix payé par un ménage :")
    print(f"  réseau, usage courant    {inequity['grid_household_xof_per_kwh']:6.0f} FCFA/kWh")
    print(f"  tranche sociale          {inequity['social_tranche_xof_per_kwh']:6.0f} FCFA/kWh")
    print(
        f"  mini-réseau rural        {inequity['mini_grid_xof_per_kwh']:6.0f} FCFA/kWh "
        f"(x{inequity['ratio_mini_grid_to_grid']:.1f}, sans subvention)"
    )

    captive = corpus.captive_capacity(registry)
    print(
        f"\nAutoproduction minière : {captive['total_operating_mw']:.0f} MW "
        f"({captive['ratio_to_edm_thermal']:.0%} du thermique EDM-SA), dont "
        f"{captive['operating_solar_mw']:.0f} MW solaire"
    )

    security = corpus.fuel_security(registry)
    print(
        f"Puissance ferme dépendant d'un convoi routier : "
        f"{security['fuel_dependent_mw']:.0f} MW "
        f"({security['share_of_firm_capacity']:.0%})"
    )
    return 0


def cmd_rapport(registry: Registry, args: argparse.Namespace) -> int:
    markdown = build_report(registry)
    if args.sortie:
        Path(args.sortie).write_text(markdown, encoding="utf-8")
        print(f"rapport ecrit dans {args.sortie}")
    else:
        print(markdown)
    return 0


def cmd_pdf(registry: Registry, args: argparse.Namespace) -> int:
    from malinergy.pdf import PdfUnavailable, build as build_pdf

    try:
        path = build_pdf(build_report(registry), args.sortie)
    except PdfUnavailable as exc:
        print(f"rendu PDF indisponible: {exc}", file=sys.stderr)
        return 3
    print(f"{path} ({path.stat().st_size / 1024:.0f} Ko)")
    return 0


def cmd_export(registry: Registry, args: argparse.Namespace) -> int:
    paths = export_write(registry, args.sortie)
    for path in paths:
        print(path)
    return 0


def cmd_json(registry: Registry, args: argparse.Namespace) -> int:
    from malinergy.export import build_payloads

    payloads = build_payloads(registry)
    if args.section not in payloads:
        print(
            f"section inconnue: {args.section} "
            f"(disponibles: {', '.join(sorted(payloads))})",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(payloads[args.section], ensure_ascii=False, indent=2, default=str))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="malinergy",
        description="Plateforme de connaissances sur le secteur énergétique malien.",
    )
    parser.add_argument("--version", action="version", version=f"malinergy {__version__}")
    parser.add_argument(
        "--donnees", type=Path, default=None, help="repertoire de jeux de données alternatif"
    )
    sub = parser.add_subparsers(dest="commande", required=True)

    sub.add_parser("sources", help="registre des sources").set_defaults(func=cmd_sources)

    p = sub.add_parser("valider", help="vérifier la cohérence des jeux de données")
    p.add_argument("--strict", action="store_true", help="sortir en erreur sur avertissement")
    p.set_defaults(func=cmd_valider)

    p = sub.add_parser("facture", help="facture mensuelle d'un abonné")
    p.add_argument("kwh", type=float)
    p.add_argument("--categorie", default="bt_domestique")
    p.add_argument(
        "--puissance", type=float, default=0.0, help="puissance souscrite en kW (MT)"
    )
    p.set_defaults(func=cmd_facture)

    sub.add_parser(
        "tarifs", help="vérité des coûts et incidence de la subvention"
    ).set_defaults(func=cmd_tarifs)

    p = sub.add_parser("offre", help="ordre de mérite et équilibre de puissance")
    p.add_argument("--demande", type=float, default=None, help="demande en MW")
    p.add_argument(
        "--solaire", action="store_true", help="se placer en journée, solaire disponible"
    )
    p.set_defaults(func=cmd_offre)

    p = sub.add_parser("lcoe", help="coût complet des options de production")
    p.add_argument("--site", default="segou")
    p.set_defaults(func=cmd_lcoe)

    sub.add_parser("solaire", help="classement des sites solaires").set_defaults(
        func=cmd_solaire
    )
    sub.add_parser("delestage", help="historique et coût économique du délestage").set_defaults(
        func=cmd_delestage
    )
    sub.add_parser("reformes", help="séquence des réformes et chaînons manquants").set_defaults(
        func=cmd_reformes
    )
    sub.add_parser("decisions", help="options d'action classées").set_defaults(
        func=cmd_decisions
    )
    sub.add_parser("corpus", help="observations externes collectées").set_defaults(
        func=cmd_corpus
    )
    sub.add_parser(
        "reconcilier", help="confronter les grandeurs internes aux sources publiées"
    ).set_defaults(func=cmd_reconcilier)
    sub.add_parser("comparer", help="le Mali face à ses comparateurs").set_defaults(
        func=cmd_comparer
    )

    p = sub.add_parser("rapport", help="rapport de décision complet en Markdown")
    p.add_argument("--sortie", type=Path, default=None)
    p.set_defaults(func=cmd_rapport)

    p = sub.add_parser("pdf", help="rapport de décision au format PDF imprimable")
    p.add_argument("--sortie", type=Path, default=Path("public/assets/malinergy-rapport.pdf"))
    p.set_defaults(func=cmd_pdf)

    p = sub.add_parser("export", help="exporter le JSON consommé par le site")
    p.add_argument("--sortie", type=Path, default=DEFAULT_OUT)
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("json", help="afficher une section exportee")
    p.add_argument("section")
    p.set_defaults(func=cmd_json)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        registry = load_registry(args.donnees)
    except DataError as exc:
        print(f"erreur de données: {exc}", file=sys.stderr)
        return 2
    try:
        return args.func(registry, args)
    except BrokenPipeError:  # sortie tronquee par un pipe (head, less)
        try:
            sys.stdout.close()
        finally:
            return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

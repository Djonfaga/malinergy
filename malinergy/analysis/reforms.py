"""Séquence des réformes: ce qui est acquis, ce qui à été defait, ce qui manque.

Une réforme énergétique n'est pas une liste de mesures mais un ordre. Certaines
décisions n'ont d'effet que si une autre à été prise avant: un appel d'offres IPP
competitif ne fait baisser le prix du kWh que si l'acheteur est solvable. Ce module
explicite ces dépendances et identifié les chaînons dont l'absence annule le
rendement des mesures déjà prises.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from malinergy.datasets import Registry

STATUS_WEIGHT = {
    "acquis": 1.0,
    "en_cours": 0.6,
    "partiel": 0.4,
    "manquant": 0.0,
    "regression": -0.5,
    "renverse": 0.0,
}

# Ce qu'une condition structurelle debloque. La cle est la condition, la valeur la
# liste des decisions dont le rendement en depend.
UNLOCKS = {
    "solvabilite_acheteur": ["appels_offres_ipp", "planification_moindre_cout"],
    "verite_des_couts": ["solvabilite_acheteur", "subvention_ciblee"],
    "regulateur_independant": ["verite_des_couts"],
    "comptage_recouvrement": ["solvabilite_acheteur"],
    "subvention_ciblee": [],
    "appels_offres_ipp": [],
    "planification_moindre_cout": [],
    "cadre_minireseaux": [],
}


@dataclass(frozen=True)
class Gap:
    id: str
    label: str
    status: str
    why_it_matters: str
    unlocks: tuple[str, ...]
    leverage: int
    source: str


def timeline(registry: Registry) -> list[dict]:
    return sorted(registry["reforms"]["events"], key=lambda e: (e["year"], e["title"]))


def cadence(registry: Registry) -> dict:
    """Rythme et composition de la séquence de réforme."""
    events = timeline(registry)
    by_category = Counter(e["category"] for e in events)
    by_status = Counter(e["status"] for e in events)
    years = [e["year"] for e in events]
    reversed_events = [e for e in events if e["status"] in ("renverse", "regression")]
    return {
        "count": len(events),
        "span": (min(years), max(years)),
        "by_category": dict(by_category),
        "by_status": dict(by_status),
        "reversal_rate": len(reversed_events) / len(events),
        "reversed": [{"year": e["year"], "title": e["title"]} for e in reversed_events],
    }


def completion_index(registry: Registry) -> float:
    """Indice de complétude des conditions structurelles, dans [0, 1].

    Il ne mesure pas le nombre de textes adoptes mais la part des conditions
    reellement en place — c'est la difference entre annoncer une réforme et en
    percevoir le rendement.
    """
    conditions = registry["reforms"]["structural_conditions"]
    total = sum(STATUS_WEIGHT.get(c["status"], 0.0) for c in conditions)
    return max(0.0, total / len(conditions))


def gaps(registry: Registry) -> list[Gap]:
    """Conditions manquantes ou partielles, classées par effet de levier.

    Le levier d'une condition est le nombre de décisions en aval dont elle
    conditionné le rendement, dépendances transitives comprises.
    """

    def downstream(cid: str, seen: set[str] | None = None) -> set[str]:
        seen = seen or set()
        for nxt in UNLOCKS.get(cid, []):
            if nxt not in seen:
                seen.add(nxt)
                downstream(nxt, seen)
        return seen

    result = []
    for cond in registry["reforms"]["structural_conditions"]:
        if cond["status"] in ("acquis",):
            continue
        unlocks = tuple(sorted(downstream(cond["id"])))
        result.append(
            Gap(
                id=cond["id"],
                label=cond["label"],
                status=cond["status"],
                why_it_matters=cond["why_it_matters"],
                unlocks=unlocks,
                leverage=len(unlocks),
                source=cond["source"],
            )
        )
    result.sort(key=lambda g: (g.leverage, g.status == "manquant"), reverse=True)
    return result


def critical_path(registry: Registry) -> list[str]:
    """Ordre dans lequel les conditions manquantes doivent être traitees.

    Un tri topologique sur les dépendances: une condition ne peut produire son
    effet avant celles qu'elle débloque.
    """
    pending = {g.id: set(g.unlocks) for g in gaps(registry)}
    ordered: list[str] = []
    while pending:
        # On sort d'abord les conditions dont toutes les dependances aval sont
        # deja traitees ou hors du perimetre des lacunes.
        ready = [cid for cid, deps in pending.items() if not (deps & set(pending))]
        if not ready:  # cycle: on rend l'ordre restant tel quel
            ordered.extend(sorted(pending))
            break
        for cid in sorted(ready):
            ordered.append(cid)
            del pending[cid]
    ordered.reverse()
    return ordered


def lessons(registry: Registry) -> list[str]:
    """Enseignements deduits de la séquence, pas de l'opinion."""
    stats = cadence(registry)
    out = []
    if stats["reversal_rate"] > 0.1:
        out.append(
            f"{stats['reversal_rate']:.0%} des décisions recensées ont été annulées ou ont "
            "régressé. Une réforme qui ne survit pas à un cycle politique ne produit aucun "
            "rendement: la séquence doit privilégier les mesures dont l'effet est visible "
            "avant l'échéance suivante."
        )
    financial = [e for e in timeline(registry) if e["category"] == "finance"]
    if all(e["status"] != "acquis" for e in financial):
        out.append(
            "Aucune mesure de la catégorie financière n'est arrivée à son terme. "
            "L'infrastructure a avancé, l'équilibre financier non — c'est pourquoi une "
            "capacité nouvelle se traduit par une dette nouvelle plutôt que par un "
            "service amélioré."
        )
    idx = completion_index(registry)
    out.append(
        f"Indice de complétude des conditions structurelles: {idx:.0%}. "
        "En dessous de la moitié, le rendement des investissements physiques reste "
        "capté par le déficit d'exploitation."
    )
    return out

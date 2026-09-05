"""Chargement, validation et accès aux jeux de données.

Toute valeur chiffrée du dépôt vit dans ``malinergy/data/*.json`` et référence un
identifiant du registre des sources. :meth:`Registry.validate` fait échouer le
chargement si une référence est manquante ou si un agregat sort de son domaine
de definition — c'est le garde-fou qui empêche un chiffre non source de se
glisser dans une recommandation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any, Iterator

DATA_DIR = Path(__file__).resolve().parent / "data"

DATASET_FILES = {
    "sources": "sources.json",
    "tariffs": "tariffs.json",
    "sector": "sector.json",
    "generation": "generation.json",
    "solar": "solar.json",
    "grid": "grid.json",
    "outages": "outages.json",
    "reforms": "reforms.json",
    "interventions": "interventions.json",
    "observations": "observations.json",
    "mines": "mines.json",
}

CONFIDENCE_ORDER = ("haute", "moyenne", "faible")


class DataError(ValueError):
    """Un jeu de données est incohérent ou une source est introuvable."""


@dataclass(frozen=True)
class Source:
    id: str
    title: str
    publisher: str
    year: int
    kind: str
    url: str
    confidence: str
    caveat: str = ""

    @property
    def is_estimate(self) -> bool:
        return self.kind == "estimation"

    def cite(self) -> str:
        return f"{self.publisher} ({self.year}) — {self.title}"


@dataclass(frozen=True)
class Value:
    """Une grandeur scalaire accompagnee de sa provenance."""

    value: float
    source: str
    confidence: str = "moyenne"
    note: str = ""

    def __float__(self) -> float:  # pragma: no cover - trivial
        return float(self.value)


def _iter_source_refs(node: Any) -> Iterator[str]:
    """Parcourt un document et rend tous les identifiants de source rencontres."""
    if isinstance(node, dict):
        for key, sub in node.items():
            if key == "source" and isinstance(sub, str):
                yield sub
            else:
                yield from _iter_source_refs(sub)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_source_refs(item)


@dataclass
class Registry:
    """Accès unifie aux jeux de données."""

    documents: dict[str, dict] = field(default_factory=dict)

    # ------------------------------------------------------------------ accès
    def __getitem__(self, name: str) -> dict:
        try:
            return self.documents[name]
        except KeyError as exc:  # pragma: no cover - garde
            raise DataError(f"jeu de données inconnu: {name}") from exc

    @cached_property
    def sources(self) -> dict[str, Source]:
        return {
            entry["id"]: Source(
                id=entry["id"],
                title=entry["title"],
                publisher=entry["publisher"],
                year=entry["year"],
                kind=entry["kind"],
                url=entry["url"],
                confidence=entry["confidence"],
                caveat=entry.get("caveat", ""),
            )
            for entry in self["sources"]["sources"]
        }

    def source(self, source_id: str) -> Source:
        try:
            return self.sources[source_id]
        except KeyError as exc:
            raise DataError(f"source inconnue: {source_id}") from exc

    def scalar(self, dataset: str, *path: str) -> Value:
        """Lit une grandeur ``{"value": ..., "source": ...}`` par son chemin."""
        node: Any = self[dataset]
        for step in path:
            if not isinstance(node, dict) or step not in node:
                raise DataError(f"chemin introuvable: {dataset}.{'.'.join(path)}")
            node = node[step]
        if not isinstance(node, dict) or "value" not in node:
            raise DataError(f"{dataset}.{'.'.join(path)} n'est pas une grandeur sourcee")
        return Value(
            value=float(node["value"]),
            source=node.get("source", "malinergy-estimation"),
            confidence=node.get("confidence", "moyenne"),
            note=node.get("note", ""),
        )

    def value(self, dataset: str, *path: str) -> float:
        """Raccourci: la valeur numérique seule."""
        return self.scalar(dataset, *path).value

    # ------------------------------------------------------------- validation

    def validate(self) -> list[str]:
        """Vérifie la cohérence interne. Retourne la liste des avertissements."""
        warnings: list[str] = []
        known = set(self.sources)

        for name, doc in self.documents.items():
            if name == "sources":
                continue
            for ref in _iter_source_refs(doc):
                if ref not in known:
                    raise DataError(f"{name}: source non declaree '{ref}'")

        for src in self.sources.values():
            if src.confidence not in CONFIDENCE_ORDER:
                raise DataError(f"source {src.id}: confiance invalide '{src.confidence}'")

                # Domaines de definition des agregats sectoriels.
        for key in (
            "network_losses_share",
            "collection_rate",
            "access_rate_national",
            "access_rate_urban",
            "access_rate_rural",
            "demand_growth_rate",
        ):
            v = self.value("sector", "aggregates", key)
            if not 0.0 <= v <= 1.0:
                raise DataError(f"sector.aggregates.{key} hors [0, 1]: {v}")

        sales = self.value("sector", "aggregates", "sales_gwh_year")
        generation = self.value("sector", "aggregates", "generation_gwh_year")
        if sales >= generation:
            raise DataError("les ventes ne peuvent pas depasser la production injectée")

        implied_losses = 1.0 - sales / generation
        declared_losses = self.value("sector", "aggregates", "network_losses_share")
        if abs(implied_losses - declared_losses) > 0.02:
            warnings.append(
                f"pertes déclarées ({declared_losses:.1%}) et pertes impliquées par "
                f"production/ventes ({implied_losses:.1%}) divergent de plus de 2 points"
            )

        mix_total = sum(row["share_of_sales"] for row in self["tariffs"]["sales_mix"])
        if abs(mix_total - 1.0) > 1e-6:
            raise DataError(f"la répartition des ventes par catégorie somme à {mix_total}")

        categories = {c["id"] for c in self["tariffs"]["categories"]}
        for row in self["tariffs"]["sales_mix"]:
            if row["category"] not in categories:
                raise DataError(
                    f"répartition des ventes: catégorie inconnue '{row['category']}'"
                )

        node_ids = {n["id"] for n in self["grid"]["nodes"]}
        for line in self["grid"]["lines"]:
            for end in ("from", "to"):
                if line[end] not in node_ids:
                    raise DataError(f"ligne réseau vers un nœud inconnu: {line[end]}")

        obs_ids = [o["id"] for o in self["observations"]["observations"]]
        if len(set(obs_ids)) != len(obs_ids):
            raise DataError("le corpus contient des observations en double")
        for obs in self["observations"]["observations"]:
            if not obs.get("unit"):
                raise DataError(f"observation sans unité: {obs['id']}")

        months = [row["month"] for row in self["outages"]["series"]]
        if months != sorted(months):
            raise DataError("la série de délestage n'est pas ordonnee chronologiquement")
        if len(set(months)) != len(months):
            raise DataError("la série de délestage contient des mois en double")

        return warnings

    # ---------------------------------------------------------------- qualité

    def provenance_summary(self) -> dict[str, int]:
        """Compte les références par niveau de confiance, tous jeux confondus."""
        counts = {level: 0 for level in CONFIDENCE_ORDER}
        for name, doc in self.documents.items():
            if name == "sources":
                continue
            for ref in _iter_source_refs(doc):
                counts[self.source(ref).confidence] += 1
        return counts


def load_registry(data_dir: Path | None = None) -> Registry:
    """Charge et valide l'ensemble des jeux de données."""
    directory = Path(data_dir) if data_dir else DATA_DIR
    documents = {}
    for name, filename in DATASET_FILES.items():
        path = directory / filename
        if not path.exists():
            raise DataError(f"fichier de données manquant: {path}")
        documents[name] = json.loads(path.read_text(encoding="utf-8"))
    registry = Registry(documents=documents)
    registry.validate()
    return registry

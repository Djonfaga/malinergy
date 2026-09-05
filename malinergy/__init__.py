"""Malinergy — plateforme de connaissances ouverte sur le secteur énergétique malien.

Le paquet exposé trois couches:

``malinergy.datasets``
    Les jeux de données curates (tarifs, parc de production, réseau, irradiation,
    délestage, réformes) avec leur provenance.

``malinergy.analysis``
    Les calculs qui transforment ces données en grandeurs decisionnelles: facture
    et vérité des coûts, LCOE, gisement solaire, coût économique du délestage,
    ordre de mérite, chaînons manquants de la réforme.

``malinergy.report`` / ``malinergy.cli``
    La restitution: rapport en Markdown, export JSON pour le site.

Regle du dépôt: aucune valeur chiffrée n'existe dans le code. Tout nombre vient
d'un fichier de ``malinergy/data`` et porté un identifiant de source.
"""

__version__ = "0.1.0"

from malinergy.datasets import Registry, load_registry

__all__ = ["Registry", "load_registry", "__version__"]

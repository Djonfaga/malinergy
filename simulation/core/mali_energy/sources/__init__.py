"""Connectors to the external datasets used by the study.

Two tiers exist:

* **Online-anywhere** — :mod:`~mali_energy.sources.owid` and
  :mod:`~mali_energy.sources.population` are served from a mirror that most
  restricted networks allow, and their extracts are committed under
  ``data/snapshots`` so the project builds offline.
* **Authoritative but firewall-sensitive** — :mod:`~mali_energy.sources.pvgis`,
  :mod:`~mali_energy.sources.nasa_power`, :mod:`~mali_energy.sources.worldbank`
  and :mod:`~mali_energy.sources.overpass` talk to the primary services. Run
  ``mali-energy fetch --all`` from an unrestricted machine to populate the
  cache; every downstream model degrades to a documented fallback if the cache
  is empty, and says so in its data card.
"""

from . import nasa_power, overpass, owid, population, pvgis, worldbank

__all__ = ["nasa_power", "overpass", "owid", "population", "pvgis", "worldbank"]

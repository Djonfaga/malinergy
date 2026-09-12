"""Provenance tracking.

Every number that enters a simulation carries a :class:`Source` and a
:class:`Confidence`. Nothing in this project is allowed to be an anonymous
constant: the validation step refuses to build a network from rows whose
provenance fields are empty, and :func:`data_card` renders the bibliography
that accompanies a published result.
"""

from __future__ import annotations

import enum
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import date


class Confidence(enum.Enum):
    """How much weight a figure can carry in a published conclusion."""

    #: Read directly from a primary dataset or an official publication.
    MEASURED = "measured"
    #: Published by a credible secondary source (press release, sector report).
    REPORTED = "reported"
    #: Computed from measured inputs with a documented method.
    DERIVED = "derived"
    #: Engineering estimate from typical values; must be verified before use in
    #: a quantitative claim. Flagged in every report.
    ESTIMATED = "estimated"

    @property
    def publishable(self) -> bool:
        return self is not Confidence.ESTIMATED


@dataclass(frozen=True)
class Source:
    """A citable origin for a dataset or a single figure."""

    key: str
    title: str
    publisher: str
    url: str = ""
    accessed: str = ""
    licence: str = ""
    note: str = ""

    def citation(self) -> str:
        bits = [self.publisher, self.title]
        if self.url:
            bits.append(self.url)
        if self.accessed:
            bits.append(f"accessed {self.accessed}")
        return ". ".join(b for b in bits if b)


#: Registry of the sources used by the committed dataset. Keys are referenced
#: from the ``source`` column of every reference table.
SOURCES: dict[str, Source] = {
    s.key: s
    for s in [
        Source(
            key="owid-energy",
            title="Energy dataset (electricity generation, demand and mix by country)",
            publisher="Our World in Data, compiled from Ember and the Energy Institute",
            url="https://github.com/owid/energy-data",
            licence="CC BY 4.0",
            note="Primary calibration series for national electricity balance.",
        ),
        Source(
            key="worldbank-wdi",
            title="World Development Indicators",
            publisher="World Bank",
            url="https://api.worldbank.org/v2/country/MLI/indicator",
            licence="CC BY 4.0",
            note="Access to electricity, transmission and distribution losses, population.",
        ),
        Source(
            key="worldbank-population",
            title="Population, total (SP.POP.TOTL)",
            publisher="World Bank via the Frictionless population mirror",
            url="https://github.com/datasets/population",
            licence="CC BY 4.0",
        ),
        Source(
            key="geonames",
            title="Gazetteer of populated places",
            publisher="GeoNames",
            url="https://www.geonames.org/",
            licence="CC BY 4.0",
            note="Coordinates of Malian load centres.",
        ),
        Source(
            key="pvgis",
            title="Photovoltaic Geographical Information System, v5.2 (SARAH-2 / ERA5)",
            publisher="European Commission, Joint Research Centre",
            url="https://re.jrc.ec.europa.eu/pvg_tools/en/",
            licence="Free reuse with attribution",
            note="Hourly irradiance and PV yield at the coordinates of each plant.",
        ),
        Source(
            key="nasa-power",
            title="POWER hourly meteorological and solar data",
            publisher="NASA Langley Research Center",
            url="https://power.larc.nasa.gov/",
            licence="Public domain",
        ),
        Source(
            key="osm",
            title="Power infrastructure of Mali (lines, substations, plants)",
            publisher="OpenStreetMap contributors, via the Overpass API",
            url="https://overpass-api.de/",
            licence="ODbL 1.0",
        ),
        Source(
            key="edm-sa",
            title="Rapports annuels et donnees d'exploitation",
            publisher="Energie du Mali (EDM-SA)",
            url="https://www.edmsa.ml/",
            note="Utility figures; rows citing this source must be checked against "
            "the latest annual report before publication.",
        ),
        Source(
            key="omvs",
            title="Amenagements hydroelectriques de Manantali, Felou et Gouina",
            publisher="Organisation pour la mise en valeur du fleuve Senegal (OMVS) / SOGEM",
            url="https://www.omvs.org/",
        ),
        Source(
            key="wapp",
            title="West African Power Pool information system and master plan",
            publisher="WAPP / EEEOA",
            url="https://www.ecowapp.org/",
        ),
        Source(
            key="cree",
            title="Deliberations tarifaires et rapports de suivi du secteur",
            publisher="Commission de regulation de l'electricite et de l'eau (CREE), Mali",
            url="https://www.cree-mali.org/",
        ),
        Source(
            key="irena",
            title="Renewable capacity statistics",
            publisher="International Renewable Energy Agency",
            url="https://www.irena.org/Statistics",
            licence="CC BY 4.0",
        ),
        Source(
            key="iec-60909",
            title="IEC 60909-0 Short-circuit currents in three-phase a.c. systems",
            publisher="International Electrotechnical Commission",
        ),
        Source(
            key="cigre",
            title="Overhead line design and conductor characteristics",
            publisher="CIGRE / IEC 61089 standard conductor tables",
            note="Basis of the conductor library used to derive line impedances.",
        ),
        Source(
            key="engineering",
            title="Engineering estimate from typical design practice",
            publisher="this study",
            note="Used only where no published value could be obtained; always "
            "carries confidence=estimated and appears in the verification checklist.",
        ),
    ]
}


@dataclass
class DataCard:
    """Machine-readable summary of what went into a build."""

    name: str
    built: str = field(default_factory=lambda: date.today().isoformat())
    records: int = 0
    sources: list[str] = field(default_factory=list)
    confidence_mix: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_json(self, indent: int = 2) -> str:
        payload = asdict(self)
        payload["bibliography"] = [
            SOURCES[k].citation() for k in self.sources if k in SOURCES
        ]
        return json.dumps(payload, indent=indent, ensure_ascii=False)


def resolve(keys: Iterable[str]) -> list[Source]:
    """Return the :class:`Source` objects for ``keys``, raising on unknown ones."""
    out = []
    for k in keys:
        k = (k or "").strip()
        if not k:
            continue
        if k not in SOURCES:
            raise KeyError(
                f"unknown source key {k!r}; register it in mali_energy.provenance.SOURCES"
            )
        out.append(SOURCES[k])
    return out


def bibliography(keys: Iterable[str]) -> str:
    """Render a plain-text bibliography, one numbered entry per source."""
    seen: list[Source] = []
    for s in resolve(keys):
        if s not in seen:
            seen.append(s)
    return "\n".join(f"[{i}] {s.citation()}" for i, s in enumerate(seen, 1))

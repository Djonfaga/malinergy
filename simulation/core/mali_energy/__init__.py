"""Canonical data layer for the Mali power-system simulation benchmark.

The package turns published statistics and a documented network catalogue into
one frozen study case, so that PowerFactory, OpenModelica, pandapower,
pandapipes and Simscape Electrical all model the *same* system and their
results can be compared rather than merely collected.
"""

from .config import DEFAULT_STUDY, REFERENCE_YEAR, StudyConfig
from .exchange import (
    OPERATING_POINTS,
    build_all_cases,
    build_case,
    export_exchange,
    load_exchange,
)
from .grid import GridCatalog, export_json, load_catalog
from .grid.validation import validate

__version__ = "1.0.0"

__all__ = [
    "DEFAULT_STUDY",
    "OPERATING_POINTS",
    "REFERENCE_YEAR",
    "GridCatalog",
    "StudyConfig",
    "__version__",
    "build_all_cases",
    "build_case",
    "export_exchange",
    "export_json",
    "load_catalog",
    "load_exchange",
    "validate",
]

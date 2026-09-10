"""Canonical data layer for the Mali power-system simulation benchmark.

The package turns published statistics and a documented network catalogue into
one frozen study case, so that PowerFactory, OpenModelica, pandapower,
pandapipes and Simscape Electrical all model the *same* system and their
results can be compared rather than merely collected.
"""

from .config import DEFAULT_STUDY, REFERENCE_YEAR, StudyConfig  # noqa: F401
from .exchange import (  # noqa: F401
    OPERATING_POINTS,
    build_all_cases,
    build_case,
    export_exchange,
    load_exchange,
)
from .grid import GridCatalog, export_json, load_catalog  # noqa: F401
from .grid.validation import validate  # noqa: F401

__version__ = "1.0.0"

__all__ = [
    "StudyConfig",
    "DEFAULT_STUDY",
    "REFERENCE_YEAR",
    "load_catalog",
    "export_json",
    "GridCatalog",
    "validate",
    "build_case",
    "build_all_cases",
    "export_exchange",
    "load_exchange",
    "OPERATING_POINTS",
    "__version__",
]

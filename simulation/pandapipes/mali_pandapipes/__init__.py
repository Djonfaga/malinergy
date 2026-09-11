"""pandapipes studies of Malian fluid networks and their coupling to the grid."""

from .coupling import evaluate_storage_flexibility, pumping_load_by_bus  # noqa: F401
from .water import load_water_catalog, run_case  # noqa: F401

__version__ = "1.0.0"
__all__ = [
    "load_water_catalog",
    "run_case",
    "pumping_load_by_bus",
    "evaluate_storage_flexibility",
]

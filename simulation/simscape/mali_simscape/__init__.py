"""Converter studies for the Malian photovoltaic fleet.

The deliverable is the Simscape Electrical model in ``matlab/``. The Python
code here is a second implementation of the same plant and control law, used to
check it and to produce results where MATLAB is not installed. Every result
says which implementation produced it.
"""

from .grid_strength import ConnectionPoint, connection_points, strength_table  # noqa: F401
from .matlab import compare_results, matlab_available, run_matlab_studies  # noqa: F401
from .reference import InverterDesign, simulate_inverter, stability_sweep  # noqa: F401
from .studies import (  # noqa: F401
    converter_limit_study,
    grid_strength_study,
    step_response_study,
    strength_sweep,
    voltage_dip_study,
    weak_grid_comparison,
)

__version__ = "1.0.0"
__all__ = [
    "InverterDesign",
    "simulate_inverter",
    "stability_sweep",
    "ConnectionPoint",
    "connection_points",
    "strength_table",
    "grid_strength_study",
    "step_response_study",
    "converter_limit_study",
    "strength_sweep",
    "voltage_dip_study",
    "weak_grid_comparison",
    "matlab_available",
    "run_matlab_studies",
    "compare_results",
]

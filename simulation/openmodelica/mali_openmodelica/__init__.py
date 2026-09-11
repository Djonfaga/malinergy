"""Dynamic studies of the Malian power system.

The Modelica library in ``modelica/MaliEnergy`` is the model; the SciPy code in
:mod:`mali_openmodelica.reference` is a second implementation of the same
equations, used to check it. Where an OpenModelica compiler is present both are
run and compared; where it is not, the reference is used and every result says
which tool produced it.
"""

from .driver import openmodelica_available, simulate  # noqa: F401
from .reference import (  # noqa: F401
    FrequencyCase,
    MinigridDesign,
    simulate_frequency,
    simulate_minigrid,
)
from .studies import cross_check, frequency_scenarios, inertia_report, minigrid_study  # noqa: F401

__version__ = "1.0.0"
__all__ = [
    "FrequencyCase",
    "MinigridDesign",
    "simulate_frequency",
    "simulate_minigrid",
    "inertia_report",
    "frequency_scenarios",
    "minigrid_study",
    "cross_check",
    "simulate",
    "openmodelica_available",
]

"""pandapower studies of the Malian interconnected network."""

from .builder import BuildResult, apply_load_shedding, build, build_all  # noqa: F401

__version__ = "1.0.0"
__all__ = ["build", "build_all", "apply_load_shedding", "BuildResult"]

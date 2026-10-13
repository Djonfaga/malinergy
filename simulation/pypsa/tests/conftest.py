"""Shared fixtures.

The dispatch is solved once per session on a three-hourly year. Three hours is
the coarsest interval at which a snapshot still falls clearly on one side of
sunrise, so the diurnal checks stay meaningful; anything coarser would leave
the model's own night check unexercised, and that check has caught real
errors.
"""

import pytest
from mali_pypsa.demand import snapshots
from mali_pypsa.dispatch import solve
from mali_pypsa.network import build_network

from mali_energy.grid import load_catalog

YEAR = 2024
STEP_HOURS = 3


@pytest.fixture(scope="session")
def catalog():
    return load_catalog()


@pytest.fixture(scope="session")
def index():
    return snapshots(YEAR, step_hours=STEP_HOURS)


@pytest.fixture(scope="session")
def build(catalog):
    return build_network(catalog, year=YEAR, step_hours=STEP_HOURS, prefer_atlite=False)


@pytest.fixture(scope="session")
def result(build):
    return solve(build)


@pytest.fixture
def fresh_build(catalog):
    """An unsolved build a test may break on purpose.

    The session build is shared and already carries a solved solver model, so
    anything that mutates a network or solves it twice needs its own. Coarse,
    because these tests are about failure handling rather than numbers.
    """
    return build_network(catalog, year=YEAR, step_hours=12, prefer_atlite=False)

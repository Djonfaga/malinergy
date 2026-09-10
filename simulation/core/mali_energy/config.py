"""Central configuration: paths, physical constants and study conventions.

Everything that another module might be tempted to hard-code lives here, so a
study can be re-parameterised without touching model code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent

DATA_DIR = Path(os.environ.get("MALI_ENERGY_DATA", PROJECT_ROOT / "data"))
REFERENCE_DIR = DATA_DIR / "reference"     # curated, version-controlled tables
RAW_DIR = DATA_DIR / "raw"                 # downloaded payloads (not committed)
SNAPSHOT_DIR = DATA_DIR / "snapshots"      # committed extracts of remote data
BUILD_DIR = Path(os.environ.get("MALI_ENERGY_BUILD", PROJECT_ROOT / "build"))

for _d in (RAW_DIR, SNAPSHOT_DIR, BUILD_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Country / study conventions
# --------------------------------------------------------------------------

COUNTRY = "Mali"
ISO3 = "MLI"
TIMEZONE = "Africa/Bamako"        # UTC+0 all year, no daylight saving
CRS_GEOGRAPHIC = "EPSG:4326"
CRS_PROJECTED = "EPSG:32629"      # UTM zone 29N, covers western Mali

BASE_MVA = 100.0                  # per-unit base for every tool in the benchmark
NOMINAL_FREQUENCY_HZ = 50.0

#: Reference year for the base-case study. Every calibration figure, load level
#: and generation dispatch in the committed dataset refers to this year.
REFERENCE_YEAR = 2024

#: Voltage levels present in the Malian interconnected network, in kV.
VOLTAGE_LEVELS_KV = (225.0, 150.0, 66.0, 33.0, 30.0, 15.0, 0.4)

#: Statutory steady-state voltage band applied in the studies (p.u.).
#: WAPP Operation Manual practice for transmission planning; tighten or relax
#: through :class:`StudyConfig` rather than editing this constant.
VOLTAGE_LIMITS_PU = (0.95, 1.05)
VOLTAGE_LIMITS_PU_EMERGENCY = (0.90, 1.10)

#: Thermal loading limits applied to branches (% of rated current).
LOADING_LIMIT_NORMAL_PCT = 100.0
LOADING_LIMIT_CONTINGENCY_PCT = 120.0


@dataclass(frozen=True)
class StudyConfig:
    """Parameters that define one study case.

    The defaults reproduce the committed base case; benchmark runs vary them
    explicitly so that every published figure can be traced to a config.
    """

    year: int = REFERENCE_YEAR
    #: Share of national electricity demand served by the EDM-SA interconnected
    #: network, the remainder being isolated centres and captive industrial
    #: generation (mainly gold mines). See docs/assumptions.md.
    utility_demand_share: float = 0.55
    #: Ratio of system peak power to average power over the year.
    peak_to_average_ratio: float = 1.42
    #: Aggregate power factor of distribution loads (inductive).
    load_power_factor: float = 0.92
    #: Total technical and commercial losses between generation and the meter.
    #: Split below, because only part of it is inside the modelled network.
    network_loss_fraction: float = 0.185
    #: Losses that the load flow itself computes, i.e. those occurring on the
    #: 225 kV, 150 kV and 33 kV network represented in the catalogue. The
    #: dispatch covers this share; the load flow then reproduces it.
    transmission_loss_fraction: float = 0.040
    voltage_limits_pu: tuple[float, float] = VOLTAGE_LIMITS_PU
    loading_limit_pct: float = LOADING_LIMIT_NORMAL_PCT
    slack_bus: str = "BUS_MANANTALI_225"
    scenario: str = "base"
    notes: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def distribution_loss_fraction(self) -> float:
        """Losses below 33 kV, which the catalogue does not represent.

        Bus demands are grossed up by this share so that the modelled network
        carries the current those losses actually draw. Applying the whole
        loss fraction to the dispatch instead would inject roughly 18 % more
        generation than the modelled network consumes, and the surplus would
        vanish into the slack bus.
        """
        remaining = (1.0 - self.network_loss_fraction) / (1.0 - self.transmission_loss_fraction)
        return max(0.0, 1.0 - remaining)

    def with_(self, **changes) -> "StudyConfig":
        """Return a copy with ``changes`` applied (frozen dataclasses)."""
        from dataclasses import replace

        return replace(self, **changes)


DEFAULT_STUDY = StudyConfig()

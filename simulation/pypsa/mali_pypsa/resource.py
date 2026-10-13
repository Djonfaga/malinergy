"""Solar resource for the Malian photovoltaic fleet.

The intended path is atlite: build an ERA5 cutout over Mali, run its
photovoltaic conversion, and take an hourly capacity factor per plant. That is
the workflow written here, and it is the one that runs on a machine with
Copernicus credentials.

It does not run everywhere. ERA5 comes from the Copernicus Climate Data Store,
which needs an account and is blocked on many institutional networks. Rather
than let that turn into a model that silently does nothing, the resource has a
documented order of preference and every result records which provider
produced it:

1. **atlite / ERA5** — an hourly cutout over the Malian bounding box, converted
   with the CSi panel model. The reference.
2. **The core solar model** — the physically-based clear-sky model from
   ``simulation/core``, already validated against published irradiation for
   Mali (2061 kWh/m2 at Bamako, 2097 at Kayes). Modelled, not measured, and
   labelled as such wherever it is used.

What is never done is to invent a flat capacity factor. A solar plant with a
constant ceiling generates at midnight, and a dispatch model built on that
would show photovoltaic capacity displacing thermal plant in the evening peak,
which is the one thing it cannot do.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from mali_energy.demand.allocation import ZONE_STATION
from mali_energy.grid.schema import GridCatalog

#: Bounding box of Mali, generous enough to cover every plant in the catalogue.
MALI_BOUNDS = {"x": slice(-12.5, -3.5), "y": slice(10.0, 17.5)}

#: Panel and mounting used for the conversion. Utility plants in Mali are
#: crystalline silicon on fixed mounts tilted near the latitude; the azimuth is
#: due south in atlite's convention.
PANEL = "CSi"
DEFAULT_TILT = 13.0
DEFAULT_AZIMUTH = 180.0


@dataclass
class ResourceResult:
    """Hourly capacity factors per plant, with the provider recorded."""

    profiles: dict[str, pd.Series]
    provider: str
    warnings: list[str] = field(default_factory=list)

    @property
    def is_measured(self) -> bool:
        return self.provider.startswith("atlite")

    def summary(self) -> dict:
        return {
            "provider": self.provider,
            "measured": self.is_measured,
            "plants": len(self.profiles),
            "mean_capacity_factor": {
                name: round(float(series.mean()), 4)
                for name, series in sorted(self.profiles.items())
            },
            "annual_full_load_hours": {
                name: int(round(float(series.sum())))
                for name, series in sorted(self.profiles.items())
            },
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# atlite
# ---------------------------------------------------------------------------


def cutout_path(year: int, directory: Path | None = None) -> Path:
    directory = Path(directory or (Path(__file__).resolve().parent.parent / "data" / "cutouts"))
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"mali-era5-{year}.nc"


def atlite_available() -> bool:
    try:
        import atlite  # noqa: F401, PLC0415
    except Exception:  # noqa: BLE001
        return False
    return True


def build_cutout(year: int, *, path: Path | None = None, dx: float = 0.25, dy: float = 0.25):
    """Prepare an ERA5 cutout over Mali.

    Needs a Copernicus Climate Data Store account and a ``~/.cdsapirc``. The
    first call downloads a year of hourly ERA5 over the bounding box, which is
    some hundreds of megabytes and takes a while; afterwards the file is reused.
    """
    import atlite  # noqa: PLC0415

    path = Path(path or cutout_path(year))
    cutout = atlite.Cutout(
        path=str(path),
        module="era5",
        x=MALI_BOUNDS["x"],
        y=MALI_BOUNDS["y"],
        dx=dx,
        dy=dy,
        time=str(year),
    )
    cutout.prepare()
    return cutout


def atlite_capacity_factors(
    catalog: GridCatalog,
    year: int,
    *,
    path: Path | None = None,
    tilt: float = DEFAULT_TILT,
    azimuth: float = DEFAULT_AZIMUTH,
) -> dict[str, pd.Series]:
    """Hourly capacity factor per photovoltaic plant, from an ERA5 cutout.

    Each plant is taken at its own coordinates rather than as a national
    average: Kita, Segou and Sikasso sit in different cloud regimes, and the
    spread between them is what makes a geographically distributed fleet
    smoother than a single site.
    """
    import atlite  # noqa: PLC0415

    path = Path(path or cutout_path(year))
    if not path.exists():
        raise FileNotFoundError(
            f"no cutout at {path}. Build one with build_cutout({year}) on a machine "
            "with Copernicus credentials, or copy the file across."
        )
    cutout = atlite.Cutout(path=str(path))

    profiles: dict[str, pd.Series] = {}
    for generator in catalog.generators.values():
        if generator.technology != "solar":
            continue
        # A one-cell layout at the plant's coordinates: the conversion is run on
        # the grid cell the plant actually sits in.
        capacity_factor = cutout.pv(
            panel=PANEL,
            orientation={"slope": tilt, "azimuth": azimuth},
            shapes=None,
            capacity_factor=True,
        )
        cell = capacity_factor.sel(
            x=generator.longitude, y=generator.latitude, method="nearest"
        )
        series = cell.to_pandas()
        series.index = pd.to_datetime(series.index)
        profiles[generator.id] = series.clip(0.0, 1.0)
    return profiles


# ---------------------------------------------------------------------------
# fallback
# ---------------------------------------------------------------------------


def core_capacity_factors(
    catalog: GridCatalog, year: int, index: pd.DatetimeIndex
) -> dict[str, pd.Series]:
    """Capacity factors from the validated clear-sky model in ``simulation/core``."""
    from mali_energy.solar.pv import design_from_generator, plant_output  # noqa: PLC0415

    profiles: dict[str, pd.Series] = {}
    for generator in catalog.generators.values():
        if generator.technology != "solar":
            continue
        bus = catalog.buses[generator.bus]
        design = design_from_generator(generator, station=ZONE_STATION.get(bus.zone, "Bamako"))
        output = plant_output(design, year)
        series = (output.ac_mw / design.ac_capacity_mw).clip(0.0, 1.0)
        profiles[generator.id] = series.reindex(index).fillna(0.0)
    return profiles


def capacity_factors(
    catalog: GridCatalog,
    year: int,
    index: pd.DatetimeIndex,
    *,
    prefer_atlite: bool = True,
    cutout: Path | None = None,
) -> ResourceResult:
    """Best available hourly capacity factor per plant, provider recorded."""
    warnings: list[str] = []

    if prefer_atlite and atlite_available():
        path = Path(cutout or cutout_path(year))
        if path.exists():
            try:
                profiles = atlite_capacity_factors(catalog, year, path=path)
                aligned = {
                    name: series.reindex(index).interpolate(limit_direction="both").fillna(0.0)
                    for name, series in profiles.items()
                }
                return ResourceResult(profiles=aligned, provider=f"atlite/era5 ({path.name})")
            except Exception as error:  # noqa: BLE001 - reported, not hidden
                warnings.append(f"atlite conversion failed ({error}); falling back")
        else:
            warnings.append(
                f"no ERA5 cutout at {path}. Build one with 'mali-pypsa cutout --year "
                f"{year}' on a machine with Copernicus credentials."
            )
    elif prefer_atlite:
        warnings.append("atlite is not installed; install the 'atlite' extra to use ERA5")

    profiles = core_capacity_factors(catalog, year, index)
    warnings.append(
        "resource is modelled, not measured: clear-sky geometry with the SoDa "
        "Linke turbidity climatology and a monthly cloud factor, validated "
        "against published irradiation for Mali"
    )
    return ResourceResult(profiles=profiles, provider="core/clear-sky", warnings=warnings)


def check_profiles(result: ResourceResult) -> list[str]:
    """Confirm the profiles behave like sunlight."""
    problems = []
    for name, series in result.profiles.items():
        if series.max() > 1.0 + 1e-9 or series.min() < -1e-9:
            problems.append(f"{name}: capacity factor outside 0..1")
        night = series[(series.index.hour >= 21) | (series.index.hour <= 4)]
        if len(night) and float(night.max()) > 0.01:
            problems.append(f"{name}: generates at night, which sunlight does not")
        mean = float(series.mean())
        if not 0.15 < mean < 0.30:
            problems.append(
                f"{name}: mean capacity factor {mean:.3f} outside the 15-30 % range "
                "a Malian plant delivers"
            )
    return problems

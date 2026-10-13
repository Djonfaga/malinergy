"""Annual hourly demand for the single-node model.

The shape comes from the calibrated demand model in ``simulation/core`` — a
daily profile per customer class, a weekly modulation, and a cooling term
filtered through the thermal mass of the building stock, which is what places
the Malian peak at 19:00 rather than at 15:00 when the air is hottest.

What this module has to decide is the *level*, and for a copper-plate model
that decision is not obvious. The core produces three figures:

``utility_energy_gwh``
    What customers consume.
``network_entry_energy_gwh``
    That, plus the losses of the distribution network below 33 kV.
``generation_required_gwh``
    That, plus the losses of the transmission network.

A single-node model has no network, so it cannot compute any losses. If demand
is set to what customers consume, the model quietly generates 18 % less energy
than the system really does, and every fuel bill and emission figure is wrong
by that much. So demand here is **generation required**: losses are inside the
demand because there is nowhere else for them to be, and the model says so.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from mali_energy.config import TIMEZONE, StudyConfig
from mali_energy.demand.allocation import allocate_timeseries
from mali_energy.grid.schema import GridCatalog

from .sampling import downsample


@dataclass
class DemandProfile:
    series_mw: pd.Series
    calibration: dict
    basis: str

    @property
    def annual_energy_gwh(self) -> float:
        return float(self.series_mw.sum() / 1000.0)

    @property
    def peak_mw(self) -> float:
        return float(self.series_mw.max())

    @property
    def load_factor(self) -> float:
        return float(self.series_mw.mean() / self.series_mw.max())

    def summary(self) -> dict:
        peak_at = self.series_mw.idxmax()
        return {
            "basis": self.basis,
            "annual_energy_gwh": round(self.annual_energy_gwh, 1),
            "peak_mw": round(self.peak_mw, 1),
            "peak_timestamp": str(peak_at),
            "peak_hour": int(peak_at.hour),
            "peak_month": int(peak_at.month),
            "minimum_mw": round(float(self.series_mw.min()), 1),
            "mean_mw": round(float(self.series_mw.mean()), 1),
            "load_factor": round(self.load_factor, 3),
            "hours": len(self.series_mw),
        }


def build_demand(
    catalog: GridCatalog,
    config: StudyConfig | None = None,
    *,
    basis: str = "generation_required",
) -> DemandProfile:
    """Total system demand, hourly, for one year.

    ``basis`` selects which of the three levels above the profile is scaled to.
    The default is the only one that balances against generation in a model
    with no network; the others exist so a study can state what it means.
    """
    config = config or StudyConfig()
    allowed = {"generation_required", "network_entry", "utility_served"}
    if basis not in allowed:
        raise ValueError(f"basis must be one of {sorted(allowed)}, not {basis!r}")

    frame, summary = allocate_timeseries(catalog, config)
    shape = frame.sum(axis=1)
    if shape.sum() <= 0:
        raise ValueError("the allocated demand series is empty")

    target_gwh = {
        "generation_required": summary["generation_required_gwh"],
        "network_entry": summary["network_entry_energy_gwh"],
        "utility_served": summary["utility_energy_gwh"],
    }[basis]

    # The allocation already carries the network-entry level; rescale the shape
    # to the requested basis rather than rebuilding it.
    series = shape * (target_gwh * 1000.0 / shape.sum())
    series.name = "demand_mw"

    calibration = dict(summary)
    calibration["basis"] = basis
    calibration["target_gwh"] = round(target_gwh, 1)
    return DemandProfile(series_mw=series, calibration=calibration, basis=basis)


def snapshots(year: int, *, step_hours: int = 1) -> pd.DatetimeIndex:
    """The model's snapshot index, in Malian local time.

    Mali keeps UTC all year with no daylight saving, so local time and the
    solar position never drift apart and an hourly index needs no adjustment.
    """
    index = pd.date_range(
        f"{year}-01-01 00:00", f"{year}-12-31 23:00", freq="h", tz=TIMEZONE
    )
    return index[::step_hours]


def snapshot_weightings(index: pd.DatetimeIndex, *, step_hours: int = 1) -> pd.Series:
    """Hours represented by each snapshot.

    A sampled year must weight its snapshots, or the objective and every energy
    total come out divided by the sampling interval.
    """
    return pd.Series(float(step_hours), index=index)


def monthly_profile(profile: DemandProfile) -> pd.DataFrame:
    """Monthly energy and peak, the resolution a report is written at."""
    series = profile.series_mw
    grouped = series.groupby(series.index.month)
    return pd.DataFrame(
        {
            "energy_gwh": (grouped.sum() / 1000.0).round(1),
            "peak_mw": grouped.max().round(1),
            "mean_mw": grouped.mean().round(1),
        }
    ).rename_axis("month")


def diurnal_profile(profile: DemandProfile) -> pd.Series:
    """Mean demand by hour of day, which is where the evening peak shows."""
    series = profile.series_mw
    return series.groupby(series.index.hour).mean().round(1).rename_axis("hour")


def resample(profile: DemandProfile, index: pd.DatetimeIndex) -> pd.Series:
    """Align a demand profile onto a sampled snapshot index.

    The mean over each interval, not the value at its start: a sampled year
    must carry the same energy as the hourly one it stands for.
    """
    return downsample(profile.series_mw, index)


def check_energy_balance(profile: DemandProfile, tolerance: float = 0.01) -> list[str]:
    """Confirm the profile carries the energy it was calibrated to."""
    target = profile.calibration["target_gwh"]
    actual = profile.annual_energy_gwh
    problems = []
    if abs(actual - target) > tolerance * target:
        problems.append(
            f"profile carries {actual:.0f} GWh against a {target:.0f} GWh target"
        )
    if not 0.5 < profile.load_factor < 0.85:
        problems.append(f"load factor {profile.load_factor:.3f} is outside a credible range")
    peak_at = profile.series_mw.idxmax()
    if not 17 <= peak_at.hour <= 22:
        problems.append(f"system peak at {peak_at.hour}:00 is not an evening peak")
    return problems


def unserved_price_series(index: pd.DatetimeIndex, price: float) -> np.ndarray:
    """A flat price for unserved energy, as an array the optimiser can take."""
    return np.full(len(index), float(price))

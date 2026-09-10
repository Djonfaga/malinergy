"""PVGIS connector — hourly irradiance and PV yield at plant coordinates.

PVGIS v5.2 (JRC) is the reference solar resource for West Africa: SARAH-2
satellite retrievals over the Sahel with ERA5 meteorology, validated against
ground stations. When the service is unreachable the study falls back to the
physically-based clear-sky model in :mod:`mali_energy.solar.resource`, which is
documented as an approximation and flagged in every data card.
"""

from __future__ import annotations

import io

import pandas as pd

from ..cache import FetchError, fetch
from ..config import RAW_DIR

SERIES_API = "https://re.jrc.ec.europa.eu/api/v5_2/seriescalc"
TMY_API = "https://re.jrc.ec.europa.eu/api/v5_2/tmy"
SOURCE_KEY = "pvgis"


def hourly_series(
    latitude: float,
    longitude: float,
    *,
    start_year: int = 2020,
    end_year: int = 2023,
    peak_power_kw: float = 1.0,
    system_loss_pct: float = 14.0,
    tilt: float | None = None,
    azimuth: float = 0.0,
    tracking: int = 0,
    refresh: bool = False,
) -> pd.DataFrame:
    """Hourly PV output and irradiance for one site.

    Parameters
    ----------
    tilt:
        Module tilt in degrees; ``None`` requests the PVGIS optimum, which for
        Malian latitudes lands near the latitude angle.
    azimuth:
        0 = due south in the PVGIS convention.
    tracking:
        0 = fixed, 1 = single-axis horizontal, 2 = two-axis.

    Returns
    -------
    DataFrame indexed by UTC timestamp with ``P`` (W), ``G(i)`` (W/m2),
    ``T2m`` (degC) and ``WS10m`` (m/s).
    """
    params = {
        "lat": f"{latitude:.4f}",
        "lon": f"{longitude:.4f}",
        "startyear": start_year,
        "endyear": end_year,
        "pvcalculation": 1,
        "peakpower": peak_power_kw,
        "loss": system_loss_pct,
        "trackingtype": tracking,
        "aspect": azimuth,
        "outputformat": "csv",
        "browser": 0,
    }
    if tilt is None:
        params["optimalangles"] = 1
    else:
        params["angle"] = tilt

    name = f"pvgis_{latitude:.3f}_{longitude:.3f}_{start_year}_{end_year}_{tracking}.csv"
    cached = fetch(SERIES_API, params=params, filename=name, subdir="pvgis", refresh=refresh)
    return _parse_seriescalc(cached.text)


def _parse_seriescalc(text: str) -> pd.DataFrame:
    """Extract the tabular block from a PVGIS CSV response."""
    lines = text.splitlines()
    try:
        header = next(i for i, line in enumerate(lines) if line.startswith("time,"))
    except StopIteration as exc:
        raise FetchError("unexpected PVGIS payload: no data header found") from exc
    end = header + 1
    while end < len(lines) and lines[end] and not lines[end].startswith(("P50", "\n")):
        if lines[end].strip() == "":
            break
        end += 1
    block = "\n".join(lines[header:end])
    frame = pd.read_csv(io.StringIO(block))
    frame["time"] = pd.to_datetime(frame["time"], format="%Y%m%d:%H%M", utc=True)
    return frame.set_index("time").sort_index()


def typical_year(latitude: float, longitude: float, *, refresh: bool = False) -> pd.DataFrame:
    """Typical meteorological year (8760 h) for a site."""
    params = {
        "lat": f"{latitude:.4f}",
        "lon": f"{longitude:.4f}",
        "outputformat": "csv",
        "browser": 0,
    }
    name = f"pvgis_tmy_{latitude:.3f}_{longitude:.3f}.csv"
    cached = fetch(TMY_API, params=params, filename=name, subdir="pvgis", refresh=refresh)
    lines = cached.text.splitlines()
    header = next(i for i, line in enumerate(lines) if line.startswith("time(UTC)"))
    end = header + 1
    while end < len(lines) and lines[end].strip():
        end += 1
    frame = pd.read_csv(io.StringIO("\n".join(lines[header:end])))
    frame["time(UTC)"] = pd.to_datetime(frame["time(UTC)"], format="%Y%m%d:%H%M", utc=True)
    return frame.set_index("time(UTC)").sort_index()


def available(latitude: float, longitude: float) -> bool:
    """True when a cached PVGIS payload exists for this site."""
    prefix = f"pvgis_{latitude:.3f}_{longitude:.3f}"
    folder = RAW_DIR / "pvgis"
    return folder.exists() and any(p.name.startswith(prefix) for p in folder.glob("*.csv"))

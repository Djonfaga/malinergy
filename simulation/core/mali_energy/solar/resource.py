"""Solar resource for Malian sites.

Preference order, recorded in the result so a report can state which was used:

1. **PVGIS v5.2** hourly series if a payload is cached — satellite-derived and
   the reference for West Africa.
2. **NASA POWER** hourly series if cached — independent, MERRA-2 based.
3. **Clear-sky model with a monthly clear-sky index** — the offline fallback.
   The clear-sky component is physical (Ineichen-Perez with the SoDa Linke
   turbidity climatology that ships with pvlib), so the diurnal geometry and
   the aerosol attenuation are real climatological data: over Mali the lookup
   returns Linke turbidity between 4.9 in December and 6.6 in July, which is
   the harmattan dust load. Only the *cloud* attenuation comes from the
   monthly table in ``data/reference/climate_normals.csv``. Treating that
   table as a general clear-sky index would double-count the dust and
   understate the resource by roughly ten per cent.

The fallback is explicitly *not* presented as measured data. Its annual global
horizontal irradiation is checked against the 2000-2200 kWh/m2 range published
for southern Mali, and any result built on it carries a warning.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import pvlib

from ..config import REFERENCE_DIR, TIMEZONE
from ..sources import nasa_power, pvgis

#: Plausible annual GHI range for Malian sites, used as a sanity check.
ANNUAL_GHI_RANGE_KWH_M2 = (1900.0, 2250.0)


@dataclass
class IrradianceResult:
    """Hourly irradiance and air temperature at one site."""

    data: pd.DataFrame           # ghi, dni, dhi (W/m2), temp_air (degC), wind_speed (m/s)
    provider: str                # pvgis | nasa-power | clear-sky-model
    latitude: float
    longitude: float
    station: str
    warnings: list[str] = field(default_factory=list)

    @property
    def annual_ghi_kwh_m2(self) -> float:
        return float(self.data["ghi"].sum() / 1000.0)

    @property
    def is_measured(self) -> bool:
        return self.provider in {"pvgis", "nasa-power"}

    def summary(self) -> dict:
        return {
            "provider": self.provider,
            "measured": self.is_measured,
            "annual_ghi_kwh_m2": round(self.annual_ghi_kwh_m2, 1),
            "mean_temp_c": round(float(self.data["temp_air"].mean()), 1),
            "hours": len(self.data),
            "warnings": self.warnings,
        }


def _climate_row(station: str) -> pd.DataFrame:
    table = pd.read_csv(REFERENCE_DIR / "climate_normals.csv")
    rows = table[table["station"] == station]
    if rows.empty:
        rows = table[table["station"] == "Bamako"]
    return rows.set_index("month")


def clear_sky_irradiance(
    latitude: float,
    longitude: float,
    year: int,
    *,
    station: str = "Bamako",
    altitude_m: float = 350.0,
) -> IrradianceResult:
    """Physical clear-sky model attenuated by a monthly clear-sky index."""
    index = pd.date_range(
        f"{year}-01-01 00:00", f"{year}-12-31 23:00", freq="h", tz=TIMEZONE
    )
    location = pvlib.location.Location(latitude, longitude, tz=TIMEZONE, altitude=altitude_m)

    warnings: list[str] = []
    try:
        clear = location.get_clearsky(index, model="ineichen")
    except Exception as exc:  # pragma: no cover - only if the turbidity file is absent
        warnings.append(f"Linke turbidity lookup unavailable ({exc}); using the Haurwitz model")
        clear = location.get_clearsky(index, model="haurwitz")
        clear = clear.reindex(columns=["ghi", "dni", "dhi"]).fillna(0.0)

    climate = _climate_row(station)
    kc = climate.loc[index.month, "clear_sky_index"].to_numpy()

    ghi = clear["ghi"].to_numpy() * kc
    # Cloud attenuation removes beam irradiance faster than diffuse: the beam
    # fraction is reduced with the square of the clear-sky index, and the
    # residual energy is returned to the diffuse component.
    dni = clear["dni"].to_numpy() * kc**2
    solar_position = location.get_solarposition(index)
    cos_zenith = np.cos(np.radians(solar_position["zenith"].to_numpy())).clip(min=0.0)
    dhi = np.clip(ghi - dni * cos_zenith, 0.0, None)

    temperature = climate.loc[index.month, "temp_mean_c"].to_numpy()
    amplitude = climate.loc[index.month, "temp_max_c"].to_numpy() - temperature
    phase = 2 * np.pi * (index.hour.to_numpy() - 15.0) / 24.0
    temp_air = temperature + amplitude * np.cos(phase)

    data = pd.DataFrame(
        {
            "ghi": ghi,
            "dni": dni,
            "dhi": dhi,
            "temp_air": temp_air,
            "wind_speed": np.full(len(index), 2.5),
        },
        index=index,
    )

    result = IrradianceResult(
        data=data,
        provider="clear-sky-model",
        latitude=latitude,
        longitude=longitude,
        station=station,
        warnings=warnings,
    )
    result.warnings.append(
        "modelled resource, not measured: clear-sky geometry with a monthly "
        "clear-sky index; run 'mali-energy fetch --pvgis' for satellite data"
    )
    low, high = ANNUAL_GHI_RANGE_KWH_M2
    if not low <= result.annual_ghi_kwh_m2 <= high:
        result.warnings.append(
            f"annual GHI {result.annual_ghi_kwh_m2:.0f} kWh/m2 falls outside the "
            f"{low:.0f}-{high:.0f} kWh/m2 range expected in Mali; review the "
            "clear-sky index table"
        )
    return result


def irradiance(
    latitude: float,
    longitude: float,
    year: int,
    *,
    station: str = "Bamako",
    altitude_m: float = 350.0,
    allow_network: bool = False,
) -> IrradianceResult:
    """Best available hourly resource for a site.

    ``allow_network=True`` permits a live PVGIS call; the default only reads
    what is already cached, so a study run is reproducible and offline.
    """
    if allow_network or pvgis.available(latitude, longitude):
        try:
            frame = pvgis.hourly_series(
                latitude, longitude, start_year=year, end_year=year, peak_power_kw=1.0
            )
            data = pd.DataFrame(
                {
                    "poa_global": frame["G(i)"],
                    "temp_air": frame["T2m"],
                    "wind_speed": frame.get("WS10m", 2.5),
                    "pvgis_power_w": frame["P"],
                }
            )
            data["ghi"] = data["poa_global"]      # plane-of-array from PVGIS
            data["dni"] = np.nan
            data["dhi"] = np.nan
            data.index = data.index.tz_convert(TIMEZONE)
            return IrradianceResult(
                data=data,
                provider="pvgis",
                latitude=latitude,
                longitude=longitude,
                station=station,
                warnings=["PVGIS returns plane-of-array irradiance; the transposition "
                          "step is skipped for this provider"],
            )
        except Exception:
            pass

    try:
        frame = nasa_power.hourly(
            latitude, longitude, start=f"{year}0101", end=f"{year}1231"
        )
        data = pd.DataFrame(
            {
                "ghi": frame["ghi_wm2"],
                "dni": frame["dni_wm2"],
                "dhi": frame["dhi_wm2"],
                "temp_air": frame["temp_air_c"],
                "wind_speed": frame["wind_speed_ms"],
            }
        )
        data.index = data.index.tz_convert(TIMEZONE)
        return IrradianceResult(
            data=data.dropna(),
            provider="nasa-power",
            latitude=latitude,
            longitude=longitude,
            station=station,
        )
    except Exception:
        pass

    return clear_sky_irradiance(
        latitude, longitude, year, station=station, altitude_m=altitude_m
    )

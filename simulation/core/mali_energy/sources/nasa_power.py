"""NASA POWER connector — hourly meteorology, used as an independent check.

Having a second irradiance source matters for the article: the spread between
PVGIS/SARAH-2 and POWER/MERRA-2 over the Sahel is a real uncertainty band, and
quoting a PV yield without it would overstate precision.
"""

from __future__ import annotations

import pandas as pd

from ..cache import fetch

API = "https://power.larc.nasa.gov/api/temporal/hourly/point"
SOURCE_KEY = "nasa-power"

PARAMETERS = {
    "ALLSKY_SFC_SW_DWN": "ghi_wm2",
    "ALLSKY_SFC_SW_DNI": "dni_wm2",
    "ALLSKY_SFC_SW_DIFF": "dhi_wm2",
    "T2M": "temp_air_c",
    "WS10M": "wind_speed_ms",
    "RH2M": "relative_humidity_pct",
}


def hourly(
    latitude: float,
    longitude: float,
    *,
    start: str = "20200101",
    end: str = "20231231",
    refresh: bool = False,
) -> pd.DataFrame:
    """Hourly meteorology for one point, indexed in UTC."""
    params = {
        "parameters": ",".join(PARAMETERS),
        "community": "RE",
        "longitude": f"{longitude:.4f}",
        "latitude": f"{latitude:.4f}",
        "start": start,
        "end": end,
        "format": "JSON",
    }
    name = f"power_{latitude:.3f}_{longitude:.3f}_{start}_{end}.json"
    cached = fetch(API, params=params, filename=name, subdir="nasa_power", refresh=refresh)
    payload = cached.json()
    series = payload["properties"]["parameter"]

    frame = pd.DataFrame({PARAMETERS[k]: pd.Series(v) for k, v in series.items() if k in PARAMETERS})
    frame.index = pd.to_datetime(frame.index, format="%Y%m%d%H", utc=True)
    return frame.sort_index().replace(-999.0, pd.NA).astype(float)

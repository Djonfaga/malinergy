"""World Bank WDI connector — sector indicators used for calibration and context.

The API is not reachable from every network. When it is not, the loader falls
back to the committed snapshot and records the fact in the data card rather
than inventing values.
"""

from __future__ import annotations

import json

import pandas as pd

from ..cache import FetchError, fetch
from ..config import ISO3, SNAPSHOT_DIR

API = "https://api.worldbank.org/v2/country/{iso}/indicator/{indicator}"
SNAPSHOT = SNAPSHOT_DIR / "worldbank_mali.csv"
SOURCE_KEY = "worldbank-wdi"

#: Indicators pulled for the study.
INDICATORS = {
    "EG.ELC.ACCS.ZS": "access_electricity_pct",
    "EG.ELC.ACCS.RU.ZS": "access_electricity_rural_pct",
    "EG.ELC.ACCS.UR.ZS": "access_electricity_urban_pct",
    "EG.ELC.LOSS.ZS": "transmission_distribution_losses_pct",
    "EG.USE.ELEC.KH.PC": "electric_power_consumption_kwh_per_capita",
    "EG.ELC.RNEW.ZS": "renewable_electricity_output_pct",
    "SP.POP.TOTL": "population",
    "SP.URB.TOTL.IN.ZS": "urban_population_pct",
    "NY.GDP.MKTP.CD": "gdp_current_usd",
}


def download(refresh: bool = False) -> pd.DataFrame:
    """Query the WDI API for every indicator and return a tidy frame."""
    frames = []
    for indicator, column in INDICATORS.items():
        cached = fetch(
            API.format(iso=ISO3, indicator=indicator),
            params={"format": "json", "per_page": "500"},
            filename=f"wdi_{indicator}.json",
            subdir="worldbank",
            refresh=refresh,
        )
        payload = json.loads(cached.text)
        if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
            continue
        records = [
            {"year": int(row["date"]), column: row["value"]}
            for row in payload[1]
            if row.get("value") is not None
        ]
        if records:
            frames.append(pd.DataFrame(records).set_index("year"))

    if not frames:
        raise FetchError("no World Bank indicator returned data")
    return pd.concat(frames, axis=1).sort_index().reset_index()


def write_snapshot(refresh: bool = False) -> pd.DataFrame:
    frame = download(refresh=refresh)
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(SNAPSHOT, index=False)
    return frame


def load() -> pd.DataFrame:
    """Return the indicator table, or an empty frame if it was never fetched."""
    if SNAPSHOT.exists():
        return pd.read_csv(SNAPSHOT)
    try:
        return write_snapshot()
    except FetchError:
        return pd.DataFrame(columns=["year", *INDICATORS.values()])


def indicator(name: str, year: int) -> float | None:
    """Return one indicator for one year, or ``None`` when unavailable."""
    frame = load()
    if frame.empty or name not in frame.columns:
        return None
    row = frame[frame["year"] == year]
    if row.empty or pd.isna(row.iloc[0][name]):
        return None
    return float(row.iloc[0][name])

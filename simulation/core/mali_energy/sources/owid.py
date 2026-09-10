"""Our World in Data energy dataset — national electricity balance for Mali.

This is the calibration anchor of the whole study: annual generation by
technology, demand, and population, 1980 to the latest available year.
The upstream compilation draws on Ember and the Energy Institute Statistical
Review, both of which report Mali's utility-scale electricity.
"""

from __future__ import annotations

import pandas as pd

from ..cache import fetch
from ..config import ISO3, SNAPSHOT_DIR

DATASET_URL = "https://raw.githubusercontent.com/owid/energy-data/master/owid-energy-data.csv"
CODEBOOK_URL = "https://raw.githubusercontent.com/owid/energy-data/master/owid-energy-codebook.csv"
SNAPSHOT = SNAPSHOT_DIR / "owid_energy_mali.csv"
SOURCE_KEY = "owid-energy"

#: Columns retained for the Malian snapshot (TWh unless stated otherwise).
COLUMNS = [
    "year",
    "population",
    "gdp",
    "electricity_generation",
    "electricity_demand",
    "electricity_demand_per_capita",
    "hydro_electricity",
    "solar_electricity",
    "wind_electricity",
    "oil_electricity",
    "gas_electricity",
    "coal_electricity",
    "biofuel_electricity",
    "fossil_electricity",
    "renewables_electricity",
    "low_carbon_electricity",
    "net_elec_imports",
    "carbon_intensity_elec",
    "renewables_share_elec",
]


def download(refresh: bool = False) -> pd.DataFrame:
    """Fetch the full OWID file and return the Malian rows."""
    cached = fetch(DATASET_URL, filename="owid-energy-data.csv", subdir="owid", refresh=refresh)
    frame = pd.read_csv(cached.path, low_memory=False)
    mali = frame[frame["iso_code"] == ISO3].copy()
    keep = [c for c in COLUMNS if c in mali.columns]
    mali = mali[keep].sort_values("year").reset_index(drop=True)
    return mali


def write_snapshot(refresh: bool = False) -> pd.DataFrame:
    """Refresh the committed Malian extract used for offline builds."""
    mali = download(refresh=refresh)
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    mali.to_csv(SNAPSHOT, index=False)
    return mali


def load() -> pd.DataFrame:
    """Return the Malian electricity balance, preferring the committed snapshot."""
    if SNAPSHOT.exists():
        return pd.read_csv(SNAPSHOT)
    return write_snapshot()


def balance(year: int) -> dict[str, float]:
    """Electricity balance of a single year, in TWh, plus derived quantities.

    Raises
    ------
    KeyError
        If the requested year is not present in the dataset, listing the range
        that is — silently falling back to another year would corrupt a study.
    """
    frame = load()
    row = frame[frame["year"] == year]
    if row.empty:
        span = f"{int(frame['year'].min())}-{int(frame['year'].max())}"
        raise KeyError(f"year {year} absent from the OWID extract (available: {span})")
    record = row.iloc[0].to_dict()

    generation = float(record.get("electricity_generation") or 0.0)
    demand = float(record.get("electricity_demand") or 0.0)
    record["average_demand_mw"] = demand * 1e6 / 8760.0 if demand else 0.0
    record["average_generation_mw"] = generation * 1e6 / 8760.0 if generation else 0.0
    record["hydro_share"] = _share(record.get("hydro_electricity"), generation)
    record["solar_share"] = _share(record.get("solar_electricity"), generation)
    record["thermal_share"] = _share(record.get("fossil_electricity"), generation)
    return record


def _share(value, total: float) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0
    return value / total if total else 0.0

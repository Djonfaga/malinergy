"""Population series and coordinates of Malian load centres.

Two mirrors are used because they are reachable from restricted networks:
World Bank population through the Frictionless data package, and the GeoNames
gazetteer through the ``datasets/world-cities`` mirror. Coordinates for the
towns that carry the interconnected network are committed under
``data/reference/load_centres.csv`` so a build never depends on either.
"""

from __future__ import annotations

import pandas as pd

from ..cache import fetch
from ..config import COUNTRY, SNAPSHOT_DIR

POPULATION_URL = "https://raw.githubusercontent.com/datasets/population/main/data/population.csv"
CITIES_URL = "https://raw.githubusercontent.com/datasets/world-cities/main/data/world-cities.csv"
CITY_COORDS_URL = (
    "https://raw.githubusercontent.com/bahar/WorldCityLocations/master/"
    "World_Cities_Location_table.csv"
)

POPULATION_SNAPSHOT = SNAPSHOT_DIR / "population_mali.csv"
CITIES_SNAPSHOT = SNAPSHOT_DIR / "cities_mali.csv"


def download_population(refresh: bool = False) -> pd.DataFrame:
    cached = fetch(POPULATION_URL, filename="population.csv", subdir="population", refresh=refresh)
    frame = pd.read_csv(cached.path)
    country_col = "Country Code" if "Country Code" in frame.columns else "country_code"
    year_col = "Year" if "Year" in frame.columns else "year"
    value_col = "Value" if "Value" in frame.columns else "value"
    mali = frame[frame[country_col] == "MLI"][[year_col, value_col]]
    mali.columns = ["year", "population"]
    return mali.sort_values("year").reset_index(drop=True)


def download_cities(refresh: bool = False) -> pd.DataFrame:
    """Malian populated places with coordinates, from the GeoNames mirrors."""
    names = pd.read_csv(
        fetch(CITIES_URL, filename="world-cities.csv", subdir="population", refresh=refresh).path
    )
    mali = names[names["country"] == COUNTRY].copy()

    coords = pd.read_csv(
        fetch(
            CITY_COORDS_URL,
            filename="world-city-locations.csv",
            subdir="population",
            refresh=refresh,
        ).path,
        header=None,
        names=["id", "country", "city", "latitude", "longitude", "altitude"],
        on_bad_lines="skip",
    )
    coords = coords[coords["country"].astype(str).str.strip() == COUNTRY]
    coords["key"] = coords["city"].astype(str).str.strip().str.lower()
    mali["key"] = mali["name"].astype(str).str.strip().str.lower()

    merged = mali.merge(
        coords[["key", "latitude", "longitude"]].drop_duplicates("key"), on="key", how="left"
    )
    return merged.drop(columns=["key"]).reset_index(drop=True)


def write_snapshots(refresh: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    pop = download_population(refresh=refresh)
    pop.to_csv(POPULATION_SNAPSHOT, index=False)
    cities = download_cities(refresh=refresh)
    cities.to_csv(CITIES_SNAPSHOT, index=False)
    return pop, cities


def load_population() -> pd.DataFrame:
    if POPULATION_SNAPSHOT.exists():
        return pd.read_csv(POPULATION_SNAPSHOT)
    return write_snapshots()[0]


def load_cities() -> pd.DataFrame:
    if CITIES_SNAPSHOT.exists():
        return pd.read_csv(CITIES_SNAPSHOT)
    return write_snapshots()[1]

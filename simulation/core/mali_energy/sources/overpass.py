"""OpenStreetMap / Overpass connector — as-built power infrastructure of Mali.

OSM coverage of Malian transmission is partial but real: it carries the 225 kV
corridors, most substations and the large plants. The study uses it for two
purposes only, both stated in the reports: cross-checking the geometry (and
therefore the length) of the lines in the reference catalogue, and locating
substations that the catalogue would otherwise place by hand.
"""

from __future__ import annotations

import json

import pandas as pd

from ..cache import fetch

ENDPOINT = "https://overpass-api.de/api/interpreter"
SOURCE_KEY = "osm"

QUERY = """
[out:json][timeout:180];
area["ISO3166-1"="ML"][admin_level=2]->.mali;
(
  way["power"="line"](area.mali);
  way["power"="minor_line"]["voltage"~"^(3[0-9]|[4-9][0-9]|[1-9][0-9]{2,})000$"](area.mali);
  node["power"="substation"](area.mali);
  way["power"="substation"](area.mali);
  node["power"="plant"](area.mali);
  way["power"="plant"](area.mali);
  relation["power"="plant"](area.mali);
  node["power"="generator"](area.mali);
);
out center tags;
"""


def download(refresh: bool = False) -> dict:
    cached = fetch(
        ENDPOINT,
        params={"data": QUERY},
        filename="osm_power_mali.json",
        subdir="osm",
        refresh=refresh,
    )
    return json.loads(cached.text)


def to_frame(refresh: bool = False) -> pd.DataFrame:
    """Flatten the Overpass answer into one row per element."""
    payload = download(refresh=refresh)
    rows = []
    for element in payload.get("elements", []):
        tags = element.get("tags", {})
        centre = element.get("center", {})
        rows.append(
            {
                "osm_type": element.get("type"),
                "osm_id": element.get("id"),
                "power": tags.get("power"),
                "name": tags.get("name"),
                "operator": tags.get("operator"),
                "voltage_v": tags.get("voltage"),
                "cables": tags.get("cables"),
                "circuits": tags.get("circuits"),
                "source_tag": tags.get("source"),
                "plant_source": tags.get("plant:source") or tags.get("generator:source"),
                "plant_output_mw": tags.get("plant:output:electricity")
                or tags.get("generator:output:electricity"),
                "latitude": element.get("lat", centre.get("lat")),
                "longitude": element.get("lon", centre.get("lon")),
            }
        )
    return pd.DataFrame(rows)

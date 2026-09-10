# Data sources

Every source referenced by the `source` column of a reference table is
registered in `mali_energy/provenance.py`. The loader raises on an unknown key,
so this list and the code cannot drift apart.

## Retrieved automatically

| Key | What it provides | Endpoint | Licence |
|---|---|---|---|
| `owid-energy` | National electricity generation, demand and mix, 1980-2024 | `raw.githubusercontent.com/owid/energy-data` | CC BY 4.0 |
| `worldbank-population` | Population series | `raw.githubusercontent.com/datasets/population` | CC BY 4.0 |
| `geonames` | Coordinates of Malian towns | `raw.githubusercontent.com/datasets/world-cities` | CC BY 4.0 |
| `worldbank-wdi` | Access rate, network losses, consumption per capita | `api.worldbank.org` | CC BY 4.0 |
| `pvgis` | Hourly irradiance and photovoltaic yield | `re.jrc.ec.europa.eu/api/v5_2` | free reuse |
| `nasa-power` | Independent hourly irradiance and temperature | `power.larc.nasa.gov` | public domain |
| `osm` | As-built lines, substations and plants | `overpass-api.de` | ODbL 1.0 |

`mali-energy fetch` writes every payload to `data/raw/` next to a
`.meta.json` recording the URL, retrieval time and SHA-256. `mali-energy
inventory` prints that ledger. Downstream code never touches the network
unless asked, so a run is reproducible.

### When a source is unreachable

Restricted networks commonly block the World Bank, PVGIS, NASA POWER and
Overpass endpoints. The behaviour is then, in order of preference and always
recorded in the data card:

1. use the committed snapshot in `data/snapshots/`;
2. fall back to a documented model, as the solar resource does;
3. omit the check and say so, as the validation step does when the OWID
   snapshot is missing.

Nothing is silently invented. To populate the cache from an unrestricted
machine, run `mali-energy fetch --pvgis --refresh` there and copy `data/raw/`
across.

## Curated by hand

The network catalogue in `data/reference/` was assembled from OMVS, WAPP,
EDM-SA and IRENA publications. Each row carries its own `source` and
`confidence`. Rows marked `estimated` are engineering judgement and are listed
individually in `verification_checklist.md`.

## Citing this dataset

`mali-energy validate` prints a data card with a bibliography built from the
sources actually used in the build. That output is the citation block for any
figure taken from this repository.

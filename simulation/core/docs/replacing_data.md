# Replacing the placeholder data with measured figures

Everything in this repository is built so that better data changes the numbers
and not the code. This is how to do it.

## The principle

Every row of every reference table carries two columns:

- `source` — a key registered in `mali_energy/provenance.py`;
- `confidence` — one of `measured`, `reported`, `derived`, `estimated`.

The loader **refuses** a row with either field empty. `mali-energy validate`
prints a data card showing the mix, and `mali-energy gaps` lists every row still
marked `estimated`, grouped by table, with the note explaining what it stands
for. Working down that list is the whole task.

## Finding what to replace

```bash
cd simulation/core
mali-energy gaps                 # every estimated row, grouped
mali-energy gaps --table plants  # just one table
mali-energy validate             # the data card and the current mix
```

`docs/verification_checklist.md` orders the same material by how much it
changes the conclusions. The six entries at the top are the ones worth chasing
first; the rest move individual results, not the argument.

## Replacing a value

1. **Edit the CSV in `data/reference/`.** They are plain comma-separated files,
   one row per object, designed to be opened in a spreadsheet.
2. **Change `confidence`** from `estimated` to `reported` or `measured`.
3. **Change `source`** to the document it came from. If the source is new, add
   it to `SOURCES` in `mali_energy/provenance.py` — the loader raises on an
   unregistered key, which is what keeps the bibliography honest.
4. **Put the reference in `note`**: the report, the page, the date.

Nothing else needs touching. Line impedances are recomputed from the conductor
and tower, lengths from the coordinates, demand from the national energy
series, and every downstream study reads the rebuilt case.

## Re-running everything

```bash
cd simulation/core
mali-energy validate             # catches an inconsistent edit before it spreads
mali-energy build                # rewrites build/mali_case.json
pytest                           # 32 checks on physics, calibration and schema

cd ../pandapower   && mali-pandapower --studies all && pytest
cd ../pandapipes   && mali-pandapipes --studies all && pytest
cd ../openmodelica && mali-openmodelica --studies all && pytest
cd ../simscape     && mali-simscape --studies all && pytest
cd ../powerfactory && mali-powerfactory --output build && pytest
cd ../benchmark    && mali-benchmark --sections all && pytest
```

The tests are the safety net. Several of them assert *behaviour* rather than
numbers — that the system peak falls in the evening, that the wet season loses
more in transport than the dry, that photovoltaic yield lands in the range
published for Mali — so a replacement that is entered in the wrong unit or the
wrong column tends to fail a test rather than quietly shift a conclusion.

## What each table holds

| File | One row per | Replace it with |
|---|---|---|
| `buses.csv` | busbar | EDM-SA single-line diagram |
| `lines.csv` | corridor | line schedule: conductor, circuits, published length |
| `transformers.csv` | transformer bank | nameplates |
| `plants.csv` | power station | EDM-SA generation register, OMVS allocation key |
| `loads.csv` | load centre | EDM-SA sales by commercial centre |
| `shunts.csv` | capacitor bank | substation equipment list |
| `interconnections.csv` | border link | interconnection contracts, WAPP exchange data |
| `hydro_availability.csv` | plant and month | OMVS operating records or gauged discharge |
| `climate_normals.csv` | station and month | Mali-Meteo records, or `mali-energy fetch --pvgis` |
| `load_classes.csv` | customer class | SCADA load curves from the control centre |

## Two parameters that are not in a table

Both live in `StudyConfig` in `mali_energy/config.py` and both matter more than
most rows:

- **`utility_demand_share`** (0.55). The share of national electricity served by
  the interconnected network, the rest being isolated centres and captive
  industrial generation. Replace with EDM-SA energy sold plus losses. Every
  megawatt in the study scales with it.
- **`transmission_loss_fraction`** (0.040) within `network_loss_fraction`
  (0.185). Only the first is inside the modelled network; the second covers
  everything below 33 kV. Replace with EDM-SA loss statistics by voltage level.

Change them on the command line or in a script rather than editing the file:

```python
from mali_energy import StudyConfig, build_all_cases
config = StudyConfig(year=2024, utility_demand_share=0.61)
cases = build_all_cases(config=config)
```

## Fetching the sources that need an open network

PVGIS, NASA POWER, the World Bank API and the OpenStreetMap Overpass endpoint
are blocked on many corporate and institutional networks. From an unrestricted
machine:

```bash
mali-energy fetch --pvgis --refresh
```

then copy `data/raw/` across. Every payload is cached with its URL, retrieval
time and SHA-256; `mali-energy inventory` prints the ledger. Once a PVGIS series
exists for a plant, the solar model uses it and stops reporting the clear-sky
fallback.

## If a replacement breaks something

That is the system working. The validation and the tests encode what the
Malian system can physically be: a capacity factor above 85 %, a line reactance
outside 0.01 to 1 Ω/km, an inverter plant with rotating inertia, load weights
that do not sum to one — each is refused with a message naming the row. Read
the message, check the unit, and if the data really does say what it says, the
check is the thing that needs changing, and it should be changed deliberately.

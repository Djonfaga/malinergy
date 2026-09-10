# Mali energy simulation — canonical data layer

This package builds the dataset that every simulation branch of this
repository consumes. Its purpose is to make a five-tool comparison honest: if
PowerFactory, OpenModelica, pandapower, pandapipes and Simscape Electrical
each start from their own transcription of a one-line diagram, differences in
their results say nothing about the tools. Here they all read one file.

```
data/reference/*.csv          curated network catalogue, one source per row
        |
        |  mali_energy.grid.catalog   (+ derived line impedances)
        v
   GridCatalog  ------------------> build/mali_network.json
        |
        |  + demand allocation  (OWID national energy x utility share x bus weight x shape)
        |  + solar production   (PVGIS if cached, else a physical clear-sky model)
        |  + merit-order dispatch
        v
   four operating points --------> build/mali_case.json     <- read by every tool
```

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e simulation/core[dev,plots]
```

## Use

```bash
mali-energy fetch                # download and cache the external datasets
mali-energy fetch --pvgis        # add satellite solar series per plant
mali-energy validate             # check the catalogue before trusting it
mali-energy build                # write build/mali_network.json and build/mali_case.json
mali-energy case dry_peak        # print one operating point
mali-energy inventory            # checksums of everything downloaded
pytest simulation/core           # 32 checks on physics, calibration and schema
```

## The four operating points

| Case | When | Why it is in the study |
|---|---|---|
| `dry_peak` | April, 20:00 | Hydro at its annual floor, no sun, cooling demand at its maximum. The hour the system is planned for, and the hour it fails. |
| `wet_peak` | September, 20:00 | Hydro at its ceiling. Shows how much of the Malian problem is seasonal rather than structural. |
| `solar_noon` | April, 13:00 | Maximum photovoltaic infeed. Sets the curtailment, voltage-rise and reserve questions. |
| `night_min` | August, 04:00 | Minimum load. Sets reactive absorption and minimum-stable-generation limits. |

Running `mali-energy build` on the committed data gives, for 2024:

| Case | Demand MW | Hydro | Solar | Thermal | Imports | Unserved |
|---|---|---|---|---|---|---|
| dry_peak | 487 | 74 | 0 | 245 | 90 | 188 |
| wet_peak | 391 | 253 | 0 | 137 | 90 | 0 |
| solar_noon | 425 | 74 | 60 | 245 | 90 | 53 |
| night_min | 222 | 227 | 0 | 30 | 16 | 0 |

The 188 MW deficit in the dry-season evening is not a modelling artefact. It
is the load shedding Malian consumers experience, reproduced from published
capacity, published river seasonality and a demand level calibrated on
measured national energy.

## What is measured and what is modelled

The distinction is enforced in code, not left to the reader. Every record
carries a `source` and a `confidence` in `{measured, reported, derived,
estimated}`, the catalogue refuses to load a row without them, and every build
emits a data card listing the mix.

**Measured or reported**
- National electricity balance 1980-2024 — Our World in Data, compiled from
  Ember and the Energy Institute. Anchors the demand level.
- Population and populated places — World Bank and GeoNames mirrors.
- Linke turbidity climatology — SoDa, shipped with pvlib. Carries the real
  harmattan aerosol load (4.9 in December to 6.6 in July over Bamako).
- Plant capacities, commissioning dates and the 225 kV corridors — OMVS, WAPP
  and EDM-SA publications.

**Derived**
- Every line impedance, computed from the conductor and tower geometry in
  `mali_energy.grid.electrical` rather than copied from a table.
- Line lengths, from bus coordinates and a documented route factor.
- Line ampacities, derated for Sahelian ambient temperature via a simplified
  IEEE 738 heat balance.

**Estimated and flagged**
- Distribution-level topology inside Bamako, transformer impedances, load
  weights between towns, hydro seasonality, and the monthly cloud factors.
  These are engineering estimates. `docs/verification_checklist.md` lists each
  one with the document that would settle it.

## Design decisions worth knowing before quoting a number

- **The OMVS share.** Manantali, Gouina and Felou are shared between Mali,
  Senegal and Mauritania. The dispatch gives Mali 52 % of them. Treating the
  full 400 MW as Malian is the largest single error available in a study of
  this system, and it flatters the dry-season balance by roughly 190 MW.
- **The utility share.** The national figure includes captive generation, in
  particular the gold mines running their own diesel plant off-grid. The
  interconnected network is credited with 55 % of national demand, a parameter
  in `StudyConfig`, not a hard-coded constant. The validation step reports the
  capacity factor this implies, so an implausible setting is visible.
- **The evening peak.** Cooling load is driven by an effective temperature
  filtered through a four-hour building time constant. Without that lag the
  modelled peak moves to 15:00, which is when the air is hottest and not when
  the system actually peaks.
- **Dust is counted once.** Aerosol attenuation lives in the Linke turbidity
  climatology; the monthly factor in `climate_normals.csv` is cloud only.
  Applying a general clear-sky index on top double-counts dust and understates
  the resource by about ten per cent.

## Layout

```
mali_energy/
  config.py         paths, constants, StudyConfig
  provenance.py     source registry, confidence levels, data cards
  cache.py          HTTP fetch with checksums, offline by default
  sources/          OWID, World Bank, population, PVGIS, NASA POWER, Overpass
  grid/
    schema.py       Bus, Line, Transformer, Generator, Load, GridCatalog
    electrical.py   conductor library, impedance and ampacity derivation
    catalog.py      strict loader for data/reference
    validation.py   consistency and plausibility checks
  demand/           hourly profiles and allocation of national energy to buses
  solar/            resource selection and photovoltaic plant model
  exchange.py       the four operating points and the exchange file
  cli.py            mali-energy
```

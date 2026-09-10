# Verification checklist

Every record marked `estimated` in the catalogue is listed here with the
document that would replace it with a measured value. The intent is that an
engineer with access to EDM-SA, OMVS or CREE material can work down this list
and lift the study from *plausible* to *verified*.

Run `mali-energy validate` to see the current count.

## Highest priority — these change the conclusions

| Item | Where | Settled by |
|---|---|---|
| Utility share of national demand | `StudyConfig.utility_demand_share` | EDM-SA annual report: energy sold plus losses |
| Malian share of the OMVS plants | `plants.csv`, `mali_share` | SOGEM allocation key for the study year |
| Hydro monthly availability | `hydro_availability.csv` | OMVS operating records or gauged discharge |
| Bamako thermal capacity and unit counts | `plants.csv` | EDM-SA generation register |
| Load weights per commercial centre | `loads.csv` | EDM-SA sales statistics by centre |
| Contracted import from Cote d'Ivoire | `interconnections.csv` | The interconnection contract or WAPP exchange data |

## Network data

| Item | Where | Settled by |
|---|---|---|
| Bamako 33 kV topology | `buses.csv`, `lines.csv` | EDM-SA distribution one-line diagram |
| Conductor types per corridor | `lines.csv` | OMVS and WAPP construction records |
| Published line lengths | `lines.csv`, `length_km` | Line schedules; the derived values can then be retired |
| Transformer impedances and vector groups | `transformers.csv` | Nameplates |
| Whether the Segou-Mopti 225 kV line is energised | `lines.csv` | EDM-SA or WAPP status report |
| Substation earthing and zero-sequence data | `electrical.py` defaults | Protection setting files |

## Generation data

| Item | Where | Settled by |
|---|---|---|
| Inertia constants and subtransient reactances | `plants.csv` | Machine test reports; matters for the dynamic branches |
| Governor droop settings | `plants.csv` | Control centre settings |
| Minimum stable generation per unit | `plants.csv` | Operating instructions |
| Photovoltaic plant design (tilt, DC/AC, tracking) | `solar/pv.py` defaults | Plant technical description |

## Resource data

| Item | Where | Settled by |
|---|---|---|
| Monthly cloud factors | `climate_normals.csv` | `mali-energy fetch --pvgis`, which replaces the model entirely |
| Temperature normals | `climate_normals.csv` | Mali-Meteo station records |
| Soiling losses | `solar/pv.py` | Plant performance-ratio records |

## How to record a verification

Replace the value, change `confidence` from `estimated` to `reported` or
`measured`, and put the document reference in `source` — adding a new entry to
`SOURCES` in `provenance.py` if needed. Re-run `mali-energy validate`; the data
card will show the improved mix, and the warning count will fall.

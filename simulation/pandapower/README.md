# pandapower — Malian interconnected network

Steady-state studies of the network described in `simulation/core`. This branch
adds no engineering assumptions of its own: it reads `build/mali_case.json`,
translates it into pandapower objects, and reports what the solver finds.

```bash
pip install -e simulation/core -e simulation/pandapower
mali-energy build                        # produce the exchange file
mali-pandapower --studies all            # load flow, N-1, short circuit, year, hosting
pytest simulation/pandapower             # 20 checks
```

## What the studies find

### Load flow, four operating points

| Case | Demand MW | Shed MW | Losses MW | Losses % | Vmin pu | Violations |
|---|---|---|---|---|---|---|
| dry_peak | 385 | 191 | 14.5 | 3.8 | 0.983 | 0 |
| wet_peak | 462 | 0 | 33.9 | 7.3 | 0.966 | 0 |
| solar_noon | 454 | 46 | 16.2 | 3.6 | 0.977 | 0 |
| night_min | 262 | 0 | 16.0 | 6.1 | 1.000 | 0 |

Three results are worth more than the table.

**The dry-season evening loses 191 MW of demand.** Not because the network
fails, but because the generation is not there: Manantali, Gouina and Felou are
at their April minimum and Mali is entitled to only 52 % of them. The load flow
is run on the network *after* that shedding, because solving the unshed case
would hand the deficit to the slack machine and produce a study of a country
that never sheds load.

**The wet season is the expensive one to transport.** Losses double, from 3.8 %
to 7.3 %, even though demand at the peak is similar. When the western hydro
runs, 250 MW has to cross the country on the single 225 kV circuit from
Manantali through Kita to Bamako, and that corridor alone accounts for 26 MW.
A tenth of the cheap energy is spent getting it to the load.

**Bamako is about 70 Mvar short of compensation at the wet-season peak.** With
hydro supplying most of the demand from 200 km away, Balingue is the only
machine regulating voltage in the capital and the load flow asks it for 111
Mvar against 40 Mvar of capability. No solution exists that respects the
machine's limits. Rather than report a non-convergence, the study re-solves
with the limits relaxed and reports the shortfall, because that number is
something a planner can act on.

### N-1 contingency, dry-season peak

27 of 33 branch outages are secure. The six that are not are all in Bamako, and
the mechanism is the same in each: losing a 225 kV feed into the city pushes
the load onto 33 kV ties that were never meant to carry it.

| Outage | Consequence |
|---|---|
| `LN_KOD_SIR_225` | `LN_SIR_SOT_33` reaches 280 % of rating |
| `LN_KOD_KAT_225` | `LN_BKO_LAF_33` reaches 126 %, voltage falls to 0.88 pu |
| `TR_KAT_225_33` | same corridor, 125 % |

### Short-circuit levels, IEC 60909

Three-phase levels run from 5.7 kA at Ferkessedougou down to 1.5 kA at
Koutiala; 1400 to 2200 MVA across the 225 kV network, which is the range
switchgear in the region is specified for.

Two findings come out of the earth-fault calculation:

- At Kodialani, Sirakoro and Kati the single-phase current *exceeds* the
  three-phase current. That is not an error: close to a solidly earthed star
  point the zero-sequence impedance is the lower of the two, and it is the
  earth fault that sizes the switchgear there.
- Every 33 kV busbar returns an earth-fault current of practically zero,
  because it sits on the delta winding of a YNd transformer and the catalogue
  contains no earthing transformer. No earth-fault protection could be set
  from this study. `earthing_review()` reports both conditions, and the gap is
  on the verification checklist in `simulation/core`.

### Annual simulation

3-hourly over 2024, AC load flow at every step:

| | |
|---|---|
| Demand | 3 531 GWh |
| Unserved | 125 GWh, 3.5 % |
| Hours with shedding | 1 866 |
| Hydro / thermal / import / solar | 1 361 / 1 280 / 770 / 150 GWh |

The shedding is not spread through the year. It is concentrated in March to
June — 112 hours in April alone — and disappears entirely from July to
December. The Malian supply problem, as this model reproduces it, is a
seasonal one.

### Photovoltaic hosting capacity

Bisection on injected power at every transmission busbar, with substation
capacitor switching allowed to respond:

| Busbar | Hosting capacity MW | Binding constraint |
|---|---|---|
| Manantali 225 | 595 | none within search range |
| Kita 225 | 511 | thermal limit on `LN_MAN_KIT_225` |
| Kodialani 225 | 408 | undervoltage at Kita 33 |
| Badalabougou 33 | 239 | thermal limit on `LN_BKO_LAF_33` |

The binding constraint is thermal loading on long corridors, not the voltage
rise that limits hosting capacity in dense European networks. Where to put the
next plant in Mali is a transmission question.

## What had to be written by hand

Three things pandapower does not do on its own, all in `operations.py`, and all
of which change the answer:

1. **Capacitor switching.** Banks sized for the evening peak drive the network
   to 1.32 pu at four in the morning. The study steps them out and back in as a
   substation regulator would; compensation falls from 151 Mvar at peak to
   87 Mvar at night.
2. **Loss-consistent dispatch.** The exchange file allows a flat 4 % for
   network losses. The load flow computes between 3.6 % and 7.3 %, and the
   difference lands on the slack machine. The dispatch is corrected in merit
   order and the case re-solved until the slack matches its schedule to within
   1 MW.
3. **Reactive shortfall reporting.** Described above.

Each of these is built into PowerFactory as a station controller or a balancing
option. What that convenience is worth is one of the questions the comparison
in `sim/benchmark` is meant to answer.

## Layout

```
mali_pandapower/
  builder.py        exchange file -> pandapower net, no engineering decisions
  operations.py     capacitor switching, loss-consistent dispatch, Q shortfall
  studies/
    loadflow.py     the four operating points
    contingency.py  N-1 screening with isolated-demand accounting
    shortcircuit.py IEC 60909, three-phase and earth faults, earthing review
    timeseries.py   chronological year
    hosting.py      photovoltaic hosting capacity by bisection
  report.py         CSV tables and a Markdown report
  cli.py            mali-pandapower
```

## Modelling choices worth knowing

- **Machines under 20 MVA do not regulate voltage.** Sotuba is 5.7 MW on a
  150 kV busbar; declaring it a voltage-controlled node makes the load flow ask
  a 6.7 MVA machine for 148 Mvar and diverge once limits are enforced.
- **Neighbouring systems are PV buses, not slack buses.** An infinite bus at
  Ferkessedougou would let Cote d'Ivoire absorb the Malian deficit. A plain
  injection at the same radial dead end drives it to 1.4 pu. A voltage-holding
  node delivering a scheduled power is the only model that is wrong in neither
  direction.
- **Loads are constant power.** Voltage-dependent load would relieve exactly
  the low-voltage cases the study exists to find.

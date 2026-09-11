# OpenModelica — dynamics of the Malian power system

Load flows say whether a network holds at an instant. This branch asks what
happens in the seconds after something breaks, and what a village mini-grid
actually burns over a year.

```bash
pip install -e simulation/core -e simulation/openmodelica
mali-openmodelica --studies all
pytest simulation/openmodelica          # 54 checks
```

## Two implementations, on purpose

The deliverable is the Modelica library in `modelica/MaliEnergy`, compiled and
simulated by OpenModelica through `mali_openmodelica.driver`. But a model that
has only ever been run by one tool has never been checked: a sign error or a
misplaced time constant produces a curve that looks entirely reasonable.

So the same equations are written a second time in `mali_openmodelica.reference`
and integrated with SciPy, component by component, with the mapping stated in
each docstring. `mali-openmodelica --studies crosscheck` runs both and compares
the rate of change of frequency and the nadir.

**The results below were produced by the SciPy reference implementation**,
because no OpenModelica compiler was available on the machine that ran them.
The cross-check reports `status: not compared` and says so rather than implying
agreement. Install OpenModelica, re-run, and the comparison completes.

## System inertia

| Case | Stored energy MW·s | Demand MW | Seconds of demand | Largest infeed MW | Primary reserve MW |
|---|---|---|---|---|---|
| dry_peak | 2 217 | 385 | 5.8 | 120 (Côte d'Ivoire) | 24.0 |
| wet_peak | 2 064 | 462 | 4.5 | 120 | 35.4 |
| solar_noon | 2 217 | 454 | 4.9 | 120 | 20.8 |
| night_min | 1 927 | 262 | 7.4 | 46 | 70.9 |

A machine contributes its whole stored energy as soon as it is on the bars,
whatever its output. Scaling inertia by loading — a common shortcut —
understates the system at light load and overstates it at full load.

The number that should worry a planner is the last column. At the dry-season
peak the Malian system carries **24 MW of primary reserve against a 120 MW
single infeed**. Every unit is at its ceiling because the energy is not there
to do anything else.

## Frequency response

Each case is balanced at t = 0 by construction — the dispatch is taken from
`build/mali_case.json` and thermal output closes the balance — so the frequency
does not move until something trips.

| Scenario | Stored MW·s | Trip MW | RoCoF Hz/s | Nadir Hz | Shed MW |
|---|---|---|---|---|---|
| Largest unit, dry-season peak | 2 217 | 40 | −0.44 | 48.80 | 19 |
| Interconnection lost, dry-season peak | 2 217 | 120 | −1.31 | 48.02 | 96 |
| Interconnection lost, wet-season peak | 2 064 | 120 | −1.39 | 48.20 | 92 |
| Interconnection lost, midday | 2 217 | 120 | −1.30 | 48.20 | 91 |
| 250 MW of solar at midday | 1 821 | 120 | −1.57 | 48.20 | 91 |
| 250 MW of solar with frequency response | 1 821 | 120 | −1.29 | 48.40 | 68 |

**Losing the Côte d'Ivoire interconnection sheds a quarter of the country.**
The frequency falls at 1.3 Hz/s — European codes are written around 1 Hz/s —
and the system survives only because eight stages of under-frequency shedding
take 96 MW off before it reaches 47 Hz. The governors contribute almost
nothing, because there is almost nothing to contribute.

**Solar makes it worse before it makes it better.** Add 250 MW of photovoltaic
plant at midday and the thermal machines it displaces come off the bars with
their inertia. Stored energy falls from 2 217 to 1 821 MW·s and the rate of
change of frequency worsens by 20 %, from −1.30 to −1.57 Hz/s, for exactly the
same event.

**Ten per cent of headroom buys most of it back.** Curtailing the plants so they
can respond on droop returns the rate of change to −1.29 Hz/s, lifts the nadir
by 0.2 Hz and cuts load shedding from 91 MW to 68 MW. The price is ten per cent
of the solar energy, every hour of every day. That is the trade the tariff and
the grid code have to decide, and this is the number to decide it on.

## Village mini-grid

One year of hourly irradiance from the same photovoltaic model that feeds the
load flows, a 120 kW village peak, a village load shape with almost no daytime
demand and a sharp evening peak.

| Design | PV kW | Battery kWh | Diesel kW | Unserved % | Diesel hours | Fuel litres | L/kWh delivered | PV spilled % |
|---|---|---|---|---|---|---|---|---|
| Diesel only | 0 | 0 | 150 | 0.00 | 8 784 | 248 807 | 0.478 | — |
| Solar and diesel, no battery | 150 | 0 | 120 | 0.00 | 8 784 | 192 637 | 0.370 | 59.8 |
| Solar, battery, diesel | 150 | 320 | 100 | 0.14 | 6 565 | 129 758 | 0.250 | 0.0 |
| Solar, battery, diesel sized to peak | 150 | 320 | 130 | 0.24 | 5 666 | 136 727 | 0.263 | 0.0 |
| Solar heavy, large battery | 250 | 700 | 80 | 0.00 | 5 808 | 81 151 | 0.156 | 0.1 |

**Solar without storage throws away six kilowatt hours in ten.** The village
uses almost nothing while the sun is up; without a battery there is nowhere for
midday generation to go, and 59.8 % of the array's output is spilled. The fuel
saving is real but a third of what the panels could deliver.

**Storage is what turns panels into fuel savings.** Adding 320 kWh takes fuel
from 0.478 to 0.250 litres per kilowatt hour delivered — 48 % — and the spill
to zero. Doubling the array and the battery reaches 0.156 L/kWh, a 67 % saving.

**One control rule was worth 4 % of the village's energy.** The first version
started the diesel set on state of charge alone. The battery converter is rated
at 80 kW against a 120 kW peak, so on evenings when the battery was full the set
stayed standing while the village was shed — 4.4 % of demand unserved with the
storage full. Starting also when the net load exceeds the converter rating
brought that to 0.14 %. The rule is now in both implementations, and a test
asserts it.

## Layout

```
modelica/MaliEnergy/
  Components/   SystemFrequency, SynchronousUnit, PhotovoltaicPlant,
                BatteryStorage, DieselGenset, AggregateLoad
  Systems/      InterconnectedFrequency, VillageMinigrid
  Studies/      UnitTripDrySeason, UnitTripHighSolar,
                SolarFrequencyResponse, VillageDay
mali_openmodelica/
  generate.py   Modelica parameters and profile tables from mali_case.json
  driver.py     OMPython compile-and-run, plus a .mat reader
  reference.py  the same equations in SciPy, for cross-checking
  studies.py    inertia, frequency scenarios, mini-grid, cross-check
  cli.py        mali-openmodelica
```

`mali-openmodelica --studies generate` writes a `.mos` script per operating
point and the `village_profiles.txt` table the Modelica mini-grid reads, so the
dynamic models and the load flows are driven by one dataset rather than two
similar ones.

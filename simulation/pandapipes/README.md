# pandapipes — Bamako water supply, and the hydrogen question

Fluid networks are where the Malian energy question stops being only about
electricity. This branch models two of them: the water system that Bamako
depends on and that the grid has to carry, and a green hydrogen scenario that
is included because it is being proposed, and because the honest way to assess
it is to put it next to the transmission line that already exists.

```bash
pip install -e simulation/core -e simulation/pandapipes
mali-pandapipes --studies all
pytest simulation/pandapipes         # 18 checks
```

## Bamako water supply

23 nodes, 14 mains, 6 pumping stations, serving 2.59 million people with
257 000 m³ a day. Every record carries a source and a confidence level, and
almost all of it is engineering estimate rather than published record — the
water data is weaker than the electrical data and the catalogue says so in
every row.

### Hydraulic cases

| Case | Delivered m³/d | Pumping kW | kWh/m³ | Districts below minimum |
|---|---|---|---|---|
| average | 256 721 | 5 105 | 0.48 | 0 |
| peak | 395 814 | 478 | — | 2 |
| night | 115 524 | 2 908 | 0.60 | 0 |

**0.48 kWh per cubic metre** is where the water and energy questions meet.
Bamako sits 125 m below the Point G reservoir that serves it, and lifting water
up that escarpment is 3.8 MW of the 5.1 MW the system draws — three quarters of
the city's water energy spent on one rising main.

**The peak hour is supplied from storage, not from the plants.** Production
runs close to flat and the reservoirs absorb the morning and evening draw-off,
which is what they are for. Modelling the peak any other way asks the plants
for a flow they were never built to deliver and produces pressures that would
never occur.

**Magnambougou and Sotuba fail at the peak hour.** They are the two districts
with no service reservoir: the left bank is pumped directly into distribution,
so when the draw-off rises there is nothing to draw on. Sotuba falls to
negative head. This is the finding, not a defect in the model — a direct-pumped
district has no peak capacity beyond its pumps.

### Pumping station outages, average day

No station has a standby. Tripping one at a time, on the continuous duty case:

| Station | Rated kW | People losing service |
|---|---|---|
| Kabala high lift | 1 059 | 1 920 000 |
| Point G boosters | 2 600 | 1 440 000 |
| Magnambougou high lift | 463 | 665 000 |
| Faladie boosters | 426 | 480 000 |
| Djicoroni high lift | 417 | 180 000 |
| Kati transfer | 89 | 180 000 |

Two thirds of Bamako depends on a single pumping station at Kabala, and more
than half on one booster house below Point G.

## Where the two systems meet

Water pumping is 5.1 MW of electrical load on four Bamako 33 kV busbars, and
3.76 MW of it sits on Badalabougou — one of the busbars the electrical study
already finds weakest at the dry-season peak.

**The reservoirs are storage the city already owns.** Bamako's water draw-off
peaks between 18:00 and 19:00, the same hour as the electrical peak. Pumping
against six hours of reservoir storage instead of following consumption removes
**4.35 MW from the 19:00 system peak** and saves 14.7 MWh a day of pumping
energy. In a system that sheds 191 MW at that hour, 4.35 MW of flexibility that
requires no new equipment is not a rounding error — and it acts precisely on the
hour that cannot be served.

**Load shedding is measurable in litres.** At 15 % feeder outage with no standby
generation and storage already exhausted, 38 500 m³ a day are not delivered —
15 litres per person per day, a quarter of what a Bamako household consumes.

## Green hydrogen, Segou to Bamako

A 100 MW electrolyser on a 200 MW photovoltaic plant at Segou, piped 250 km to
Bamako.

| | |
|---|---|
| Hydrogen | 7 603 t/year |
| Chemical energy delivered | 253 GWh/year |
| Electrolysis efficiency | 62.9 % |
| Water consumed | 114 000 m³/year |
| Pipeline | 300 mm holds 59.2 bar at Bamako; 200 mm works too, at 3.8 m/s |

The pipeline is the easy part. The comparison is the answer: the same
electricity sent to Bamako on the 225 kV line that is **already built** arrives
as 390 GWh of electricity. Converting it to hydrogen first delivers 253 GWh of
chemical energy — a penalty of 137 GWh a year, and the hydrogen still has to be
burned or converted back at the far end.

Hydrogen in Mali is worth building for what electricity cannot do: fertiliser
feedstock for a country that imports its urea, seasonal storage, heavy
transport. It is not worth building to move energy to Bamako. A study that
sized the pipeline without putting the existing line beside it would have
concluded the opposite, and would have been wrong.

## Two modelling traps that cost real time

Both were caught by checks that now live in the catalogue loader, because both
produce answers that look plausible in a summary table.

1. **An active element in parallel with a pipe.** A pump or a control valve
   connected between the same two nodes as a main is short-circuited by it:
   flow leaves through the pump and returns through the pipe. The solver either
   fails to converge or returns a large recirculating flow. The remedy is an
   intermediate discharge node so the two sit in series.
2. **Fixed production plus fixed demand.** Give every plant a flow setpoint and
   every district a fixed draw, and the system is over-determined: if the
   setpoints supply more than the sinks take, the surplus has nowhere to go and
   the solution comes back as nothing but NaN. At least one plant has to float
   and follow the load, which is how Kabala is actually run.

A third trap is handled in the results rather than the input: a node cut off
from every source returns NaN, and NaN compares false against any threshold. A
naive check reports the districts with no water at all as adequately served.

## Layout

```
mali_pandapipes/
  water/
    catalog.py    reference tables, provenance, topology checks
    builder.py    pandapipes network, production controls, pressure reduction
    studies.py    demand cases, outage screening, daily pumping profile
  hydrogen/
    network.py    electrolyser sizing, pipeline hydraulics, the comparison
  coupling.py     pumping load by busbar, storage flexibility, shedding in litres
  cli.py          mali-pandapipes
data/reference/   nodes, pipes, pumps, demand, controls
```

# Simscape Electrical — converters on the Malian network

Load flows and dynamic models treat a photovoltaic plant as a power injection.
This branch asks whether the converter that makes that injection can actually
be controlled at the busbar it is connected to — a question that depends on the
network, not on the inverter, and that is answered here with the fault levels
the pandapower branch computed for the same system.

```bash
pip install -e simulation/core -e simulation/simscape
mali-simscape --studies all
pytest simulation/simscape          # 17 checks
```

## Two implementations

The deliverable is the Simscape Electrical model in `matlab/`, built
programmatically so it lives in version control as readable text rather than a
binary `.slx`. `mali_simscape/reference.py` is the same plant and the same
control law written again in Python and integrated with SciPy.

**The results below come from the Python reference**, because no MATLAB
installation was available on the machine that produced them. `--studies
compare` reports `not compared` and says so explicitly rather than implying the
two agree. Install MATLAB with Simulink and Simscape Electrical, run
`matlab/scripts/run_all.m`, then re-run the comparison.

## Grid strength at the connection points

Fault levels from the IEC 60909 calculation on the dry-season peak case,
committed in `data/shortcircuit_dry_peak.csv` with instructions to regenerate.

| Plant | Busbar | kV | MW | Sk MVA | SCR | Strength | PLL bandwidth Hz |
|---|---|---|---|---|---|---|---|
| Kita | BUS_KITA_33 | 33 | 50 | 279 | 5.6 | moderate | 11 |
| Safo / Sanankoroba | BUS_KATI_225 | 225 | 200 | 1 311 | 6.6 | moderate | 13 |
| Sikasso | BUS_SIKASSO_33 | 33 | 50 | 415 | 8.3 | moderate | 17 |
| Ségou | BUS_SEGOU_33 | 33 | 33 | 397 | 12.0 | strong | 24 |

Kita is the weakest: 50 MW behind a 279 MVA busbar. It is still comfortably
above the threshold where converter control becomes difficult, which is the
useful conclusion — **the existing Malian photovoltaic fleet is not
grid-strength constrained**, and a study that claimed otherwise would be
inventing a problem.

## Validation before conclusions

The same converter against a progressively weaker network, to establish that
the model reproduces behaviour that is already known:

| SCR | Stable | Final P pu | Max angle ° | Max current pu |
|---|---|---|---|---|
| 8.0 | yes | 1.00 | 7.7 | 0.99 |
| 5.0 | yes | 1.00 | 12.3 | 0.99 |
| 3.0 | yes | 1.00 | 21.0 | 1.01 |
| 2.0 | yes | 1.00 | 33.8 | 1.08 |
| 1.5 | yes | **0.89** | 58.5 | 1.21 |
| 1.2 | **no** | 0.26 | diverges | 1.25 |
| 1.0 | **no** | −0.61 | diverges | 1.22 |

The power-transfer limit appears at a ratio of 1.5 — the plant can no longer
deliver its setpoint whatever the controller does — and synchronism is lost
below about 1.2. Those are the textbook limits, and the model reaching them
without being told to is what makes the Malian numbers above worth anything.

Two modelling choices decide whether this works at all, and both are asserted
by tests:

1. **The current controller decouples with the filter inductance, not the
   total.** Decoupling with filter plus network cancels the grid impedance
   exactly; every connection then looks strong and the weak-grid problem
   disappears from the model rather than from the plant. Before this was
   corrected, a ratio of 1.0 was reported as stable.
2. **A control delay is represented.** One and a half sample periods of
   sampling, computation and modulation, which is the other half of the
   mechanism.

## How much more can each busbar take

The actionable result. Converting fault level into the megawatts a connection
point can carry before the converter, rather than the thermal rating of the
network, becomes the constraint:

| Busbar | Connected MW | SCR now | MW at SCR 3 | Headroom MW | Limiting factor |
|---|---|---|---|---|---|
| BUS_KITA_33 | 50 | 5.6 | 93 | **43** | converter control |
| BUS_SIKASSO_33 | 50 | 8.3 | 138 | 88 | converter control |
| BUS_SEGOU_33 | 33 | 12.0 | 132 | 100 | thermal rating |
| BUS_KATI_225 | 200 | 6.6 | 437 | 237 | converter control |

Kita has 43 MW of headroom before it needs a different control structure or
synchronous support. Kati, where the 200 MW Safo project connects, has 237 MW —
the 225 kV busbar is the right place for a plant that size, and the numbers say
why rather than asserting it.

## Low-voltage ride-through

A 40 % dip at each connection point:

| Plant | SCR | Max current pu | On limit | P after dip pu |
|---|---|---|---|---|
| Kita | 5.3 | 1.20 | yes | 0.71 |
| Ségou | 11.4 | 1.20 | yes | 0.73 |
| Safo | 6.2 | 1.20 | yes | 0.71 |
| Sikasso | 7.9 | 1.20 | yes | 0.73 |

Every plant rides through on its current limit and none trips. The angle
excursion scales with weakness — 24.6° at Kita against 11.2° at Ségou — which
is the margin that disappears first as plant capacity grows.

## Layout

```
matlab/
  +mali/
    caseData.m             read build/mali_case.json
    gridStrength.m         fault levels -> short-circuit ratio and Thevenin
    inverterParameters.m   plant and controller tuning
    buildSimscapeModel.m   build the model programmatically
    addControlSubsystem.m  PLL, dq current control, decoupling, delay
    runStudies.m           run everything, write the same tables as Python
    extractMetrics.m       reduce a run to comparable figures
  scripts/run_all.m
mali_simscape/
  grid_strength.py   fault levels to connection points
  reference.py       averaged EMT model of plant and control
  studies.py         strength, sweep, step, limits, dip, fleet
  matlab.py          invoke MATLAB, compare the two implementations
  cli.py             mali-simscape
data/
  shortcircuit_dry_peak.csv   produced by sim/pandapower, with regeneration steps
```

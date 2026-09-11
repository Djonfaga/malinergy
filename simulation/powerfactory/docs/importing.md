# Importing the project into PowerFactory

## 1. Build the canonical case

```bash
cd simulation/core
mali-energy build
```

## 2. Export and verify

```bash
cd simulation/powerfactory
mali-powerfactory --output build
```

This writes one `.dgs` file per operating point and checks each against the
source data before saying it is ready. The checks are not cosmetic: they catch
a missing busbar, a reference that points at no object, an impedance that
changed on the way out, a ragged row, more than one slack, and a dispatch
figure written into a per-machine attribute.

## 3. Import

In PowerFactory: **File → Import → DGS**, select `build/mali_dry_peak.dgs`,
and accept the target project name. The grid, the type library and the
operating point arrive together.

Repeat for the other three files if you want all four operating points as
separate projects, or import the first and use **Operation Scenarios** to
carry the other three dispatches against one network — which is the tidier
arrangement for a study and what a PowerFactory user would normally do.

## 4. Run the studies

The scripts in `mali_powerfactory/scripts/` run inside PowerFactory. Two ways:

**From the project.** Create a `ComPython` object, point it at the script, and
execute. This is the usual route and needs no environment setup.

**From outside.** Put the PowerFactory Python directory for your interpreter
version on `PYTHONPATH` so that `import powerfactory` resolves, then:

```bash
mali-powerfactory --run run_loadflow.py --case dry_peak --results results
```

| Script | What it does |
|---|---|
| `run_loadflow.py` | Balanced load flow on all four cases, with tap changers and shunt switching active. Writes voltages, flows, violations and a summary. |
| `run_shortcircuit.py` | IEC 60909, three-phase and single-phase, maximum and minimum, at every busbar. |
| `run_contingency.py` | N-1 over every in-service branch, using the built-in contingency object. |
| `run_rms.py` | RMS simulation of the loss of the largest infeed, for comparison with the Modelica frequency trace. |

## What the export contains

| DGS class | Objects | From |
|---|---|---|
| `ElmTerm` | 33 | busbars, with coordinates and zone |
| `TypLne` / `ElmLne` | 7 / 25 | one type per conductor and tower family, shared between corridors |
| `TypTr2` / `ElmTr2` | 6 / 12 | transformer types with zero-sequence data and tap range |
| `TypSym` / `ElmSym` | 9 / 9 | synchronous machines with inertia and subtransient reactance |
| `ElmGenstat` | 2 | photovoltaic plants as static generators with a current-limited fault contribution |
| `ElmShnt` | 12 | capacitor banks, with the step count so the station controller can switch them |
| `ElmLod` | 12 | demand at the operating point |
| `ElmXnet` | 3 | the slack machine and the two neighbouring systems |

## Two choices that matter

**Neighbours are `PV`, not `SL`.** Côte d'Ivoire and Senegal appear as
voltage-controlled nodes delivering a scheduled power. Making either of them a
slack node lets the neighbour absorb the Malian deficit, and the study then
describes a country that never sheds load.

**`pgini` is per machine.** PowerFactory multiplies it by `ngnum`. Manantali is
five units; exporting the station output against a machine count of five gives
a load flow with five times the generation. It converges. It is nonsense. The
verifier checks the product against the case and fails the export if they
differ by more than one per cent.

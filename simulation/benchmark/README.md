# Five tools, one system

This branch carries all five environments at once, so the comparison can
actually be run rather than described. It exists to answer a question the
individual branches cannot: given the same Malian network, the same demand and
the same dispatch, what do PowerFactory, OpenModelica, pandapower, pandapipes
and Simscape Electrical each contribute, and what does each of them cost?

```bash
pip install -e simulation/core -e simulation/pandapower -e simulation/pandapipes \
            -e simulation/openmodelica -e simulation/simscape -e simulation/powerfactory \
            -e simulation/benchmark
mali-energy build
mali-benchmark --sections all
pytest simulation/benchmark        # 14 checks
```

## What makes this a benchmark rather than a collection

Every tool reads `build/mali_case.json`. The network, the demand at every
busbar, the dispatch of every unit and the interchange with the neighbours are
resolved once, in `simulation/core`, and each adapter translates rather than
decides. A difference between two results is therefore a difference between two
tools, which is the only way the comparison means anything.

## Capability

Seventeen capabilities, scored on what each tool did during this study —
built in, partly, written by hand, or not available — with capabilities that do
not apply to a tool excluded from its score.

| Tool | Applicable | Built in | Partly | By hand | Absent | Weighted |
|---|---|---|---|---|---|---|
| pandapipes | 8 | 6 | 0 | 2 | 0 | 0.85 |
| pandapower | 16 | 8 | 0 | 5 | 3 | 0.62 |
| PowerFactory | 17 | 10 | 3 | 0 | 4 | 0.61 |
| OpenModelica | 15 | 5 | 4 | 1 | 5 | 0.51 |
| Simscape Electrical | 15 | 5 | 5 | 1 | 4 | 0.40 |

Read the score carefully. pandapipes leads because it was asked eight questions
and answered them; it cannot compute a short-circuit current and was not asked
to. PowerFactory has the most capabilities built in and none written by hand,
and still scores level with pandapower, because the weighting counts running in
automated checks and installing without a licence as capabilities too. Whether
those belong in the table is a judgement, and it is stated rather than hidden:
change the weights in `capability.py` and the ranking changes.

## What each tool made us write

The column an engineering office should read, because it is the difference
between a licence fee and an engineer's month:

| Capability | Written by hand for | Built into |
|---|---|---|
| Automatic tap changing and shunt switching | pandapower | PowerFactory |
| Loss-consistent dispatch | pandapower | PowerFactory |
| Reporting a reactive shortfall | pandapower | (partly PowerFactory) |
| Contingency analysis with isolated-demand accounting | pandapower, pandapipes | PowerFactory |
| Coupling a fluid network to an electrical one | pandapower, pandapipes | OpenModelica, Simscape |

Three of those took a day each and are now ninety to a hundred and fifty lines
in `mali_pandapower/operations.py` and `mali_pandapipes/coupling.py`. All three
change the answer: without capacitor switching the night case sits at 1.32 pu,
without loss-consistent dispatch the slack machine silently carries 20 MW it
does not have, and without the reactive shortfall report the wet-season peak is
a non-convergence rather than a number.

## Effort

| Branch | Files | Code | Commentary | Ratio | Test lines |
|---|---|---|---|---|---|
| core (shared data layer) | 24 | 2 809 | 465 | 0.17 | 198 |
| pandapower | 11 | 1 526 | 226 | 0.15 | 125 |
| PowerFactory | 10 | 1 216 | 92 | 0.08 | 85 |
| pandapipes | 9 | 1 107 | 158 | 0.14 | 91 |
| OpenModelica | 22 | 1 097 | 407 | 0.37 | 98 |
| Simscape Electrical | 14 | 976 | 194 | 0.20 | 89 |
| benchmark | 6 | 837 | 54 | 0.06 | — |
| **total** | **96** | **9 568** | **1 596** | **0.17** | **686** |

The shared data layer is the largest single piece, which is the honest result:
getting one defensible description of the Malian system into a form all five
tools could read took more work than any of the studies built on it.

## What it takes to run each tool

| Tool | Licence | Installation | Runs in CI | A reader can reproduce it |
|---|---|---|---|---|
| pandapower | BSD-3 | `pip install` | yes | yes |
| pandapipes | BSD-3 | `pip install` | yes | yes |
| OpenModelica | OSMC-PL | package, ~1 GB | no | yes |
| PowerFactory | commercial, per seat | licensed installer | no | no |
| Simscape Electrical | commercial | MATLAB plus two toolboxes | no | no |

This is the sharpest division in the study, and it is not about accuracy. Two
of the five were verified by running them on every change. Three were verified
by other means: a second implementation of the same equations for OpenModelica
and Simscape, and an export checked against the source for PowerFactory. Those
are real forms of verification, and they are not the same as execution. Every
result in this repository says which one produced it.

## Numerical comparison

`mali-benchmark --sections compare` runs pandapower here and reads whatever the
other tools have left behind. On a machine with only the open tools installed
it reports:

```
  pandapower             ran
  OpenModelica           ran
  PowerFactory           not run
  Simscape Electrical    not run
  - only one steady-state tool produced results, so no numerical comparison is
    possible. Run the PowerFactory scripts and re-run.
```

A test asserts that nothing ever appears in the comparison table under a tool
that did not run. The point of the harness is to make the cross-check possible
for someone who has the licences — not to produce a table that looks complete.

## Findings

Seventeen findings, each naming the branch that produced it, the evidence, and
the assumption it is most sensitive to. None is marked `measured`: this study
is built on published national statistics and a documented network catalogue,
and a findings table where everything was measured would be the clearest
possible warning sign. A test enforces that.

The six that open the argument:

1. **The dry-season evening peak cannot be served.** 191 MW shed, 3.5 % of
   annual energy, 1 866 hours a year.
2. **The shortfall is seasonal, not structural.** 112 hours of shedding in
   April, none between July and December.
3. **Moving the western hydro to Bamako costs a tenth of it.** Losses double
   from 3.8 % to 7.3 % when the OMVS plants run.
4. **The system runs with almost no primary reserve.** 24 MW of headroom
   against a 120 MW single infeed.
5. **Losing the Côte d'Ivoire interconnection sheds a quarter of the country.**
   The frequency falls at 1.31 Hz/s against a 1 Hz/s design norm.
6. **Ten per cent of solar headroom buys the response back.** Shedding falls
   from 91 MW to 68 MW, at the cost of a tenth of the solar energy.

## Replacing the data

Everything above rests on a catalogue whose rows are marked `estimated`. See
`simulation/core/docs/replacing_data.md` for how to substitute measured EDM-SA,
OMVS or CREE figures and re-run the whole chain — the studies are written so
that this changes the numbers and not the code.

## Layout

```
mali_benchmark/
  capability.py  the matrix, with evidence for every claim
  compare.py     run what can be run, read what was left behind, compare
  effort.py      lines written, and what it takes to run each tool
  findings.py    the Malian conclusions, with branch and sensitivity
  cli.py         mali-benchmark
```

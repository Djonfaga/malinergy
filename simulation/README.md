# Mali power system simulation — five tools, one dataset

Seven branches. One canonical description of the Malian energy system, and five
simulation environments studying it.

| Branch | Contents | Verified by |
|---|---|---|
| `sim/core-data` | Canonical dataset: network catalogue, real data import, demand and solar models, four operating points | 32 tests, executed |
| `sim/pandapower` | Load flow, N-1, IEC 60909, annual chronological run, photovoltaic hosting capacity | 20 tests, executed |
| `sim/pandapipes` | Bamako water supply, electricity–water coupling, green hydrogen scenario | 18 tests, executed |
| `sim/openmodelica` | Modelica library: system frequency dynamics, village mini-grid | 54 tests; SciPy reference executed, library checked structurally |
| `sim/simscape-electrical` | Converter control at the real connection points, grid strength, ride-through | 17 tests; Python reference executed |
| `sim/powerfactory` | DGS export, verification, automation scripts | 16 tests; export verified against source |
| `sim/benchmark` | All five together, capability matrix, effort, findings, comparison harness | 14 tests; **171 in total** |

## Start here

```bash
python -m venv .venv && source .venv/bin/activate
git checkout sim/benchmark                       # carries all five tools

pip install -e simulation/core -e simulation/pandapower -e simulation/pandapipes \
            -e simulation/openmodelica -e simulation/simscape \
            -e simulation/powerfactory -e simulation/benchmark

cd simulation/core
mali-energy fetch      # real data: national electricity balance, population, places
mali-energy validate   # check the catalogue before trusting it
mali-energy build      # write build/mali_case.json, which every tool reads
mali-energy gaps       # every row still resting on an engineering estimate
```

Then any of:

```bash
cd ../pandapower   && mali-pandapower --studies all
cd ../pandapipes   && mali-pandapipes --studies all
cd ../openmodelica && mali-openmodelica --studies all
cd ../simscape     && mali-simscape --studies all
cd ../powerfactory && mali-powerfactory --output build
cd ../benchmark    && mali-benchmark --sections all
```

## The rule the whole thing rests on

Every tool reads the same file. The network, the demand at each busbar, the
dispatch of every unit and the interchange with the neighbours are resolved once
in `simulation/core` and each adapter translates rather than decides. A
difference between two results is a difference between two tools.

## What is measured, what is modelled

Enforced in code, not left to the reader. Every record carries a `source` and a
`confidence`; the loader refuses a row without them; every build emits a data
card with the mix and a bibliography.

- **Measured**: national electricity balance 1980–2024 (Our World in Data, from
  Ember and the Energy Institute), population and populated places, the SoDa
  Linke turbidity climatology that carries the harmattan dust load.
- **Derived**: every line impedance, computed from conductor and tower geometry
  rather than copied; line lengths from coordinates; ampacities derated for
  Sahelian ambient temperature by a simplified IEC 738 heat balance.
- **Estimated**: 187 of 224 catalogue rows — Bamako's distribution topology,
  transformer impedances, load weights, hydro seasonality, cloud factors.

`simulation/core/docs/replacing_data.md` is the workflow for substituting
measured EDM-SA, OMVS or CREE figures. Edit a CSV, change the confidence,
register the source, re-run. Nothing downstream needs touching.

## What the study found

Seventeen findings with branch, evidence and dominant sensitivity in
`simulation/benchmark/results/findings.csv`. The argument in six lines:

1. The dry-season evening peak cannot be served — 191 MW shed, 1 866 hours a year.
2. The shortfall is seasonal: 112 hours of shedding in April, none July to December.
3. Moving the western hydro to Bamako costs a tenth of it — losses double to 7.3 %.
4. The system runs on 24 MW of primary reserve against a 120 MW single infeed.
5. Losing the Côte d'Ivoire interconnection sheds a quarter of the country at 1.31 Hz/s.
6. Ten per cent of solar headroom buys that response back, cutting shedding from 91 to 68 MW.

And beyond the grid: Bamako's water costs 0.48 kWh per cubic metre and two
thirds of the city depends on one pumping station; the reservoirs are 4.35 MW
of flexibility at the exact hour the grid cannot serve; hydrogen delivers 253
GWh where the existing 225 kV line delivers 390.

## What could not be run here

PowerFactory and MATLAB need licences; OpenModelica needs an installation this
environment did not have. Those three were verified by other means — a second
implementation of the same equations, checked against the first, and an export
verified against the source data. Every result states which tool produced it,
and a test in `sim/benchmark` forbids a value from appearing under a tool that
did not run.

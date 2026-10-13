# Mali PyPSA model — version 0.1

A single-node least-cost dispatch model of the Malian power system, built on the
shared catalogue in `simulation/core`. Everything it knows about the fleet, the
demand and the sun comes from that catalogue, so this model and the power-flow
studies in the sibling branches describe the same country rather than two
similar ones.

```bash
pip install -e ../core -e .
mali-pypsa solve --figures          # dispatch, tables, report, figures
mali-pypsa validate                 # against data the model did not use
mali-pypsa compare                  # both import bases
mali-pypsa cutout --year 2024       # ERA5, needs a Copernicus account
```

Current PyPSA declares `pandas>=3.0` and current pandapower declares
`pandas~=2.3`, so installing this package beside the sibling in
`simulation/pandapower` — which `mali-pypsa validate` does, to compare the two
models — leaves pip with an unsatisfiable pair and a warning. Both run
correctly on pandas 2.3 and the suite passes there; install them one at a time
rather than in a single resolve, which is what the workflow does. Installing
this package on its own takes the newer pandas and the warning does not arise.

## Scope

Stated so that what the model does *not* do is as clear as what it does.

| In scope | Out of scope, deferred to a later version |
|---|---|
| One node (copper plate) | Transmission network and losses — `sim/pandapower` has that |
| EDM-SA generation fleet, as commissioned | Capacity expansion and investment |
| Annual hourly demand profile | Multi-year horizons, demand growth |
| Solar resource, hourly | Wind, and any other new resource |
| Least-cost economic dispatch | Unit commitment, start-up costs, minimum up and down times |
| Run-of-river limited hour by hour; reservoirs by a monthly energy budget | Reservoir optimisation against an inflow time series, and storage across months |

Version 0.1 is the floor, not the ambition: a model small enough that every
number in it can be traced, so that later versions have something to be checked
against.

## Result, 2024

Hourly, 8784 snapshots, imports at the contracted level, Mali's OMVS share
taken off at the plant, resource from the clear-sky model in `simulation/core`
(no Copernicus credentials in this environment). Every table and figure below
comes from the single run committed in `results/`, and the data behind each
figure sits beside it.

| | |
|---|---|
| Demand (generation required) | **3 685 GWh**, peak 604 MW |
| Unserved | **70.7 GWh — 1.9 %**, in snapshots standing for 994 hours |
| Operating cost | **255 M USD**, 70.6 USD/MWh served |
| Emissions | **689 kt CO₂**, 0.191 kg/kWh |
| Mix | hydro 1 361 · thermal 1 043 · import 1 040 · solar 170 GWh |

![Monthly energy balance](results/figures/monthly_balance.png)

The shape of the Malian year is the result. Hydro falls from 182 GWh in
September to 50 GWh in May while load climbs into the hot months, and
everything that is not water is either bought from Côte d'Ivoire up to the
contracted ceiling or burnt. All of the unserved energy falls in March to June;
from July to February the model sheds nothing at all.

### Demand is generation required, not consumption

A copper plate has no network and therefore computes no losses. If demand were
set to what customers consume, the model would generate about a fifth less
energy than the system really does and every fuel bill and emission figure
would be understated by that fifth, while still solving cleanly. So demand here
carries the transmission and distribution losses inside it, because there is
nowhere else for them to be. This is the single most consequential choice in
the model and it is why the totals are not directly comparable with the sibling
studies, which have a network to put losses in.

The summary reports `demand_gwh`, `export_obligation_gwh` and `total_load_gwh`
separately rather than one number called demand, because under the alternative
OMVS settlement below they are not the same and quoting the larger under the
smaller's name overstates demand by 7 %.

## Two findings

### Mali's dry season is short of energy, not of power

Reservoir plants are limited by a monthly energy budget rather than by an
hourly ceiling — see below — so Manantali and Sélingué are free to open to
Mali's full entitlement for the evening peak. What that freedom cannot do is
create water: in April and May the month's budget is spent and the system still
sheds in 447 of April's 720 hours and 391 of May's 744, so moving a megawatt
hour from one of those hours to another changes nothing.

![Dry-season week](results/figures/dry_season_week.png)

The restlessness of the hydro band in that figure is the linear programme being
indifferent, not the river. Thermal sits flat against its availability ceiling
all week; the orange is what nobody can supply.

### The contracted import, not the line, is what rations supply

The interconnection to Côte d'Ivoire is rated 200 MW and the contracted
exchange is 120 MW. Running the same year on both ceilings:

| Import basis | Unserved | Operating cost | CO₂ | Thermal | Import |
|---|---|---|---|---|---|
| contracted, 120 MW | 70.7 GWh (1.9 %) | 255 M USD | 689 kt | 1 043 GWh | 1 040 GWh |
| line rating, 200 MW | 0.2 GWh (0.0 %) | 233 M USD | 376 kt | 573 GWh | 1 580 GWh |

Shedding all but disappears and the cost of serving a megawatt hour falls 11 %.
The emissions column needs a caveat the model cannot supply: imported energy is
counted as carbon free, and the Ivorian system is largely gas fired, so the
apparent 45 % saving is the carbon that moves across the border rather than the
carbon that stops being emitted. Whether the headroom is real depends on what
is available on the Ivorian side and on the commercial arrangement, neither of
which this model knows. It is the gap between two stated assumptions, not a
recommendation.

## The open question in the data

**Mali's OMVS share is deducted once, at the plant — and the catalogue can be
read as asking for it twice.** Manantali, Gouina and Félou are capped at Mali's
52 % entitlement, so Mali never receives the other 192 MW. The catalogue also
carries the Senegal interconnection at −30 MW with the note *"exchange of the
OMVS hydro shares"*. Taking that at face value and carrying it as a firm export
on top deducts the same entitlement a second time, and prices it at zero
against Malian load valued at the cost of lost load.

The default is therefore `--omvs-settlement at_the_plant`. The other reading
stays reachable, because the catalogue is genuinely ambiguous — the −30 MW may
be a separate commercial sale rather than the share settlement — and the answer
moves the headline numbers by a factor of two:

| OMVS settlement | Total load | Unserved | Operating cost | CO₂ |
|---|---|---|---|---|
| `at_the_plant` (default) | 3 685 GWh | 70.7 GWh (1.9 %) | 255 M USD | 689 kt |
| `and_again_on_the_link` | 3 948 GWh | 136.3 GWh (3.5 %) | 285 M USD | 813 kt |

This is the first thing measured OMVS settlement data should resolve. Until it
does, no shedding figure from this model should be quoted without saying which
settlement produced it.

## Validation

A model calibrated on a statistic cannot be validated against it. The demand
level here comes from the national electricity balance, so reproducing total
demand proves nothing. What can be checked is the *composition* the optimiser
chose, because nothing told it how much of the year should come from hydro,
thermal or solar — that fell out of the merit order, the river and the sun.

![Validation](results/figures/validation.png)

| Quantity | Model | National statistic | Deviation |
|---|---|---|---|
| Solar | 169.8 GWh | 170.0 GWh | **−0.1 %** |
| Hydro | 1 361 GWh | 920 GWh | +48 % |
| Thermal | 1 043 GWh | 2 640 GWh | −60 % |

**Solar is a real check and it passes.** The resource model, the plant list and
the capacity factors were all built without reference to that figure, and they
land on it within a fifth of a per cent.

**Hydro at +48 % is an open problem, and it is a data problem.** The model
dispatches every megawatt hour the monthly availability table and Mali's OMVS
share allow, because water is the cheapest thing in the merit order. Either the
availability table is too generous — it is marked `estimated`, derived from
design energies rather than from operating records — or the real plants are not
run to their limit. Measured OMVS production data will decide it, and until
then every hydro figure here should be read as an upper bound.

**Thermal at −60 % is mostly a definitional gap.** The national fossil figure
includes the captive diesel plant of the gold mines, which is not on the
interconnected network at all. The utility share used to adjust for it is an
assumption and the comparison inherits its uncertainty.

**The national net-import line is not a reference for this model's import
variable**, and the comparison is refused rather than made. Manantali stands on
Malian soil, so its Senegalese and Mauritanian shares appear as Malian exports
in national accounts, whereas this model simply never gives Mali that energy.

### Against the sibling model

`mali-pypsa validate` also runs the chronological study in `sim/pandapower` on
the same catalogue. A merit-order dispatch followed by an AC load flow and a
linear programme are different machinery on the same question:

| | Demand | Hydro | Solar | Thermal | Import | Unserved |
|---|---|---|---|---|---|---|
| pandapower | 3 534 | 1 361 | 169 | 1 272 | 755 | 131 |
| PyPSA | 3 685 | 1 361 | 170 | 1 043 | 1 040 | 71 |

Hydro agrees exactly and solar to half a per cent. The other three columns
differ, and the differences have names rather than cancelling out:

- **Demand, 151 GWh.** The sibling works at network entry and computes
  transmission losses; this one is a copper plate and carries them inside
  demand.
- **Import, 285 GWh.** The sibling nets the Senegal exchange against the
  Ivorian import, which accounts for 264 GWh of the gap on its own — the same
  ambiguity as above, resolved the other way on that branch. The remaining
  21 GWh is the sibling's smaller demand leaving less for imports to serve.
- **Thermal and unserved, 229 and 61 GWh.** The sibling caps reservoir hydro
  hour by hour at the month's mean rather than by a monthly energy budget, so
  its water cannot follow the evening peak and more of the peak falls to fuel
  and to shedding.

Agreement on hydro and solar is worth something precisely because the three
disagreements are explained rather than averaged away.

## Three things the model does that stock PyPSA does not

**Reservoirs are limited by energy, not by power.** A reservoir does not limit
how much a plant can produce at any instant; it limits how much it can produce
over a season. Capping Manantali hour by hour at the month's mean availability
— a factor of 0.32 in May, which against Mali's 52 % share is 33 MW of a 200 MW
machine — gets both ends wrong: it hides the peak capacity Mali actually has
and spreads the water flat across hours that do not need it. So Manantali and
Sélingué carry a monthly energy budget, added to the optimisation model as an
explicit constraint, and may reach Mali's share of nameplate in any hour. Félou,
Gouina and Sotuba keep an hourly ceiling, because their pondage is measured in
hours and for them the river really is a power limit. The budgets are set from
the same availability table the ceiling used, so the change moves energy about
without creating any.

**Profiles are averaged over each snapshot's interval, not read at its start.**
A sampled year is the ordinary way to keep an optimisation tractable and the
ordinary way to get it wrong. Sampling a solar profile twelve-hourly reads a
capacity factor of zero at midnight and nearly eighty per cent at noon,
averaging to 0.39 against a true annual mean near 0.23 — a model that solves
cleanly and reports well over half as much solar again as Mali can produce.
Averaging over the interval removes that bias. It makes the model's *inputs*
invariant to the sampling interval, and that invariance is tested; the model's
*outputs* are not exactly invariant, and the tests pin that too. Shedding is an
outcome, so coarse sampling averages a short deep shortfall into a long shallow
one: the energy moves a few per cent and the hour count moves by tens of per
cent. That is why the summary calls it `snapshot_hours_with_unserved` and the
energy is the figure to quote. Beyond three hours a snapshot straddles sunrise;
the diurnal checks then say they are not applicable instead of failing.

**Nothing is quoted from a result that has not been checked.** Every run passes
through assertions before a number leaves it, and all three commands that write
files call them. The checks that merely restate the linear programme's own rows
— energy balance, each generator under its availability, the objective equal to
the cost dispatched — can only catch solver corruption, and are kept for that.
The ones with teeth are: every reservoir month inside its budget, no load shed
while usable capacity remained, no solar at night, the demand profile on the
basis it claims and peaking in the evening, and the solar profiles behaving
like sunlight. The budget check exists because a constraint that was never
added is the one failure of this model with no symptom — the dispatch looks
reasonable and the reservoirs have quietly produced more water than the river
carries.

## Honest limits

- The solar resource is **modelled, not measured**. Without Copernicus
  credentials the model falls back on clear-sky geometry with a turbidity
  climatology, and says so in the provider field of every result. That
  describes a typical Malian year, not 2024. `mali-pypsa cutout` builds the
  ERA5 cutout where credentials exist, and the provider field then changes.
- **Imported energy is counted as carbon free.** It is not: the Ivorian system
  is largely gas fired. Every emission figure here is the carbon of Malian
  plant diluted over Malian and imported energy alike, and any saving that
  comes from importing more is overstated.
- **Minimum stable generation is recorded and not enforced.** A linear dispatch
  without unit commitment cannot represent a machine that is off, and a minimum
  applied anyway forces output from plant the optimiser would rather not run at
  all.
- **No reserve, no ramp rates, no outage schedule.** Thermal carries a flat 8 %
  forced-outage allowance instead.
- **Water does not move between months.** The budget is monthly, so the model
  cannot carry the wet season into the dry one the way a real operator does.
- **No minimum release** is imposed on the reservoirs. In reality water passes
  for irrigation and navigation whether or not the power is wanted; here water
  is the cheapest energy available so the budget is spent in full regardless,
  and only its placement within the month would be affected.
- **Fuel prices and efficiencies are `estimated`**, not invoiced. The merit
  order they produce is robust — heavy fuel oil below diesel, both far above
  water — but the absolute cost figures move with them.

## Data provenance

Every data row in `data/reference/` carries a `source` and a `confidence` in
`measured`, `reported`, `derived` or `estimated`; the loaders refuse a row
without them, and refuse it for a blank cell as well as for an empty string —
pandas reads a blank as `nan`, `str(nan)` is `"nan"`, and a guard written the
obvious way waves through exactly the row it was meant to stop. The confidence
column is reproduced in `results/fleet.csv` and `results/merit_order.csv` so
that no figure can be read without it.

## Tests

```bash
pytest
```

They cover the arithmetic of the cost table, the translation of each physical
limit into a constraint, the demand level and shape, the resource, the network
assembly, the dispatch and its checks, the validation, the report, the figures
and the command line. Several exist to catch a specific defect that was found
and fixed: a reservoir flattened to its monthly mean, a sampled year inflating
its solar, a budget constraint that was never added, a provenance label read
from the function called rather than from what it returned, a provenance guard
that a blank cell walked straight through, and Mali's OMVS entitlement deducted
twice.

Where a check could not fail it has been replaced rather than kept for
appearance: comparing a demand profile with the target stored beside it is
arithmetic, not evidence, so the check now looks the target up from the basis
and verifies the three bases are in the order the physics requires.

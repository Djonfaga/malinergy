# Mali PyPSA model — version 0.1

A single-node least-cost dispatch model of the Malian power system, built on the
shared catalogue in `simulation/core`.

**Scope of v0.1**, stated so that what the model does *not* do is as clear as
what it does:

| In scope | Out of scope, and deferred to a later version |
|---|---|
| One node (copper plate) | Transmission network and losses — `sim/pandapower` has that |
| EDM-SA generation fleet, as commissioned | Capacity expansion / investment optimisation |
| Annual hourly demand profile | Multi-year horizons, demand growth |
| Solar resource, hourly | Wind, and any other new resource |
| Least-cost economic dispatch | Unit commitment with start-up costs and minimum up/down times |
| Hydro limited by monthly availability | Reservoir optimisation with inflow time series |

Version 0.1 is the floor, not the ambition: a model small enough that every
number in it can be traced, so that later versions have something to be checked
against.

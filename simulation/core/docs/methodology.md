# Methodology

## Why a shared dataset

The question this repository exists to answer is what five simulation
environments do with the same power system. That only works if they receive
the same system. The exchange file `build/mali_case.json` is therefore the
contract: it contains the network, the demand at every bus, the dispatch of
every unit and the interchange with the neighbours, already resolved. A tool
adapter translates it; it does not decide anything.

Anything a tool adds beyond that — a solver setting, a dynamic model, a
protection function — is the tool's own contribution and is exactly what the
comparison is about.

## The calibration chain

```
national electricity demand         measured (OWID / Ember / Energy Institute)
  x utility share                   assumption, documented, validated
  / (1 - distribution losses)       the share lost below the modelled network
  x bus weight                      assumption, documented
  x hourly shape                    modelled from class, calendar, temperature
  = hourly demand per bus
  / (1 - transmission losses)       covered by the dispatch, recomputed by the load flow
  = generation to schedule
```

The loss fraction is split rather than applied whole. The catalogue represents
the network down to 33 kV, so only about four points of the eighteen and a half
per cent of total losses occur inside it. Grossing the bus demands up by the
distribution share and letting the dispatch cover only the transmission share
keeps the load flow self-consistent: the losses it computes are the losses the
dispatch scheduled.

The level comes from measurement and the shape from a model. Inverting that —
taking a peak figure from a report and inventing an annual energy — hides the
assumptions inside one number and cannot be audited.

## Line parameters

For each corridor the catalogue records a conductor and a tower family.
`mali_energy.grid.electrical` computes:

- resistance at operating temperature, from the standard 20 degC table value
  with a temperature coefficient and a skin-effect uplift;
- positive-sequence reactance from the geometric mean distance of the tower
  and the geometric mean radius of the conductor, with bundle handling;
- shunt capacitance from the same geometry;
- zero-sequence quantities via the Carson-Clem earth-return approximation,
  with a soil resistivity representative of southern Malian laterite;
- ampacity, derated from the manufacturer's reference ambient to Malian
  conditions with a simplified IEEE 738 steady-state heat balance.

Sanity is asserted in the test suite against textbook values: a 225 kV
single-circuit ASTER 570 line comes out at 0.071 ohm/km resistance,
0.415 ohm/km reactance, 8.8 nF/km, a 388 ohm surge impedance and 130 MW of
natural loading.

## Solar resource

Preference order, recorded in every result:

1. PVGIS v5.2 hourly series, if cached;
2. NASA POWER hourly series, if cached;
3. a physical clear-sky model.

The fallback is not a guess about irradiance. Solar geometry is exact and
aerosol attenuation comes from the SoDa Linke turbidity climatology shipped
with pvlib, which over Bamako returns 4.9 in December rising to 6.6 in July —
the harmattan signal. Only cloud attenuation is supplied by a monthly table.
Results built on the fallback carry a warning and the provider name.

## Dispatch

Merit order reflecting Malian practice rather than a market: hydro up to what
the river and the OMVS share allow, then all available solar, then contracted
imports, then thermal from heavy fuel oil to distillate and rental sets. What
cannot be covered is reported as unserved energy rather than absorbed by the
slack bus, because concealing a deficit in the slack is how a study of this
system ends up describing a network that does not shed load.

## Validation

`mali-energy validate` refuses to build from a catalogue that fails a
structural check and warns on the rest. It covers connectivity and islanding,
slack definition, generation adequacy against the calibrated peak, the implied
capacity factor, reactance and R/X plausibility on every line, transformer
impedance consistency, inertia constants, inverter plants wrongly given
rotating inertia, and load-weight normalisation.

## Reproducibility

Every download is cached with its SHA-256 and retrieval time; `mali-energy
inventory` prints the ledger. Model runs read the cache, never the network,
unless explicitly allowed. The four operating points are deterministic
functions of the reference tables and the `StudyConfig`.

## Known limitations

- Distribution below 33 kV is not modelled. Losses at that level are carried
  by the aggregate loss fraction.
- Isolated centres outside the interconnected network are represented only
  through the utility share; Mopti is in the catalogue but out of service.
- The dispatch is a merit order, not a unit-commitment optimisation: start-up
  costs, minimum up and down times, and reserve constraints are absent.
- Reactive dispatch is not optimised. Generators hold a voltage target and the
  load flow settles reactive flows.
- The demand model has no price or income elasticity, so multi-year scenarios
  need a separate growth assumption.

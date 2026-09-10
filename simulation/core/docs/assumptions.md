# Assumptions

Each entry states the value, why it was chosen, how sensitive the results are
to it, and what would replace it with a measurement.

## Demand

**Utility share of national demand — 0.55**
The national figure from Our World in Data covers everything generated in
Mali, including the captive diesel plant of the gold mines, which is not
connected to the interconnected network. Validation shows the consequence
directly: crediting the whole 5.96 TWh of 2024 to the catalogue fleet would
require an 87 % average capacity factor, which no fleet with this hydro and
solar share can deliver. At 55 % the implied factor is 48 %, which is
consistent with a hydro-thermal system.
*Sensitivity: high and linear.* Every megawatt in the study scales with it.
*Replace with:* EDM-SA energy sold plus network losses, from the annual report.

**Peak to average ratio — 1.42**
The inverse of a 0.70 load factor, typical of a West African utility with a
strong evening residential peak.
*Replace with:* CREE monitoring reports.

**Losses — 18.5 % total, of which 4.0 % on the modelled network**
Total losses of 18.5 % are in the range the World Bank reports for Mali and
cover technical and commercial losses alike. The split matters more than the
total. The catalogue stops at 33 kV, so only about 4 % of the energy is lost
inside it; the remaining 15 % happens below, on medium- and low-voltage
feeders that are not represented. Bus demands are therefore grossed up by the
distribution share, and the dispatch covers only the transmission share.
Applying the full 18.5 % to the dispatch instead injects roughly 18 % more
generation than the modelled network consumes, and the surplus disappears into
the slack bus — which makes every generator output and every line flow wrong
while the load flow still converges and looks respectable.
*Sensitivity: high on flows, moderate on the balance.*
*Replace with:* EDM-SA loss statistics by voltage level.

**Bus weights**
Allocation between load centres follows the concentration of demand in Bamako
(about 65 % across its five busbars), with the regional capitals and the
Koutiala industrial load making up the rest.
*Sensitivity: high locally, low globally.* Changes which line overloads first,
not the national balance.
*Replace with:* EDM-SA sales by commercial centre.

**Daily shape and the four-hour building time constant**
No hourly load curve is published for Mali. The shape is built from four
anchor points per customer class and a cooling term driven by an effective
temperature lagged through the thermal mass of the building stock. The lag is
what places the peak at 19:00-20:00 rather than at 15:00 when the air is
hottest; the test suite asserts that outcome, so a change to the model that
moves the peak fails visibly.
*Sensitivity: high for anything hour-specific.*
*Replace with:* SCADA load curves from the national control centre.

## Generation

**Malian share of the OMVS plants — 52 %**
Manantali, Gouina and Felou belong to the three riparian states. Mali cannot
dispatch the whole 400 MW.
*Sensitivity: very high in the wet season.* Assuming full ownership removes
about 190 MW of apparent dry-season deficit and would make the study wrong in
the direction that matters most.
*Replace with:* the SOGEM allocation key in force for the study year.

**Hydro monthly availability**
Reservoir and run-of-river availability follow the Senegal and Niger regimes:
minimum in April and May, maximum in September. Run-of-river plants swing far
more than reservoir plants, which is why Gouina and Felou drop to 0.20 while
Manantali holds 0.32.
*Sensitivity: very high.* This is the main driver of the seasonal contrast.
*Replace with:* OMVS operating records or gauged discharge series.

**Thermal capacity in Bamako**
Balingue, Darsalam and the rental units are represented at plant level with
capacities that are engineering estimates. Unit counts set the minimum stable
generation, which matters at `night_min`.
*Replace with:* the EDM-SA generation register.

## Network

**Line impedances** are computed from conductor and tower geometry, not
assumed. The assumption is the *choice* of conductor: ASTER 570 on the 225 kV
corridors, ASTER 366 at 150 kV, ASTER 228 in Bamako.
*Sensitivity: low for voltages, moderate for losses and thermal limits.*

**Line lengths** come from bus coordinates times a route factor of 1.10 to
1.35, higher inside Bamako where routes detour. Where a published length
exists it overrides the calculation and the record is marked as measured. The
derived lengths that can be checked against published figures agree within a
few per cent: Bamako-Segou 228 km, Sikasso-Ferkessedougou 228 km.

**Ambient temperature for ratings — 40 degC**
Manufacturer ampacities assume 25-35 degC. At 40 degC an ASTER 570 conductor
loses about 7 % of its rating, and more on a still afternoon. The study uses
the derated value everywhere.
*Sensitivity: moderate.* It decides whether a contingency overloads a line.

**Transformer impedances** are typical design values for their rating and
voltage ratio. *Replace with:* nameplate data.

## Solar

**Cloud factors, not clear-sky index**
The Linke turbidity climatology already carries the harmattan dust. The
monthly factor in `climate_normals.csv` therefore represents cloud only:
0.98 in the dry season, 0.80 in August at Bamako, lower at Sikasso. The
resulting annual global horizontal irradiation is 2061 kWh/m2 at Bamako,
2097 at Kayes and 1979 at Sikasso, consistent with published values for Mali.

**Soiling — 2 % to 14 % monthly**
Harmattan dust between November and March is the largest avoidable loss on a
Malian plant. It is applied monthly and reported separately in the plant
diagnostics so its weight is visible rather than buried in a single derate.

**Plant design — 1.25 DC/AC ratio, latitude tilt, fixed mount**
Yields land at 1570-1640 kWh/kWp, within the published range for Malian
utility plants.
*Replace with:* the actual plant design, or a PVGIS series once fetched.

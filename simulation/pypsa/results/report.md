# Mali PyPSA v0.1

## Result

- Demand **3,948 GWh**, served 3,812 GWh
- Unserved **136.3 GWh** (3.45 %) over 1,505 hours
- Operating cost **284.8 million USD**, 74.72 USD/MWh served
- Emissions **813 kt CO2**, 0.213 kg/kWh
- Resource provider: `core/clear-sky-model` (modelled)

The system cost includes unserved energy priced at the value of lost load, which accounts for 22.3 % of it. That share is an assumption rather than a measurement, which is why the operating cost is reported separately.

## Energy by carrier

| carrier | energy_gwh |
|---|---|
| hydro | 1,361 |
| thermal | 1,230 |
| import | 1,051 |
| solar | 169.8 |
| unserved | 136.4 |

## Monthly balance

| month | hydro | import | solar | thermal | unserved | demand_gwh | hours_unserved |
|---|---|---|---|---|---|---|---|
| 1 | 109.8 | 89.28 | 13.99 | 99.94 | 0 | 313.1 | 0 |
| 2 | 86.88 | 83.52 | 13.37 | 125.2 | 0.29 | 309.3 | 34 |
| 3 | 72.71 | 89.28 | 14.52 | 166.9 | 21.85 | 365.2 | 280 |
| 4 | 53.55 | 86.4 | 14.22 | 162.2 | 56.77 | 373.2 | 716 |
| 5 | 50.04 | 89.28 | 14.6 | 167.6 | 52.6 | 374.1 | 338 |
| 6 | 65.48 | 86.4 | 13.73 | 159.6 | 4.84 | 330 | 137 |
| 7 | 118 | 89.28 | 13.64 | 97.22 | 0 | 318.1 | 0 |
| 8 | 168.7 | 89.28 | 13.87 | 37.78 | 0 | 309.6 | 0 |
| 9 | 181.8 | 82.85 | 14.17 | 26.26 | 0 | 305.1 | 0 |
| 10 | 177.3 | 89.28 | 15.19 | 48.06 | 0 | 329.8 | 0 |
| 11 | 148.9 | 86.4 | 14.18 | 59.16 | 0 | 308.6 | 0 |
| 12 | 128.2 | 89.28 | 14.32 | 80.3 | 0 | 312.1 | 0 |

## Merit order

| technology | fuel | fuel_usd_per_t | fuel_usd_per_mwh_th | efficiency | vom_usd_per_mwh | marginal_cost_usd_per_mwh | co2_t_per_mwh_el | confidence |
|---|---|---|---|---|---|---|---|---|
| solar | sun | 0 | 0 | 1 | 1 | 1 | 0 | estimated |
| storage | battery | 0 | 0 | 0.9 | 2 | 2 | 0 | estimated |
| hydro | water | 0 | 0 | 1 | 3 | 3 | 0 | estimated |
| thermal_hfo | hfo | 550 | 48.89 | 0.43 | 8 | 121.7 | 0.6488 | estimated |
| thermal_diesel | diesel | 1,000 | 84.32 | 0.38 | 12 | 233.9 | 0.7026 | estimated |

## Fleet

| generator | carrier | fuel | p_nom_mw | mali_share | mean_availability | limited_by | available_gwh | marginal_cost | min_stable_pu | limits | confidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| GEN_PV_SEGOU | solar | sun | 33 | 1 | 0.232 | hourly ceiling | 67.1 | 1 | 0 | hourly solar resource | reported |
| GEN_PV_KITA | solar | sun | 50 | 1 | 0.234 | hourly ceiling | 102.7 | 1 | 0 | hourly solar resource | reported |
| GEN_MANANTALI | hydro | water | 200 | 0.52 | 0.326 | energy budget | 572.9 | 3 | 0.1 | monthly reservoir energy budget; Malian share of an OMVS scheme (52%) | reported |
| GEN_GOUINA | hydro | water | 140 | 0.52 | 0.295 | hourly ceiling | 362.3 | 3 | 0.1 | monthly river availability, as a power limit; Malian share of an OMVS scheme (52%) | reported |
| GEN_SOTUBA | hydro | water | 5.7 | 1 | 0.523 | hourly ceiling | 26.2 | 3 | 0.105 | monthly river availability, as a power limit | reported |
| GEN_SELINGUE | hydro | water | 44 | 1 | 0.633 | energy budget | 244.7 | 3 | 0.1 | monthly reservoir energy budget | reported |
| GEN_FELOU | hydro | water | 60 | 0.52 | 0.295 | hourly ceiling | 155.3 | 3 | 0.1 | monthly river availability, as a power limit; Malian share of an OMVS scheme (52%) | reported |
| GEN_AEMK_KAYES | thermal | hfo | 90 | 1 | 0.92 | hourly ceiling | 727.3 | 121.7 | 0.3 | forced-outage allowance (8%) | reported |
| GEN_BALINGUE | thermal | hfo | 65 | 1 | 0.92 | hourly ceiling | 525.3 | 121.7 | 0.3 | forced-outage allowance (8%) | estimated |
| GEN_DARSALAM | thermal | diesel | 40 | 1 | 0.92 | hourly ceiling | 323.3 | 233.9 | 0.3 | forced-outage allowance (8%) | estimated |
| GEN_RENTAL_BKO | thermal | diesel | 50 | 1 | 0.92 | hourly ceiling | 404.1 | 233.9 | 0.2 | forced-outage allowance (8%) | estimated |

## Modelling notes

- atlite is not installed; install the 'atlite' extra to use ERA5
- resource is modelled, not measured: clear-sky geometry with the SoDa Linke turbidity climatology and a monthly cloud factor, validated against published irradiation for Mali
- XC_CIV: import of up to 120 MW at $95/MWh (contracted basis; the line is rated 200 MW and the contracted exchange is 120 MW)
- XC_SEN: 30 MW export obligation, carried as a fixed load because the OMVS exchange is an entitlement settled in energy rather than a purchase
- unserved energy priced at $600/MWh, above every generator so the optimiser sheds only when nothing else is available
- minimum stable generation is recorded in the fleet specification but not bound: a linear dispatch without unit commitment cannot represent a machine that is off
- GEN_MANANTALI: reservoir plant, limited by a monthly energy budget (573 GWh over the year) and free to reach its Malian share of nameplate in any hour, rather than capped hour by hour at the month's mean
- GEN_SELINGUE: reservoir plant, limited by a monthly energy budget (245 GWh over the year) and free to reach its Malian share of nameplate in any hour, rather than capped hour by hour at the month's mean
- run-of-river plant is limited hour by hour, because there is no storage to move energy with; reservoir plant is limited by energy within the month but not across months, so the model may not carry water from the wet season into the dry one the way the real operator does
- no minimum release is imposed on the reservoir plants. In reality water is passed for irrigation and navigation whether or not the power is wanted; here hydro is the cheapest energy available, so the budget is spent in full regardless, and only its placement within the month is affected
- the model's import variable is not comparable with the national net-import statistic: Manantali stands on Malian soil and its Senegalese and Mauritanian shares are counted as Malian exports in national accounts, whereas this model simply never gives Mali that energy
- 136 GWh unserved over 1505 hours, 22 % of the objective. That share is set by the value of lost load, which is an assumption: read the operating cost separately.

"""The Malian findings, with the branch and the evidence behind each one.

This is the list a reader of the study should be able to check line by line.
Each entry names the branch that produced it, the quantity, and the assumption
it is most sensitive to — because a finding whose sensitivity is not stated is
an assertion.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class Finding:
    area: str
    finding: str
    value: str
    branch: str
    evidence: str
    sensitive_to: str
    confidence: str        # measured | derived | modelled


FINDINGS: list[Finding] = [
    Finding(
        area="Adequacy",
        finding="The dry-season evening peak cannot be served",
        value="191 MW of demand shed, 3.5 % of annual energy, 1 866 hours a year",
        branch="sim/pandapower",
        evidence="loadflow_summary.csv, annual_monthly.csv",
        sensitive_to="the Malian share of the OMVS plants (52 %) and hydro "
                     "seasonality; both are estimates on the verification checklist",
        confidence="derived",
    ),
    Finding(
        area="Adequacy",
        finding="The shortfall is seasonal, not structural",
        value="112 hours of shedding in April, none from July to December",
        branch="sim/pandapower",
        evidence="annual_monthly.csv",
        sensitive_to="the monthly hydro availability table",
        confidence="derived",
    ),
    Finding(
        area="Transmission",
        finding="Moving the western hydro to Bamako costs a tenth of it",
        value="losses double from 3.8 % to 7.3 % between dry and wet peak; "
              "26 MW on the Manantali-Kita-Bamako corridor alone",
        branch="sim/pandapower",
        evidence="flows_wet_peak.csv",
        sensitive_to="whether that corridor is single or double circuit",
        confidence="derived",
    ),
    Finding(
        area="Transmission",
        finding="Bamako is short of reactive compensation at the wet-season peak",
        value="71 Mvar; no solution exists respecting Balingue's 40 Mvar limit",
        branch="sim/pandapower",
        evidence="operations.reactive_shortfall",
        sensitive_to="the capacitor bank ratings, which are engineering estimates",
        confidence="modelled",
    ),
    Finding(
        area="Security",
        finding="Six single outages overload Bamako's 33 kV ties",
        value="loss of LN_KOD_SIR_225 takes LN_SIR_SOT_33 to 280 % of rating",
        branch="sim/pandapower",
        evidence="n1_dry_peak.csv",
        sensitive_to="the Bamako 33 kV topology, which is estimated",
        confidence="modelled",
    ),
    Finding(
        area="Security",
        finding="No earth-fault protection can be set from the present model",
        value="every 33 kV busbar returns under 0.05 kA for a single-phase fault",
        branch="sim/pandapower",
        evidence="shortcircuit_dry_peak.csv, earthing_review()",
        sensitive_to="the absence of an earthing transformer in the catalogue",
        confidence="derived",
    ),
    Finding(
        area="Dynamics",
        finding="Losing the Cote d'Ivoire interconnection sheds a quarter of the country",
        value="96 MW shed, frequency falls at 1.31 Hz/s against a 1 Hz/s design norm",
        branch="sim/openmodelica",
        evidence="frequency_scenarios.csv",
        sensitive_to="the inertia constants of the machines, which are estimates",
        confidence="modelled",
    ),
    Finding(
        area="Dynamics",
        finding="The system runs with almost no primary reserve",
        value="24 MW of headroom against a 120 MW single infeed at the dry peak",
        branch="sim/openmodelica",
        evidence="inertia.csv",
        sensitive_to="the dispatch, which follows from the adequacy finding above",
        confidence="derived",
    ),
    Finding(
        area="Dynamics",
        finding="Solar displacing machines worsens the frequency response",
        value="stored energy 2 217 to 1 821 MW.s; rate of change worsens 20 %",
        branch="sim/openmodelica",
        evidence="frequency_scenarios.csv",
        sensitive_to="whether the displaced machines come off the bars or stay "
                     "synchronised at low output",
        confidence="modelled",
    ),
    Finding(
        area="Dynamics",
        finding="Ten per cent of solar headroom buys the response back",
        value="rate of change returns to 1.29 Hz/s, shedding falls from 91 to 68 MW",
        branch="sim/openmodelica",
        evidence="frequency_scenarios.csv",
        sensitive_to="the droop setting and the headroom fraction",
        confidence="modelled",
    ),
    Finding(
        area="Converters",
        finding="The present photovoltaic fleet is not grid-strength constrained",
        value="short-circuit ratios from 5.6 at Kita to 12.0 at Segou",
        branch="sim/simscape-electrical",
        evidence="grid_strength.csv",
        sensitive_to="the fault levels, which follow from the catalogue impedances",
        confidence="derived",
    ),
    Finding(
        area="Converters",
        finding="Kita has 43 MW of headroom before control becomes difficult",
        value="93 MW at a ratio of 3, against 50 MW connected",
        branch="sim/simscape-electrical",
        evidence="converter_limits.csv",
        sensitive_to="the ratio of 3 taken as the threshold",
        confidence="derived",
    ),
    Finding(
        area="Water",
        finding="Bamako's water costs 0.48 kWh per cubic metre",
        value="5.1 MW of pumping, three quarters of it lifting water 125 m to Point G",
        branch="sim/pandapipes",
        evidence="water_cases.csv",
        sensitive_to="the pump efficiencies and the reservoir elevation",
        confidence="modelled",
    ),
    Finding(
        area="Water",
        finding="Two thirds of Bamako depends on one pumping station",
        value="losing Kabala leaves 1.92 million people without service",
        branch="sim/pandapipes",
        evidence="water_pump_outages.csv",
        sensitive_to="the network topology, which is estimated throughout",
        confidence="modelled",
    ),
    Finding(
        area="Water and energy",
        finding="Reservoir storage is flexibility the city already owns",
        value="4.35 MW off the 19:00 electrical peak, 14.7 MWh a day saved",
        branch="sim/pandapipes",
        evidence="water_coupling.json",
        sensitive_to="the assumed six hours of usable reservoir capacity",
        confidence="modelled",
    ),
    Finding(
        area="Hydrogen",
        finding="Hydrogen is the wrong way to move energy to Bamako",
        value="253 GWh as hydrogen against 390 GWh as electricity on the existing line",
        branch="sim/pandapipes",
        evidence="hydrogen_scenario.json",
        sensitive_to="the electrolyser efficiency, 53 kWh/kg",
        confidence="derived",
    ),
    Finding(
        area="Rural",
        finding="Solar without storage throws away six kilowatt hours in ten",
        value="59.8 % of a village array spilled; adding a battery cuts fuel 48 %",
        branch="sim/openmodelica",
        evidence="minigrid.csv",
        sensitive_to="the village load shape, which has almost no daytime demand",
        confidence="modelled",
    ),
]


def table() -> pd.DataFrame:
    return pd.DataFrame([f.__dict__ for f in FINDINGS])


def by_confidence() -> pd.DataFrame:
    frame = table()
    return (
        frame.groupby("confidence").size().rename("findings").reset_index()
        .sort_values("findings", ascending=False)
    )


def headline(limit: int = 6) -> pd.DataFrame:
    """The findings that would open an article, in the order they build."""
    order = [
        "The dry-season evening peak cannot be served",
        "The shortfall is seasonal, not structural",
        "Moving the western hydro to Bamako costs a tenth of it",
        "The system runs with almost no primary reserve",
        "Losing the Cote d'Ivoire interconnection sheds a quarter of the country",
        "Ten per cent of solar headroom buys the response back",
    ]
    frame = table().set_index("finding")
    rows = [frame.loc[name].to_dict() | {"finding": name} for name in order if name in frame.index]
    return pd.DataFrame(rows).head(limit)

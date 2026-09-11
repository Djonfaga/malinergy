"""The dynamic studies, run through OpenModelica where available."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .driver import openmodelica_available, openmodelica_version, simulate
from .generate import (
    frequency_case,
    high_solar_case,
    largest_infeed_mw,
    load_default_exchange,
    stored_energy_mws,
    village_profiles,
)
from .reference import FrequencyCase, MinigridDesign, simulate_frequency, simulate_minigrid


def inertia_report(exchange: dict | None = None) -> pd.DataFrame:
    """Stored kinetic energy at each operating point, and what sets it."""
    exchange = exchange or load_default_exchange()
    rows = []
    for case_name in exchange["cases"]:
        energy, contributions = stored_energy_mws(exchange, case_name)
        trip, source = largest_infeed_mw(exchange, case_name)
        case = frequency_case(exchange, case_name)
        rows.append(
            {
                "case": case_name,
                "stored_energy_mws": round(energy, 0),
                "demand_mw": case.demand_mw,
                "inertia_seconds_of_demand": round(energy / max(case.demand_mw, 1e-9), 2),
                "largest_infeed_mw": trip,
                "largest_infeed": source,
                "primary_reserve_mw": round(case.primary_reserve_mw, 1),
                "initial_rocof_hz_s": round(50.0 * trip / (2 * energy), 3) if energy else None,
                "machines": len(contributions),
            }
        )
    return pd.DataFrame(rows)


def frequency_scenarios(exchange: dict | None = None) -> pd.DataFrame:
    """Every frequency experiment, with the tool that produced each row named."""
    exchange = exchange or load_default_exchange()
    scenarios: list[tuple[str, FrequencyCase]] = [
        ("largest unit, dry season peak", frequency_case(exchange, "dry_peak", trip_mw=40.0)),
        ("interconnection lost, dry season peak", frequency_case(exchange, "dry_peak")),
        ("interconnection lost, wet season peak", frequency_case(exchange, "wet_peak")),
        ("interconnection lost, midday", frequency_case(exchange, "solar_noon")),
        ("250 MW of solar at midday", high_solar_case(exchange, solar_mw=250.0)),
        (
            "250 MW of solar with frequency response",
            high_solar_case(exchange, solar_mw=250.0, solar_response=True),
        ),
    ]

    rows = []
    for label, case in scenarios:
        result = simulate_frequency(case)
        row = {"scenario": label, **result.metrics}
        row["tool"] = "scipy reference"
        rows.append(row)

    frame = pd.DataFrame(rows)
    keep = [
        "scenario", "tool", "stored_energy_mws", "primary_reserve_mw", "trip_mw",
        "rocof_hz_s", "nadir_hz", "nadir_time_s", "settled_hz", "shed_mw", "collapsed",
    ]
    return frame[[c for c in keep if c in frame.columns]]


def cross_check(exchange: dict | None = None, *, case_name: str = "dry_peak") -> dict:
    """Run the same case in both implementations and compare.

    This is the check that makes the Modelica library trustworthy. Where the
    compiler is not available the comparison cannot be made, and the result
    says so rather than implying agreement.
    """
    exchange = exchange or load_default_exchange()
    case = frequency_case(exchange, case_name, trip_mw=40.0)
    reference = simulate_frequency(case)

    outcome = {
        "case": case_name,
        "openmodelica_available": openmodelica_available(),
        "openmodelica_version": openmodelica_version(),
        "reference_rocof_hz_s": reference.metrics["rocof_hz_s"],
        "reference_nadir_hz": reference.metrics["nadir_hz"],
    }
    if not openmodelica_available():
        outcome["status"] = "not compared"
        outcome["note"] = (
            "no OpenModelica compiler on this machine, so only the SciPy "
            "reference implementation was run. Install OpenModelica and re-run "
            "to compare the two."
        )
        return outcome

    simulation = simulate(
        "MaliEnergy.Systems.InterconnectedFrequency",
        stop_time=60.0,
        overrides={
            "Sbase": case.s_base_mw * 1e6,
            "Hsys": case.inertia_h_s,
            "Pdemand": case.demand_mw * 1e6,
            "Phydro": max(case.hydro_capacity_mw, 0.001) * 1e6,
            "Pthermal": max(case.thermal_capacity_mw, 0.001) * 1e6,
            "Psolar": case.solar_mw * 1e6,
            "Pimport": case.import_mw * 1e6,
            "Ptrip": case.trip_mw * 1e6,
            "tTrip": case.trip_time_s,
        },
    )
    if not simulation.ok or simulation.frame is None:
        outcome["status"] = "simulation failed"
        outcome["note"] = simulation.message
        return outcome

    frame = simulation.frame
    column = "grid.f" if "grid.f" in frame else next(
        (c for c in frame.columns if c.endswith(".f")), None
    )
    if column is None:
        outcome["status"] = "no frequency signal in the result"
        return outcome

    after = frame.index >= case.trip_time_s
    nadir = float(frame.loc[after, column].min())
    window = (frame.index >= case.trip_time_s) & (frame.index <= case.trip_time_s + 0.5)
    values = frame.loc[window, column]
    rocof = float((values.iloc[-1] - values.iloc[0]) / (values.index[-1] - values.index[0]))

    outcome.update(
        {
            "status": "compared",
            "openmodelica_rocof_hz_s": round(rocof, 4),
            "openmodelica_nadir_hz": round(nadir, 4),
            "rocof_difference_pct": round(
                100.0 * abs(rocof - reference.metrics["rocof_hz_s"])
                / max(abs(reference.metrics["rocof_hz_s"]), 1e-9),
                2,
            ),
            "nadir_difference_hz": round(abs(nadir - reference.metrics["nadir_hz"]), 4),
        }
    )
    outcome["agreement"] = (
        outcome["rocof_difference_pct"] < 2.0 and outcome["nadir_difference_hz"] < 0.05
    )
    return outcome


def minigrid_study(
    *,
    year: int = 2024,
    site: str = "Kita",
    peak_demand_kw: float = 120.0,
    designs: list[MinigridDesign] | None = None,
) -> pd.DataFrame:
    """Compare mini-grid designs over a full year of real irradiance."""
    profiles = village_profiles(year=year, site=site, peak_demand_kw=peak_demand_kw)
    irradiance = profiles["irradiance_pu"].to_numpy()
    load = profiles["load_pu"].to_numpy()

    designs = designs or [
        MinigridDesign(name="diesel only", pv_kw=0.0, battery_kw=0.0, battery_kwh=0.0,
                       diesel_kw=150.0, peak_demand_kw=peak_demand_kw,
                       soc_start_diesel=1.0, soc_stop_diesel=1.0),
        MinigridDesign(name="solar and diesel, no battery", pv_kw=150.0, battery_kw=0.0,
                       battery_kwh=0.0, diesel_kw=120.0, peak_demand_kw=peak_demand_kw,
                       soc_start_diesel=1.0, soc_stop_diesel=1.0),
        # The diesel set here is deliberately smaller than the village peak, to
        # show what that costs: when the battery empties during the evening
        # peak there is nothing left to cover the difference.
        MinigridDesign(name="solar, battery and diesel", pv_kw=150.0, battery_kw=80.0,
                       battery_kwh=320.0, diesel_kw=100.0, peak_demand_kw=peak_demand_kw),
        MinigridDesign(name="solar, battery, diesel sized to peak", pv_kw=150.0,
                       battery_kw=80.0, battery_kwh=320.0, diesel_kw=130.0,
                       peak_demand_kw=peak_demand_kw),
        MinigridDesign(name="solar heavy, large battery", pv_kw=250.0, battery_kw=120.0,
                       battery_kwh=700.0, diesel_kw=80.0, peak_demand_kw=peak_demand_kw),
    ]

    rows = []
    for design in designs:
        outcome = simulate_minigrid(design, irradiance, load, step_hours=1.0)
        outcome.pop("soc_trace", None)
        outcome.pop("diesel_trace", None)
        outcome["pv_kw"] = design.pv_kw
        outcome["battery_kwh"] = design.battery_kwh
        outcome["diesel_kw"] = design.diesel_kw
        rows.append(outcome)

    frame = pd.DataFrame(rows)
    order = [
        "design", "pv_kw", "battery_kwh", "diesel_kw", "served_kwh", "unserved_pct",
        "diesel_share_pct", "diesel_hours", "diesel_starts", "fuel_litres",
        "fuel_per_delivered_kwh", "pv_curtailed_pct",
    ]
    return frame[[c for c in order if c in frame.columns]]

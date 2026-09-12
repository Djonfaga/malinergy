"""Generation of Modelica parameters and input profiles from the core dataset.

The dynamic models must describe the same system as the load flows. That is
achieved here rather than by hand: every frequency case is derived from an
operating point in ``build/mali_case.json``, and the inertia is summed over the
units that are actually synchronised in that dispatch.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from mali_energy.config import BUILD_DIR
from mali_energy.exchange import load_exchange
from mali_energy.solar.pv import PlantDesign, plant_output

from .reference import FrequencyCase

#: Per-unit base used by every frequency case, so inertia constants compare.
S_BASE_MW = 500.0


def stored_energy_mws(exchange: dict, case_name: str) -> tuple[float, dict[str, float]]:
    """Kinetic energy of the fleet synchronised at this operating point.

    A machine contributes its whole stored energy as soon as it is on the bars,
    whatever its output. Scaling inertia by loading — a common shortcut —
    understates the system's ability to ride through a trip at light load and
    overstates it at full load.
    """
    generators = {g["id"]: g for g in exchange["network"]["generators"]}
    setpoints = exchange["cases"][case_name]["generators"]
    contributions: dict[str, float] = {}
    total = 0.0
    for gen_id, setpoint in setpoints.items():
        record = generators[gen_id]
        if record["inertia_h_s"] <= 0 or setpoint["p_mw"] <= 0:
            continue
        energy = record["inertia_h_s"] * record["sn_mva"]
        contributions[gen_id] = round(energy, 1)
        total += energy
    return total, contributions


def largest_infeed_mw(exchange: dict, case_name: str) -> tuple[float, str]:
    """The biggest single loss the system has to survive.

    Manantali is five units, so losing the plant is not the design event;
    losing one machine is. The interconnection is a single infeed and can be
    lost whole, which is often the larger number.
    """
    generators = {g["id"]: g for g in exchange["network"]["generators"]}
    worst, name = 0.0, ""
    for gen_id, setpoint in exchange["cases"][case_name]["generators"].items():
        record = generators[gen_id]
        units = max(int(record["units"]), 1)
        if setpoint["p_mw"] <= 0:
            continue
        per_unit = setpoint["p_mw"] / units
        if per_unit > worst:
            worst, name = per_unit, f"{gen_id} (one of {units} units)"
    for link_id, flow in exchange["cases"][case_name]["interchange_mw"].items():
        if flow > worst:
            worst, name = float(flow), link_id
    return round(worst, 2), name


def frequency_case(
    exchange: dict,
    case_name: str,
    *,
    trip_mw: float | None = None,
    solar_response: bool = False,
) -> FrequencyCase:
    """Build a balanced :class:`FrequencyCase` from an operating point."""
    case = exchange["cases"][case_name]
    balance = case["balance"]
    energy, _ = stored_energy_mws(exchange, case_name)
    trip, _ = largest_infeed_mw(exchange, case_name)

    demand_mw = balance["demand_mw"] - balance["unserved_mw"]
    hydro = balance["hydro_mw"]
    solar = balance["solar_mw"]
    imports = balance["net_import_mw"]
    # Thermal closes the balance. Taking it from the dispatch instead would
    # leave the case unbalanced at t = 0 by the loss allowance, and the
    # frequency would move before anything had tripped.
    thermal = demand_mw - hydro - solar - imports

    # Capacity synchronised and therefore available to the governors. Hydro is
    # limited by the river and the OMVS share at this time of year; thermal by
    # what is on the bars.
    generators = {g["id"]: g for g in exchange["network"]["generators"]}
    hydro_capacity = sum(
        setpoint["available_mw"]
        for gen_id, setpoint in case["generators"].items()
        if generators[gen_id]["technology"] == "hydro" and setpoint["p_mw"] > 0
    )
    thermal_capacity = sum(
        generators[gen_id]["capacity_mw"]
        for gen_id, setpoint in case["generators"].items()
        if generators[gen_id]["technology"] == "thermal" and setpoint["p_mw"] > 0
    )

    return FrequencyCase(
        name=case_name,
        s_base_mw=S_BASE_MW,
        inertia_h_s=energy / S_BASE_MW,
        demand_mw=round(demand_mw, 2),
        hydro_mw=round(max(hydro, 0.0), 2),
        thermal_mw=round(max(thermal, 0.0), 2),
        solar_mw=round(max(solar, 0.0), 2),
        import_mw=round(imports, 2),
        hydro_capacity_mw=round(max(hydro_capacity, hydro), 2),
        thermal_capacity_mw=round(max(thermal_capacity, thermal), 2),
        trip_mw=round(trip_mw if trip_mw is not None else trip, 2),
        solar_response=solar_response,
    )


def high_solar_case(
    exchange: dict,
    *,
    solar_mw: float = 250.0,
    base_case: str = "solar_noon",
    solar_response: bool = False,
) -> FrequencyCase:
    """A future midday with more photovoltaic capacity than exists today.

    Solar displaces thermal output megawatt for megawatt, and the machines that
    back off are assumed to come off the bars once their output reaches zero,
    which is what removes their inertia.
    """
    base = frequency_case(exchange, base_case)
    added = max(0.0, solar_mw - base.solar_mw)
    thermal = max(0.0, base.thermal_mw - added)
    displaced = base.thermal_mw - thermal

    energy, contributions = stored_energy_mws(exchange, base_case)
    # Remove the stored energy of the thermal machines in proportion to the
    # output they no longer produce, because a machine backed off to zero comes
    # off the bars and takes its inertia with it.
    thermal_energy = sum(
        value for gen_id, value in contributions.items() if _is_thermal(exchange, gen_id)
    )
    removed = (
        thermal_energy * min(1.0, displaced / base.thermal_mw) if base.thermal_mw > 0 else 0.0
    )

    return replace(
        base,
        name=f"high_solar_{int(solar_mw)}mw" + ("_ffr" if solar_response else ""),
        solar_mw=round(solar_mw, 2),
        thermal_mw=round(thermal, 2),
        thermal_capacity_mw=round(max(thermal, base.thermal_capacity_mw - displaced), 2),
        inertia_h_s=(energy - removed) / S_BASE_MW,
        solar_response=solar_response,
    )


def _is_thermal(exchange: dict, gen_id: str) -> bool:
    for record in exchange["network"]["generators"]:
        if record["id"] == gen_id:
            return record["technology"] == "thermal"
    return False


def village_profiles(
    *,
    year: int = 2024,
    site: str = "Kita",
    latitude: float = 13.05,
    longitude: float = -9.49,
    station: str = "Kayes",
    peak_demand_kw: float = 120.0,
) -> pd.DataFrame:
    """Hourly irradiance and demand for a village, from the core models.

    Irradiance comes from the same photovoltaic model that feeds the load flow
    studies. The demand shape is a village one rather than a city one: almost
    no daytime load, a short productive-use period, and a sharp evening peak
    driven by lighting and television.
    """
    design = PlantDesign(
        name=site,
        dc_capacity_mw=0.001,
        ac_capacity_mw=0.001,
        latitude=latitude,
        longitude=longitude,
        station=station,
        apply_soiling=True,
    )
    result = plant_output(design, year)
    irradiance = (result.ac_mw / design.ac_capacity_mw).clip(0.0, 1.0)

    village_shape = np.array(
        [0.22, 0.18, 0.16, 0.16, 0.18, 0.28, 0.40, 0.45, 0.50, 0.55, 0.58, 0.60,
         0.58, 0.55, 0.52, 0.55, 0.68, 0.88, 1.00, 0.95, 0.75, 0.52, 0.35, 0.26]
    )
    load = np.array([village_shape[h] for h in irradiance.index.hour])

    return pd.DataFrame(
        {
            "irradiance_pu": irradiance.to_numpy(),
            "load_pu": load,
            "load_kw": load * peak_demand_kw,
        },
        index=irradiance.index,
    )


def write_modelica_parameters(
    case: FrequencyCase, path: Path, *, model: str = "MaliEnergy.Systems.InterconnectedFrequency"
) -> Path:
    """Write a Modelica ``.mos`` script that runs one case with these parameters."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    overrides = ",".join(
        [
            f"Sbase={case.s_base_mw * 1e6}",
            f"Hsys={case.inertia_h_s:.6f}",
            f"Pdemand={case.demand_mw * 1e6}",
            f"Phydro={max(case.hydro_mw, 0.001) * 1e6}",
            f"Pthermal={max(case.thermal_mw, 0.001) * 1e6}",
            f"Psolar={case.solar_mw * 1e6}",
            f"Pimport={case.import_mw * 1e6}",
            f"Ptrip={case.trip_mw * 1e6}",
            f"tTrip={case.trip_time_s}",
            f"solarProvidesResponse={'true' if case.solar_response else 'false'}",
        ]
    )
    script = f"""// Generated from build/mali_case.json - do not edit by hand.
loadModel(Modelica); getErrorString();
loadFile("MaliEnergy/package.mo"); getErrorString();
simulate({model},
  startTime=0, stopTime=60, numberOfIntervals=6000, tolerance=1e-8,
  simflags="-override {overrides}",
  fileNamePrefix="{case.name}");
getErrorString();
"""
    path.write_text(script, encoding="utf-8")
    return path


def write_village_profile_table(frame: pd.DataFrame, path: Path, *, days: int = 365) -> Path:
    """Write the Modelica CombiTimeTable file read by Studies.VillageDay."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = frame.head(days * 24)
    seconds = np.arange(len(rows)) * 3600.0
    lines = ["#1", f"double profiles({len(rows)},3)"]
    for t, irradiance, load in zip(
        seconds, rows["irradiance_pu"], rows["load_pu"], strict=True
    ):
        lines.append(f"{t:.1f} {irradiance:.6f} {load:.6f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def load_default_exchange() -> dict:
    path = BUILD_DIR / "mali_case.json"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run 'mali-energy build' in simulation/core first."
        )
    return load_exchange(path)

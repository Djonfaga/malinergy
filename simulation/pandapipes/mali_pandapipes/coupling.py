"""Coupling between the water system and the electrical network.

The two systems in this repository meet at exactly one place: the pumping
stations are electrical loads on named 33 kV busbars. That is enough to ask
the questions that matter for Mali.

* **What does water cost the grid?** Bamako's water pumping is a few megawatts
  on busbars that are already the weakest in the dry-season case.
* **What could water give back?** Reservoirs are energy storage that already
  exists. A city that can pump into storage overnight and coast through the
  evening peak removes load from the hour the system cannot serve — and
  Bamako's evening water peak currently coincides with the electrical one.
* **What happens when the grid sheds?** Pumping stations on a shed feeder stop.
  The coupling makes the consequence visible in litres rather than megawatts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .water.catalog import WaterCatalog, load_water_catalog
from .water.studies import daily_pumping_profile, run_case


@dataclass
class CouplingResult:
    bus_loads_mw: dict[str, float] = field(default_factory=dict)
    daily: pd.DataFrame = field(default_factory=pd.DataFrame)
    summary: dict = field(default_factory=dict)
    findings: list[str] = field(default_factory=list)


def pumping_load_by_bus(
    catalog: WaterCatalog | None = None, *, case: str = "average"
) -> dict[str, float]:
    """Electrical load of the water system, in MW, by 33 kV busbar.

    The average day is the right case: at the peak hour the transmission pumps
    are standing while storage discharges, so a peak-hour snapshot would report
    almost no electrical load for a system that runs continuously.
    """
    catalog = catalog or load_water_catalog()
    result = run_case(case, catalog=catalog)
    if not result.converged:
        raise RuntimeError(f"the {case} hydraulic case does not solve")

    loads: dict[str, float] = {}
    for _, row in result.pumps.iterrows():
        pump = catalog.pumps[row["pump"]]
        if not pump.electrical_bus:
            continue
        electrical_kw = row["hydraulic_kw"] / (pump.efficiency * pump.motor_efficiency)
        loads[pump.electrical_bus] = loads.get(pump.electrical_bus, 0.0) + electrical_kw / 1000.0
    return {bus: round(mw, 4) for bus, mw in sorted(loads.items())}


def evaluate_storage_flexibility(
    catalog: WaterCatalog | None = None,
    *,
    electrical_peak_hour: int = 19,
    storage_hours: float = 6.0,
) -> CouplingResult:
    """What the reservoirs are worth to the electrical system.

    Compares the pumping load profile with and without using reservoir storage
    to decouple pumping from consumption, and reports the load removed from the
    hour of the electrical system peak.
    """
    catalog = catalog or load_water_catalog()
    following = daily_pumping_profile(catalog, storage_hours=0.0)
    scheduled = daily_pumping_profile(catalog, storage_hours=storage_hours)

    daily = pd.DataFrame(
        {
            "demand_factor": following["demand_factor"],
            "load_following_kw": following["electrical_kw"],
            "storage_scheduled_kw": scheduled["electrical_kw"],
        }
    )
    daily["reduction_kw"] = daily["load_following_kw"] - daily["storage_scheduled_kw"]

    peak_reduction_kw = float(daily.loc[electrical_peak_hour, "reduction_kw"])
    result = CouplingResult(
        bus_loads_mw=pumping_load_by_bus(catalog, case="average"),
        daily=daily.round(1),
    )
    result.summary = {
        "storage_hours": storage_hours,
        "electrical_peak_hour": electrical_peak_hour,
        "load_following_peak_kw": round(float(daily["load_following_kw"].max()), 1),
        "storage_scheduled_peak_kw": round(float(daily["storage_scheduled_kw"].max()), 1),
        "reduction_at_system_peak_kw": round(peak_reduction_kw, 1),
        "daily_energy_load_following_mwh": round(
            float(daily["load_following_kw"].sum()) / 1000.0, 2
        ),
        "daily_energy_scheduled_mwh": round(
            float(daily["storage_scheduled_kw"].sum()) / 1000.0, 2
        ),
        "total_pumping_load_mw": round(sum(result.bus_loads_mw.values()), 3),
    }
    energy_saved = (
        result.summary["daily_energy_load_following_mwh"]
        - result.summary["daily_energy_scheduled_mwh"]
    )
    result.findings.append(
        f"scheduling the pumps against {storage_hours:.0f} hours of reservoir storage "
        f"removes {peak_reduction_kw:.0f} kW from the {electrical_peak_hour}:00 system "
        f"peak and {energy_saved:.1f} MWh a day of pumping energy, because the pumps "
        "no longer chase the evening draw-off"
    )
    result.findings.append(
        "the water evening peak at 18:00-19:00 coincides with the electrical one, "
        "so this flexibility is worth more than its size suggests: it acts on the "
        "hour the Malian system cannot serve"
    )
    return result


def water_lost_to_load_shedding(
    shed_fraction: float,
    catalog: WaterCatalog | None = None,
    *,
    affected_buses: tuple[str, ...] = (),
) -> dict:
    """Water not delivered when the feeders supplying the pumps are shed.

    ``shed_fraction`` is the share of time the feeder is off. Pumping is taken
    to stop entirely while the feeder is off, which is what happens unless the
    station has standby generation.
    """
    catalog = catalog or load_water_catalog()
    loads = pumping_load_by_bus(catalog, case="average")
    buses = affected_buses or tuple(loads)

    affected_pumps = [
        p for p in catalog.pumps.values() if p.electrical_bus in buses and p.in_service
    ]
    affected_flow = sum(p.total_flow_m3_h for p in affected_pumps)
    total_flow = sum(d.average_flow_m3_h for d in catalog.demands.values())
    lost_m3_day = min(affected_flow, total_flow) * 24.0 * shed_fraction
    people = catalog.population_served

    return {
        "shed_fraction": shed_fraction,
        "affected_buses": list(buses),
        "affected_pumping_mw": round(
            sum(loads.get(b, 0.0) for b in buses), 3
        ),
        "water_not_delivered_m3_day": round(lost_m3_day, 0),
        "litres_per_person_per_day_lost": round(lost_m3_day * 1000.0 / max(people, 1), 1),
        "note": "assumes pumping stops entirely while the feeder is off and that "
        "reservoir storage is already exhausted; standby generation at the "
        "stations would change this",
    }

"""Annual chronological simulation.

The snapshot cases answer "can the network hold at this hour". This answers
the questions that only a full year can: how much energy is not served over a
year, how the seasonal hydro cycle interacts with demand, when photovoltaic
output has to be curtailed, and what the losses cost in energy rather than
percent.

The run solves an AC load flow for each step by default. That is slow but
honest: a DC approximation would drop exactly the reactive and voltage effects
that matter in a network with long radial corridors. Use ``step_hours`` to
sample the year when a full 8760 is not needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

import pandapower as pp
from mali_energy.config import StudyConfig
from mali_energy.demand.allocation import ZONE_STATION, allocate_timeseries
from mali_energy.grid.schema import GridCatalog
from mali_energy.solar.pv import design_from_generator, plant_output

from ..builder import build


@dataclass
class YearResult:
    frame: pd.DataFrame                     # one row per simulated step
    summary: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def monthly(self) -> pd.DataFrame:
        """Monthly aggregation, the resolution a report is usually written at."""
        grouped = self.frame.resample("MS").agg(
            demand_gwh=("demand_mw", lambda s: s.sum() * self.frame.attrs["step_hours"] / 1000.0),
            served_gwh=("served_mw", lambda s: s.sum() * self.frame.attrs["step_hours"] / 1000.0),
            unserved_gwh=("unserved_mw", lambda s: s.sum() * self.frame.attrs["step_hours"] / 1000.0),
            hydro_gwh=("hydro_mw", lambda s: s.sum() * self.frame.attrs["step_hours"] / 1000.0),
            solar_gwh=("solar_mw", lambda s: s.sum() * self.frame.attrs["step_hours"] / 1000.0),
            thermal_gwh=("thermal_mw", lambda s: s.sum() * self.frame.attrs["step_hours"] / 1000.0),
            import_gwh=("import_mw", lambda s: s.sum() * self.frame.attrs["step_hours"] / 1000.0),
            losses_gwh=("losses_mw", lambda s: s.sum() * self.frame.attrs["step_hours"] / 1000.0),
            peak_mw=("demand_mw", "max"),
            vm_min_pu=("vm_min_pu", "min"),
            hours_shed=("unserved_mw", lambda s: int((s > 0.1).sum())),
        )
        return grouped.round(2)


def run_year(
    exchange: dict,
    catalog: GridCatalog,
    *,
    config: StudyConfig | None = None,
    step_hours: int = 3,
    solve_power_flow: bool = True,
    base_case: str = "dry_peak",
) -> YearResult:
    """Chronological run over one year.

    Parameters
    ----------
    step_hours:
        Sampling interval. ``1`` runs every hour of the year; ``3`` samples
        every third hour, which preserves the daily and seasonal structure at
        a third of the cost.
    solve_power_flow:
        When ``False`` only the energy balance is computed, which is useful for
        a quick adequacy screen.
    """
    config = config or StudyConfig()
    demand, calibration = allocate_timeseries(catalog, config)
    demand = demand.iloc[::step_hours]

    # Photovoltaic output for every plant, once.
    solar: dict[str, pd.Series] = {}
    for generator in catalog.generators_by_technology("solar"):
        bus = catalog.buses[generator.bus]
        design = design_from_generator(generator, station=ZONE_STATION.get(bus.zone, "Bamako"))
        solar[generator.id] = plant_output(design, config.year).ac_mw.iloc[::step_hours]

    hydro_plants = catalog.generators_by_technology("hydro")
    thermal_plants = sorted(
        catalog.generators_by_technology("thermal"),
        key=lambda g: (0 if g.fuel == "hfo" else 1, -g.capacity_mw),
    )
    import_capacity = {
        link.id: link for link in catalog.interconnections.values() if link.in_service
    }

    template = build(exchange, base_case)
    net = template.net
    load_columns = [c for c in demand.columns if c in template.load_index]

    rows: list[dict] = []
    notes: list[str] = []
    non_convergent = 0

    for timestamp, step_demand in demand.iterrows():
        month = timestamp.month
        total_demand = float(step_demand.sum())
        required = total_demand / (1.0 - config.transmission_loss_fraction)
        remaining = required

        hydro_mw = 0.0
        hydro_dispatch: dict[str, float] = {}
        for generator in hydro_plants:
            availability = catalog.hydro_availability.get(generator.id, {}).get(month, 1.0)
            available = generator.capacity_mw * availability * generator.mali_share
            p = min(available, max(remaining, 0.0))
            hydro_dispatch[generator.id] = p
            hydro_mw += p
            remaining -= p

        solar_mw = 0.0
        solar_dispatch: dict[str, float] = {}
        curtailed = 0.0
        for generator in catalog.generators_by_technology("solar"):
            series = solar.get(generator.id)
            available = float(series.loc[timestamp]) if series is not None and timestamp in series.index else 0.0
            p = min(available, max(remaining, 0.0))
            curtailed += available - p
            solar_dispatch[generator.id] = p
            solar_mw += p
            remaining -= p

        import_mw = 0.0
        for link in import_capacity.values():
            typical = link.typical_import_mw
            p = (
                min(typical, max(remaining, 0.0), link.capacity_mw)
                if typical >= 0
                else max(typical, -link.capacity_mw)
            )
            import_mw += p
            remaining -= p

        thermal_mw = 0.0
        thermal_dispatch: dict[str, float] = {}
        for generator in thermal_plants:
            p = 0.0
            if remaining > 0:
                p = min(generator.capacity_mw, remaining)
                if 0 < p < generator.min_load_mw:
                    p = generator.min_load_mw
            thermal_dispatch[generator.id] = p
            thermal_mw += p
            remaining -= p

        unserved = max(remaining, 0.0)
        served = total_demand - min(unserved, total_demand)

        row = {
            "timestamp": timestamp,
            "demand_mw": total_demand,
            "served_mw": served,
            "unserved_mw": min(unserved, total_demand),
            "hydro_mw": hydro_mw,
            "solar_mw": solar_mw,
            "solar_curtailed_mw": curtailed,
            "thermal_mw": thermal_mw,
            "import_mw": import_mw,
            "losses_mw": np.nan,
            "vm_min_pu": np.nan,
            "max_loading_pct": np.nan,
            "converged": True,
        }

        if solve_power_flow:
            shed_factor = served / total_demand if total_demand else 1.0
            for load_id in load_columns:
                index = template.load_index[load_id]
                p = float(step_demand[load_id]) * shed_factor
                net.load.at[index, "p_mw"] = p
                net.load.at[index, "q_mvar"] = p * np.tan(
                    np.arccos(catalog.loads[load_id].power_factor)
                )
            for gen_id, p in {**hydro_dispatch, **thermal_dispatch}.items():
                if gen_id in template.gen_index:
                    index = template.gen_index[gen_id]
                    net.gen.at[index, "p_mw"] = p
                    net.gen.at[index, "in_service"] = p > 0
            for gen_id, p in solar_dispatch.items():
                if gen_id in template.sgen_index:
                    index = template.sgen_index[gen_id]
                    net.sgen.at[index, "p_mw"] = p
                    net.sgen.at[index, "in_service"] = p > 0
            try:
                pp.runpp(net, calculate_voltage_angles=True, init="dc", max_iteration=30)
                row["losses_mw"] = float(net.res_line.pl_mw.sum() + net.res_trafo.pl_mw.sum())
                row["vm_min_pu"] = float(net.res_bus.vm_pu.min())
                row["max_loading_pct"] = float(net.res_line.loading_percent.max())
            except pp.LoadflowNotConverged:
                row["converged"] = False
                non_convergent += 1

        rows.append(row)

    frame = pd.DataFrame(rows).set_index("timestamp")
    frame.attrs["step_hours"] = step_hours

    energy = lambda column: float(frame[column].sum() * step_hours / 1000.0)  # noqa: E731
    hours_shed = int((frame["unserved_mw"] > 0.1).sum() * step_hours)
    summary = {
        "year": config.year,
        "step_hours": step_hours,
        "steps": len(frame),
        "demand_gwh": round(energy("demand_mw"), 1),
        "served_gwh": round(energy("served_mw"), 1),
        "unserved_gwh": round(energy("unserved_mw"), 2),
        "unserved_pct": round(100.0 * energy("unserved_mw") / max(energy("demand_mw"), 1e-9), 2),
        "hours_with_shedding": hours_shed,
        "hydro_gwh": round(energy("hydro_mw"), 1),
        "solar_gwh": round(energy("solar_mw"), 1),
        "solar_curtailed_gwh": round(energy("solar_curtailed_mw"), 2),
        "thermal_gwh": round(energy("thermal_mw"), 1),
        "import_gwh": round(energy("import_mw"), 1),
        "peak_demand_mw": round(float(frame["demand_mw"].max()), 1),
        "peak_timestamp": str(frame["demand_mw"].idxmax()),
        "load_factor": round(float(frame["demand_mw"].mean() / frame["demand_mw"].max()), 3),
        "calibration_energy_gwh": round(calibration["network_entry_energy_gwh"], 1),
    }
    if solve_power_flow:
        solved = frame[frame["converged"]]
        summary.update(
            {
                "losses_gwh": round(float(solved["losses_mw"].sum() * step_hours / 1000.0), 2),
                "mean_losses_pct": round(
                    100.0 * float(solved["losses_mw"].sum() / solved["demand_mw"].sum()), 2
                ),
                "min_voltage_pu": round(float(solved["vm_min_pu"].min()), 4),
                "steps_not_converged": non_convergent,
            }
        )
        if non_convergent:
            notes.append(
                f"{non_convergent} of {len(frame)} steps did not converge and are "
                "excluded from the network statistics"
            )

    energy_error = abs(summary["demand_gwh"] - summary["calibration_energy_gwh"])
    if energy_error > 0.02 * summary["calibration_energy_gwh"]:
        notes.append(
            f"simulated demand {summary['demand_gwh']:.0f} GWh differs from the "
            f"calibration target {summary['calibration_energy_gwh']:.0f} GWh by "
            f"{energy_error:.0f} GWh; check the sampling interval"
        )

    return YearResult(frame=frame, summary=summary, notes=notes)

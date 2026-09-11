"""Hydraulic studies of the Bamako water network."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandapipes as ppipes
import pandas as pd

from .builder import MIN_SERVICE_PRESSURE_BAR, WaterBuildResult, build_water_network
from .catalog import WATER_DENSITY_KG_M3, WaterCatalog, load_water_catalog

#: Colebrook-White is the reference friction law, but the implementation in the
#: installed pandapipes fails when its internal Newton iteration is handed an
#: empty mask. Swamee-Jain is an explicit algebraic approximation of the same
#: law, within about one per cent over the Reynolds range of these mains.
FRICTION_MODEL = "swamee-jain"

#: Velocity above which a main is considered over-loaded. Water utilities design
#: transmission mains for 1 to 2 m/s; beyond 2.5 m/s head loss and surge
#: pressures rise quickly.
MAX_DESIGN_VELOCITY_M_S = 2.5


@dataclass
class HydraulicResult:
    case: str
    converged: bool
    build: WaterBuildResult
    junctions: pd.DataFrame = field(default_factory=pd.DataFrame)
    pipes: pd.DataFrame = field(default_factory=pd.DataFrame)
    pumps: pd.DataFrame = field(default_factory=pd.DataFrame)
    summary: dict = field(default_factory=dict)
    findings: list[str] = field(default_factory=list)


def solve(result: WaterBuildResult, *, iterations: int = 300) -> bool:
    try:
        ppipes.pipeflow(result.net, friction_model=FRICTION_MODEL, iter=iterations)
        return True
    except Exception:  # noqa: BLE001 - pandapipes raises several types here
        return False


def run_case(
    case: str = "average",
    *,
    catalog: WaterCatalog | None = None,
    pumps_out_of_service: tuple[str, ...] = (),
) -> HydraulicResult:
    """Solve one demand case.

    ``average`` is the mean day; ``peak`` applies each district's own peak
    factor, which is the case a network is designed for.
    """
    catalog = catalog or load_water_catalog()
    if case == "peak":
        factor = sum(d.peak_flow_m3_h for d in catalog.demands.values()) / sum(
            d.average_flow_m3_h for d in catalog.demands.values()
        )
    elif case == "average":
        factor = 1.0
    elif case == "night":
        factor = 0.45
    else:
        raise KeyError(f"unknown case {case!r}")

    # At peak hour the plants do not follow the demand: the reservoirs do. A
    # water system is sized so that production runs close to flat and storage
    # absorbs the morning and evening draw-off, which is why the peak case lets
    # the reservoirs supply the difference instead of asking the pumps for a
    # flow they were never built to deliver.
    build = build_water_network(
        catalog,
        demand_factor=factor,
        pumps_out_of_service=pumps_out_of_service,
        reservoirs_float=(case == "peak"),
    )
    converged = solve(build)
    result = HydraulicResult(case=case, converged=converged, build=build)
    result.findings.extend(build.notes)
    if not converged:
        result.findings.append(
            "the hydraulic calculation found no solution: with these demands the "
            "pumps cannot deliver against the static head"
        )
        return result

    net = build.net
    result.junctions = pd.DataFrame(
        {
            "node": net.junction.name,
            "elevation_m": net.junction.height_m,
            "p_bar": net.res_junction.p_bar,
            "head_m": (net.res_junction.p_bar * 10.197).round(1),
            "type": [catalog.nodes[n].type for n in net.junction.name],
        }
    )
    result.pipes = pd.DataFrame(
        {
            "pipe": net.pipe.name,
            "length_km": net.pipe.length_km,
            "diameter_mm": net.pipe.inner_diameter_mm,
            "velocity_m_s": net.res_pipe.v_mean_m_per_s.round(3),
            "flow_m3_h": (net.res_pipe.mdot_from_kg_per_s * 3.6).round(0),
            "head_loss_m": (
                (net.res_pipe.p_from_bar - net.res_pipe.p_to_bar) * 10.197
            ).round(2),
        }
    )
    result.pumps = pd.DataFrame(
        {
            "pump": net.pump.name,
            "lift_bar": net.res_pump.deltap_bar.round(3),
            "lift_m": (net.res_pump.deltap_bar * 10.197).round(1),
            "flow_m3_h": (net.res_pump.mdot_from_kg_per_s * 3.6).round(0),
        }
    )
    # bar -> Pa, m3/h -> m3/s, W -> kW.
    # A pump that is out of service returns NaN rather than zero.
    result.pumps = result.pumps.fillna({"lift_bar": 0.0, "lift_m": 0.0, "flow_m3_h": 0.0})
    result.pumps["hydraulic_kw"] = (
        result.pumps["lift_bar"] * 1e5 * result.pumps["flow_m3_h"] / 3600.0 / 1000.0
    ).round(1)

    electrical_kw = 0.0
    for _, row in result.pumps.iterrows():
        pump = catalog.pumps[row["pump"]]
        electrical_kw += row["hydraulic_kw"] / (pump.efficiency * pump.motor_efficiency)

    demand_nodes = result.junctions[result.junctions["type"] == "demand"]
    # A node cut off from every source returns NaN, and NaN compares false
    # against any threshold. Counting it as adequately served is the worst
    # failure this study could make: the nodes with no water at all would be
    # the ones reported as secure.
    isolated = demand_nodes[demand_nodes["p_bar"].isna()]
    deficient = demand_nodes[
        demand_nodes["p_bar"].notna() & (demand_nodes["p_bar"] < MIN_SERVICE_PRESSURE_BAR)
    ]
    fast = result.pipes[result.pipes["velocity_m_s"].abs() > MAX_DESIGN_VELOCITY_M_S]

    # Production is what the demand nodes actually take, which in the peak case
    # comes partly from storage rather than from the plants.
    production_m3_h = float(net.sink.mdot_kg_per_s.sum() * 3.6)
    result.summary = {
        "case": case,
        "demand_factor": round(factor, 3),
        "production_m3_h": round(production_m3_h, 0),
        "production_m3_day": round(production_m3_h * 24, 0),
        "hydraulic_power_kw": round(float(result.pumps["hydraulic_kw"].sum()), 1),
        "electrical_power_kw": round(electrical_kw, 1),
        "specific_energy_kwh_m3": round(electrical_kw / max(production_m3_h, 1e-9), 3),
        "pumped_share_of_supply": round(
            float(result.pumps["flow_m3_h"].clip(lower=0).sum()) / max(production_m3_h, 1e-9), 3
        ),
        "min_service_head_m": round(float(demand_nodes["head_m"].min()), 1)
        if demand_nodes["head_m"].notna().any()
        else None,
        "min_service_node": str(demand_nodes.loc[demand_nodes["head_m"].idxmin(), "node"])
        if demand_nodes["head_m"].notna().any()
        else "",
        "max_service_head_m": round(float(demand_nodes["head_m"].max()), 1),
        "max_velocity_m_s": round(float(result.pipes["velocity_m_s"].abs().max()), 2),
        "deficient_nodes": int(len(deficient)),
        "isolated_nodes": int(len(isolated)),
        "overloaded_mains": int(len(fast)),
    }

    for _, row in isolated.iterrows():
        result.findings.append(
            f"{row['node']} has no hydraulic connection to any source in this case: "
            "it receives no water at all"
        )
    for _, row in deficient.iterrows():
        result.findings.append(
            f"{row['node']} is served at {row['head_m']:.0f} m of head, below the "
            f"{MIN_SERVICE_PRESSURE_BAR * 10.197:.0f} m design minimum"
        )
    for _, row in fast.iterrows():
        result.findings.append(
            f"{row['pipe']} runs at {abs(row['velocity_m_s']):.1f} m/s, above the "
            f"{MAX_DESIGN_VELOCITY_M_S} m/s design limit"
        )
    return result


def pump_outage_screening(catalog: WaterCatalog | None = None) -> pd.DataFrame:
    """Trip each pumping station in turn at peak demand.

    Bamako's supply is not redundant, and this quantifies what that means: for
    each station, how much of the city loses adequate pressure.

    The screening runs on the average day, not the peak hour. At the peak the
    transmission pumps are already standing while the reservoirs discharge, so
    tripping one of them would show nothing; it is the continuous duty case
    that reveals what each station carries.
    """
    catalog = catalog or load_water_catalog()
    rows: list[dict] = []
    base = run_case("average", catalog=catalog)

    for pump_id, pump in catalog.pumps.items():
        result = run_case("average", catalog=catalog, pumps_out_of_service=(pump_id,))
        if not result.converged:
            rows.append(
                {
                    "pump": pump_id,
                    "name": pump.name,
                    "rated_power_kw": round(pump.rated_electrical_power_kw, 0),
                    "status": "no solution",
                    "nodes_below_minimum": None,
                    "population_affected": None,
                    "note": "the network cannot be balanced without this station",
                }
            )
            continue

        demand_nodes = result.junctions[result.junctions["type"] == "demand"]
        failed = demand_nodes[
            demand_nodes["p_bar"].isna()
            | (demand_nodes["p_bar"] < MIN_SERVICE_PRESSURE_BAR)
        ]
        affected = sum(
            catalog.demands[node].population_served
            for node in failed["node"]
            if node in catalog.demands
        )
        rows.append(
            {
                "pump": pump_id,
                "name": pump.name,
                "rated_power_kw": round(pump.rated_electrical_power_kw, 0),
                "status": "secure" if failed.empty else "service lost",
                "nodes_below_minimum": int(len(failed)),
                "population_affected": int(affected),
                "note": ", ".join(failed["node"]) if not failed.empty else "",
            }
        )

    frame = pd.DataFrame(rows)
    frame.attrs["base_case"] = base.summary
    return frame.sort_values("population_affected", ascending=False, na_position="first").reset_index(
        drop=True
    )


def daily_pumping_profile(
    catalog: WaterCatalog | None = None, *, storage_hours: float = 0.0
) -> pd.DataFrame:
    """Hourly pumping power over a day.

    ``storage_hours`` is the reservoir capacity, expressed as hours of average
    demand, that can be used to move pumping in time. With zero storage the
    pumps follow consumption and the water load peaks with the electrical
    evening peak. With storage they can be scheduled, which is what makes the
    water system a flexibility resource rather than an additional burden.
    """
    catalog = catalog or load_water_catalog()

    # Domestic water draw-off in a Sahelian city: two clear peaks, morning and
    # early evening, with a deep night trough.
    shape = [
        0.35, 0.28, 0.25, 0.28, 0.45, 0.80, 1.25, 1.45, 1.40, 1.20, 1.05, 1.00,
        1.05, 1.00, 0.95, 0.95, 1.10, 1.35, 1.50, 1.40, 1.15, 0.85, 0.60, 0.44,
    ]
    mean = sum(shape) / len(shape)
    shape = [s / mean for s in shape]

    average_flow = sum(d.average_flow_m3_h for d in catalog.demands.values())
    base = run_case("average", catalog=catalog)
    if not base.converged:
        raise RuntimeError("the average case must solve before a daily profile can be built")

    # Pumping power scales close to the cube of flow at fixed head loss, but
    # the static lift dominates here, so a quadratic fit through the duty point
    # represents it better than either extreme.
    duty_kw = base.summary["electrical_power_kw"]

    rows = []
    for hour, factor in enumerate(shape):
        if storage_hours > 0:
            # Reservoirs let the plants run flat; the draw-off shape is met from
            # storage instead of from the pumps.
            pumped = 1.0
        else:
            pumped = factor
        power = duty_kw * (0.35 + 0.65 * pumped**2)
        rows.append(
            {
                "hour": hour,
                "demand_factor": round(factor, 3),
                "pumped_factor": round(pumped, 3),
                "flow_m3_h": round(average_flow * pumped, 0),
                "electrical_kw": round(power, 1),
            }
        )
    frame = pd.DataFrame(rows).set_index("hour")
    frame.attrs["storage_hours"] = storage_hours
    frame.attrs["daily_energy_mwh"] = round(float(frame["electrical_kw"].sum()) / 1000.0, 2)
    return frame

"""Green hydrogen scenario: Segou to Bamako.

Mali has the solar resource for hydrogen and none of the infrastructure. The
question this module answers is narrow and concrete: if the surplus of a large
photovoltaic plant at Segou were used to make hydrogen, what would it take to
move it 250 km to Bamako by pipeline, and how does that compare with moving the
same energy as electricity on the 225 kV line that already exists?

The comparison is the point. A hydrogen pipeline is not obviously the right
answer for Mali, and a study that only sizes the pipeline without putting the
existing transmission line beside it is not a study, it is an advertisement.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandapipes as ppipes
import pandas as pd

#: Lower heating value of hydrogen.
LHV_H2_KWH_KG = 33.33
#: Electricity needed per kilogram in a modern alkaline or PEM stack, including
#: the balance of plant. 52-55 kWh/kg is current commercial practice.
ELECTROLYSER_KWH_PER_KG = 53.0
#: Water consumed per kilogram of hydrogen, including purification losses.
WATER_LITRES_PER_KG_H2 = 15.0


@dataclass
class HydrogenScenario:
    name: str = "Segou to Bamako"
    pv_capacity_mw: float = 200.0
    pv_capacity_factor: float = 0.23
    electrolyser_mw: float = 100.0
    pipeline_length_km: float = 250.0
    pipeline_diameter_mm: float = 300.0
    inlet_pressure_bar: float = 60.0
    outlet_pressure_bar: float = 30.0
    roughness_mm: float = 0.01
    temperature_k: float = 308.15

    @property
    def electrolyser_full_load_hours(self) -> float:
        """Hours a year the stack runs, limited by the plant it is attached to."""
        pv_energy_mwh = self.pv_capacity_mw * self.pv_capacity_factor * 8760.0
        return min(pv_energy_mwh / self.electrolyser_mw, 8760.0)

    @property
    def hydrogen_tonnes_per_year(self) -> float:
        energy_mwh = self.electrolyser_mw * self.electrolyser_full_load_hours
        return energy_mwh * 1000.0 / ELECTROLYSER_KWH_PER_KG / 1000.0

    @property
    def hydrogen_kg_per_hour(self) -> float:
        return self.electrolyser_mw * 1000.0 / ELECTROLYSER_KWH_PER_KG

    @property
    def water_m3_per_year(self) -> float:
        return self.hydrogen_tonnes_per_year * 1000.0 * WATER_LITRES_PER_KG_H2 / 1000.0


def build_pipeline(scenario: HydrogenScenario) -> ppipes.pandapipesNet:
    """A single pipeline from the electrolyser to the Bamako offtake."""
    net = ppipes.create_empty_network(fluid="hydrogen", name=scenario.name)
    segou = ppipes.create_junction(
        net, pn_bar=scenario.inlet_pressure_bar, tfluid_k=scenario.temperature_k,
        height_m=290.0, name="SEGOU_ELECTROLYSER",
    )
    bamako = ppipes.create_junction(
        net, pn_bar=scenario.outlet_pressure_bar, tfluid_k=scenario.temperature_k,
        height_m=350.0, name="BAMAKO_OFFTAKE",
    )
    ppipes.create_ext_grid(
        net, junction=segou, p_bar=scenario.inlet_pressure_bar,
        t_k=scenario.temperature_k, name="ELECTROLYSER_OUTLET", type="pt",
    )
    ppipes.create_pipe_from_parameters(
        net,
        from_junction=segou,
        to_junction=bamako,
        length_km=scenario.pipeline_length_km,
        inner_diameter_mm=scenario.pipeline_diameter_mm,
        k_mm=scenario.roughness_mm,
        sections=25,
        text_k=scenario.temperature_k,
        name="H2_SEGOU_BAMAKO",
    )
    ppipes.create_sink(
        net, junction=bamako,
        mdot_kg_per_s=scenario.hydrogen_kg_per_hour / 3600.0,
        name="BAMAKO_DEMAND",
    )
    return net


def evaluate(scenario: HydrogenScenario | None = None) -> dict:
    """Size the pipeline and compare it with the existing transmission line."""
    scenario = scenario or HydrogenScenario()
    net = build_pipeline(scenario)
    converged = True
    try:
        ppipes.pipeflow(net, friction_model="swamee-jain", iter=200)
    except Exception:  # noqa: BLE001
        converged = False

    result = {
        "scenario": scenario.name,
        "pv_capacity_mw": scenario.pv_capacity_mw,
        "electrolyser_mw": scenario.electrolyser_mw,
        "full_load_hours": round(scenario.electrolyser_full_load_hours, 0),
        "hydrogen_t_per_year": round(scenario.hydrogen_tonnes_per_year, 0),
        "hydrogen_kg_per_hour": round(scenario.hydrogen_kg_per_hour, 1),
        "energy_in_hydrogen_gwh_per_year": round(
            scenario.hydrogen_tonnes_per_year * 1000.0 * LHV_H2_KWH_KG / 1e6, 1
        ),
        "water_m3_per_year": round(scenario.water_m3_per_year, 0),
        "pipeline_km": scenario.pipeline_length_km,
        "pipeline_diameter_mm": scenario.pipeline_diameter_mm,
        "converged": converged,
    }

    if converged:
        outlet = float(net.res_junction.at[1, "p_bar"])
        result["outlet_pressure_bar"] = round(outlet, 2)
        result["pressure_drop_bar"] = round(scenario.inlet_pressure_bar - outlet, 2)
        result["velocity_m_s"] = round(float(net.res_pipe.at[0, "v_mean_m_per_s"]), 2)
        result["feasible"] = outlet >= scenario.outlet_pressure_bar
        if not result["feasible"]:
            result["finding"] = (
                f"a {scenario.pipeline_diameter_mm:.0f} mm line cannot hold "
                f"{scenario.outlet_pressure_bar:.0f} bar at Bamako: it arrives at "
                f"{outlet:.1f} bar. Either the diameter goes up or a compressor "
                "station goes in, and both cost energy the plant has to make first."
            )
    else:
        result["feasible"] = False
        result["finding"] = "no hydraulic solution: the pipeline is undersized for this flow"

    # The comparison that decides the question.
    electrical_energy_gwh = (
        scenario.electrolyser_mw * scenario.electrolyser_full_load_hours / 1000.0
    )
    delivered_gwh = result["energy_in_hydrogen_gwh_per_year"]
    result["electrolysis_efficiency_pct"] = round(
        100.0 * delivered_gwh / max(electrical_energy_gwh, 1e-9), 1
    )
    # Losses on the existing 225 kV Segou-Bamako corridor carrying the same
    # energy: about 228 km at roughly 0.071 ohm/km per circuit.
    line_loss_pct = 3.2
    result["transmission_alternative"] = {
        "delivered_gwh_per_year": round(electrical_energy_gwh * (1 - line_loss_pct / 100.0), 1),
        "line_loss_pct": line_loss_pct,
        "note": "the same electricity sent to Bamako on the 225 kV line that "
        "already exists arrives as electricity, not as hydrogen that then has "
        "to be burned or converted back",
    }
    result["energy_penalty_gwh"] = round(
        result["transmission_alternative"]["delivered_gwh_per_year"] - delivered_gwh, 1
    )
    result["conclusion"] = (
        f"converting to hydrogen and piping it delivers {delivered_gwh:.0f} GWh of "
        f"chemical energy against {result['transmission_alternative']['delivered_gwh_per_year']:.0f} "
        "GWh of electricity on the existing line. Hydrogen is worth building for what "
        "electricity cannot do — fertiliser feedstock, long-term storage, heavy "
        "transport — and not for moving energy to Bamako."
    )
    return result


def sizing_sweep(
    diameters_mm: tuple[float, ...] = (200.0, 250.0, 300.0, 400.0, 500.0),
    scenario: HydrogenScenario | None = None,
) -> pd.DataFrame:
    """Outlet pressure against pipeline diameter, to find the smallest that works."""
    base = scenario or HydrogenScenario()
    rows = []
    for diameter in diameters_mm:
        trial = HydrogenScenario(**{**base.__dict__, "pipeline_diameter_mm": diameter})
        outcome = evaluate(trial)
        rows.append(
            {
                "diameter_mm": diameter,
                "outlet_pressure_bar": outcome.get("outlet_pressure_bar"),
                "velocity_m_s": outcome.get("velocity_m_s"),
                "feasible": outcome.get("feasible"),
            }
        )
    return pd.DataFrame(rows)

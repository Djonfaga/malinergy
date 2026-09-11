"""Translation of the water catalogue into a pandapipes network."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandapipes as ppipes

from .catalog import WATER_DENSITY_KG_M3, WaterCatalog, load_water_catalog

#: Water temperature used throughout. The Niger runs at 26-30 degC for most of
#: the year; using 20 degC would understate friction losses by a few per cent.
WATER_TEMPERATURE_K = 300.15

#: Minimum service pressure at a demand node, in bar above atmospheric.
#: Two bar is the usual design figure for a two-storey distribution network.
MIN_SERVICE_PRESSURE_BAR = 2.0


@dataclass
class WaterBuildResult:
    net: ppipes.pandapipesNet
    catalog: WaterCatalog
    junction_index: dict[str, int] = field(default_factory=dict)
    pipe_index: dict[str, int] = field(default_factory=dict)
    pump_index: dict[str, int] = field(default_factory=dict)
    control_index: dict[str, int] = field(default_factory=dict)
    sink_index: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def junction_name(self, index: int) -> str:
        for name, idx in self.junction_index.items():
            if idx == index:
                return name
        return str(index)


def build_water_network(
    catalog: WaterCatalog | None = None,
    *,
    demand_factor: float = 1.0,
    pumps_out_of_service: tuple[str, ...] = (),
    reservoirs_float: bool = False,
) -> WaterBuildResult:
    """Build the Bamako water network.

    Parameters
    ----------
    demand_factor:
        Multiplier on the average demand. Use the ``peak_factor`` of each
        demand record through :func:`peak_demand_factor` for the design case.
    pumps_out_of_service:
        Pump identifiers to trip, for the supply-security study.
    reservoirs_float:
        Treat each service reservoir as a free surface that can supply or
        absorb flow. This is the correct representation of the peak hour: the
        draw-off above average production comes out of storage, not out of the
        pumps. With this off, a peak case asks the plants for an instantaneous
        flow they are not built for and the distribution network shows
        pressures that would never occur.
    """
    catalog = catalog or load_water_catalog()
    net = ppipes.create_empty_network(fluid="water", name="Bamako water supply")
    result = WaterBuildResult(net=net, catalog=catalog)

    for node in catalog.nodes.values():
        index = ppipes.create_junction(
            net,
            pn_bar=node.pressure_bar + MIN_SERVICE_PRESSURE_BAR,
            tfluid_k=WATER_TEMPERATURE_K,
            height_m=node.elevation_m,
            name=node.id,
            in_service=node.in_service,
            geodata=(node.longitude, node.latitude),
        )
        result.junction_index[node.id] = index

    # The river is the pressure reference: a free surface at atmospheric
    # pressure. Everything the network needs above that is pumped. At the peak
    # hour most of the abstraction chain is out of service, so a river is only
    # a reference where a pump downstream of it is still running.
    live_suctions = {
        pump.from_node
        for pump in catalog.pumps.values()
        if pump.in_service
        and pump.id not in pumps_out_of_service
        and (pump.peak_in_service if reservoirs_float else True)
    }
    for node in catalog.nodes.values():
        if node.type == "source" and (not reservoirs_float or node.id in live_suctions):
            ppipes.create_ext_grid(
                net,
                junction=result.junction_index[node.id],
                p_bar=1.0,
                t_k=WATER_TEMPERATURE_K,
                name=f"RIVER_{node.id}",
                type="pt",
            )

    def live(element) -> bool:
        """Is this element in service in the case being built?"""
        if not element.in_service:
            return False
        return element.peak_in_service if reservoirs_float else True

    if reservoirs_float:
        for node in catalog.nodes.values():
            if node.type == "reservoir" and node.in_service:
                ppipes.create_ext_grid(
                    net,
                    junction=result.junction_index[node.id],
                    p_bar=1.0,
                    t_k=WATER_TEMPERATURE_K,
                    name=f"STORAGE_{node.id}",
                    type="pt",
                )
        result.notes.append(
            "service reservoirs are modelled as free surfaces: the flow above "
            "average production is drawn from storage"
        )

    for pipe in catalog.pipes.values():
        index = ppipes.create_pipe_from_parameters(
            net,
            from_junction=result.junction_index[pipe.from_node],
            to_junction=result.junction_index[pipe.to_node],
            length_km=pipe.length_km,
            inner_diameter_mm=pipe.diameter_mm,
            k_mm=pipe.roughness_mm,
            sections=max(int(pipe.length_km) + 1, 1),
            alpha_w_per_m2k=0.0,
            text_k=WATER_TEMPERATURE_K,
            name=pipe.id,
            in_service=live(pipe),
            # Parallel mains are represented by an equivalent diameter so that
            # the friction loss matches; pandapipes has no parallel attribute.
            loss_coefficient=0.0,
        )
        result.pipe_index[pipe.id] = index
        if pipe.parallel > 1:
            # Two mains of diameter D carry the same head loss as one main of
            # D x 2^(2/5): the Darcy-Weisbach exponent, not a linear sum.
            equivalent = pipe.diameter_mm * (pipe.parallel ** (2.0 / 5.0))
            net.pipe.at[index, "inner_diameter_mm"] = equivalent
            result.notes.append(
                f"{pipe.id}: {pipe.parallel} parallel mains represented by an "
                f"equivalent diameter of {equivalent:.0f} mm"
            )

    for pump in catalog.pumps.values():
        in_service = live(pump) and pump.id not in pumps_out_of_service
        # A quadratic head-flow curve through the duty point. pandapipes takes
        # the curve as pressure against volume flow.
        flows = [0.0, pump.total_flow_m3_h * 0.5, pump.total_flow_m3_h,
                 pump.total_flow_m3_h * 1.3]
        heads_bar = [
            pump.head_at_flow(f) * WATER_DENSITY_KG_M3 * 9.81 / 1e5 for f in flows
        ]
        std_type = f"curve_{pump.id}"
        index = ppipes.create_pump_from_parameters(
            net,
            from_junction=result.junction_index[pump.from_node],
            to_junction=result.junction_index[pump.to_node],
            new_std_type_name=std_type,
            pressure_list=heads_bar,
            flowrate_list=flows,
            reg_polynomial_degree=2,
            name=pump.id,
            in_service=in_service,
        )
        result.pump_index[pump.id] = index
        if not in_service:
            result.notes.append(f"{pump.id} is out of service in this case")

    for control in catalog.controls.values():
        if control.type == "flow":
            index = ppipes.create_flow_control(
                net,
                from_junction=result.junction_index[control.from_node],
                to_junction=result.junction_index[control.to_node],
                controlled_mdot_kg_per_s=control.mass_flow_kg_s * demand_factor,
                name=control.id,
                in_service=live(control),
            )
        elif control.type == "pressure":
            index = ppipes.create_pressure_control(
                net,
                from_junction=result.junction_index[control.from_node],
                to_junction=result.junction_index[control.to_node],
                controlled_junction=result.junction_index[control.controlled_node],
                controlled_p_bar=control.setpoint,
                name=control.id,
                in_service=live(control),
            )
        else:
            raise ValueError(f"unknown control type {control.type!r} on {control.id}")
        result.control_index[control.id] = index

    for node_id, demand in catalog.demands.items():
        flow_kg_s = demand.mass_flow_kg_s * demand_factor
        index = ppipes.create_sink(
            net,
            junction=result.junction_index[node_id],
            mdot_kg_per_s=flow_kg_s,
            name=f"DEMAND_{node_id}",
        )
        result.sink_index[node_id] = index

    return result


def peak_demand_factor(catalog: WaterCatalog) -> float:
    """Flow-weighted mean peak factor, for the design case."""
    total = sum(d.average_flow_m3_h for d in catalog.demands.values())
    if total <= 0:
        return 1.0
    return sum(d.peak_flow_m3_h for d in catalog.demands.values()) / total

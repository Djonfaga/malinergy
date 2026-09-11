"""Translation of the canonical exchange file into a pandapower network.

This module makes no engineering decisions. Every impedance, rating, setpoint
and demand value comes from ``mali_case.json``; what happens here is bookkeeping
between two data models. Keeping it that way is what allows a difference
between pandapower and PowerFactory results to be attributed to the tools
rather than to two people building two different networks.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandapower as pp

from mali_energy.config import BASE_MVA, NOMINAL_FREQUENCY_HZ
from mali_energy.exchange import load_exchange

#: Smallest machine allowed to regulate the voltage of its busbar, in MVA.
#:
#: Sotuba is 5.7 MW on a 150 kV busbar. Declaring it a voltage-controlled node
#: asks a 6.7 MVA machine to hold the voltage of the Bamako transmission
#: network: the load flow then demands 148 Mvar from it, and once reactive
#: limits are enforced the case diverges. Machines below this threshold inject
#: at their rated power factor instead, which is how they are actually run.
VOLTAGE_CONTROL_MIN_MVA = 20.0


@dataclass
class BuildResult:
    """A pandapower network plus the index maps needed to read results back."""

    net: pp.pandapowerNet
    case_name: str
    bus_index: dict[str, int] = field(default_factory=dict)
    line_index: dict[str, int] = field(default_factory=dict)
    trafo_index: dict[str, int] = field(default_factory=dict)
    gen_index: dict[str, int] = field(default_factory=dict)
    sgen_index: dict[str, int] = field(default_factory=dict)
    load_index: dict[str, int] = field(default_factory=dict)
    shunt_index: dict[str, int] = field(default_factory=dict)
    ext_grid_index: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def bus_name(self, index: int) -> str:
        for name, idx in self.bus_index.items():
            if idx == index:
                return name
        return str(index)


def build(
    exchange: dict | Path | str,
    case_name: str = "dry_peak",
    *,
    include_out_of_service: bool = False,
) -> BuildResult:
    """Build the pandapower network for one operating point.

    Parameters
    ----------
    exchange:
        The parsed exchange payload or a path to ``mali_case.json``.
    case_name:
        One of the operating points defined by the core package.
    include_out_of_service:
        Keep planned assets (the Guinea link, the Segou-Mopti line, the
        scenario photovoltaic plants) in the network as out-of-service
        elements, so a scenario study can switch them in without rebuilding.
    """
    if isinstance(exchange, (str, Path)):
        exchange = load_exchange(Path(exchange))
    if case_name not in exchange["cases"]:
        raise KeyError(f"case {case_name!r} not in the exchange file")

    network = exchange["network"]
    case = exchange["cases"][case_name]
    config = case["config"]

    net = pp.create_empty_network(
        name=f"Mali interconnected network - {case_name}",
        f_hz=NOMINAL_FREQUENCY_HZ,
        sn_mva=BASE_MVA,
    )
    result = BuildResult(net=net, case_name=case_name)

    # -- buses -------------------------------------------------------------
    for bus in network["buses"]:
        if not bus["in_service"] and not include_out_of_service:
            continue
        index = pp.create_bus(
            net,
            vn_kv=bus["vn_kv"],
            name=bus["id"],
            zone=bus["zone"],
            type="b",
            in_service=bool(bus["in_service"]),
            geodata=(bus["longitude"], bus["latitude"]),
        )
        result.bus_index[bus["id"]] = index

    # -- lines -------------------------------------------------------------
    for line in network["lines"]:
        if line["from_bus"] not in result.bus_index or line["to_bus"] not in result.bus_index:
            continue
        if not line["in_service"] and not include_out_of_service:
            continue
        index = pp.create_line_from_parameters(
            net,
            from_bus=result.bus_index[line["from_bus"]],
            to_bus=result.bus_index[line["to_bus"]],
            length_km=line["length_km"],
            r_ohm_per_km=line["r_ohm_per_km"],
            x_ohm_per_km=line["x_ohm_per_km"],
            c_nf_per_km=line["c_nf_per_km"],
            r0_ohm_per_km=line["r0_ohm_per_km"],
            x0_ohm_per_km=line["x0_ohm_per_km"],
            c0_nf_per_km=line["c0_nf_per_km"],
            max_i_ka=line["max_i_ka"],
            parallel=line["circuits"],
            name=line["id"],
            in_service=bool(line["in_service"]),
            type="ol",
            # Endtemp is what pandapower uses for the short-circuit resistance
            # correction; the catalogue already evaluates R at 75 degC.
            endtemp_degree=80.0,
        )
        result.line_index[line["id"]] = index

    # -- transformers ------------------------------------------------------
    for trafo in network["transformers"]:
        if trafo["hv_bus"] not in result.bus_index or trafo["lv_bus"] not in result.bus_index:
            continue
        if not trafo["in_service"] and not include_out_of_service:
            continue
        hv = net.bus.at[result.bus_index[trafo["hv_bus"]], "vn_kv"]
        lv = net.bus.at[result.bus_index[trafo["lv_bus"]], "vn_kv"]
        index = pp.create_transformer_from_parameters(
            net,
            hv_bus=result.bus_index[trafo["hv_bus"]],
            lv_bus=result.bus_index[trafo["lv_bus"]],
            sn_mva=trafo["sn_mva"],
            vn_hv_kv=hv,
            vn_lv_kv=lv,
            vkr_percent=trafo["vkr_percent"],
            vk_percent=trafo["vk_percent"],
            pfe_kw=trafo["pfe_kw"],
            i0_percent=trafo["i0_percent"],
            shift_degree=330.0 if trafo["vector_group"].endswith("11") else 0.0,
            # pandapower wants the vector group without the clock number, which
            # it takes separately as shift_degree. The neutral letters must be
            # kept: an earthed star and an unearthed one have entirely
            # different zero-sequence behaviour, and dropping the N silently
            # changes every earth-fault current in the study.
            vector_group=re.sub(r"\d+$", "", trafo["vector_group"]),
            tap_side=trafo["tap_side"],
            tap_neutral=trafo["tap_neutral"],
            tap_min=trafo["tap_min"],
            tap_max=trafo["tap_max"],
            tap_step_percent=trafo["tap_step_percent"],
            tap_pos=trafo["tap_neutral"],
            parallel=trafo["parallel"],
            name=trafo["id"],
            in_service=bool(trafo["in_service"]),
            # Zero-sequence data, required for unbalanced and earth-fault studies.
            vk0_percent=trafo["vk_percent"],
            vkr0_percent=trafo["vkr_percent"],
            mag0_percent=100.0,
            mag0_rx=0.0,
            si0_hv_partial=0.9,
        )
        result.trafo_index[trafo["id"]] = index

    # -- loads -------------------------------------------------------------
    for load_id, load in case["loads"].items():
        if load["bus"] not in result.bus_index:
            continue
        index = pp.create_load(
            net,
            bus=result.bus_index[load["bus"]],
            p_mw=load["p_mw"],
            q_mvar=load["q_mvar"],
            name=load_id,
            # Constant power is the conservative assumption for a planning
            # study: voltage-dependent load would relieve the low-voltage
            # cases and understate the problem.
            const_z_percent=0.0,
            const_i_percent=0.0,
        )
        result.load_index[load_id] = index

    # -- shunt compensation ------------------------------------------------
    for shunt in network.get("shunts", []):
        if shunt["bus"] not in result.bus_index:
            continue
        if not shunt["in_service"] and not include_out_of_service:
            continue
        bus = result.bus_index[shunt["bus"]]
        sign = 1.0 if shunt["type"] == "capacitor" else -1.0
        index = pp.create_shunt(
            net,
            bus=bus,
            # pandapower multiplies q_mvar by the step number, so q_mvar is the
            # rating of one step and the number of connected steps goes in
            # "step". It also takes q_mvar as consumed reactive power, so a
            # capacitor bank carries a negative value.
            q_mvar=-sign * shunt["q_mvar_per_step"],
            p_mw=0.0,
            vn_kv=net.bus.at[bus, "vn_kv"],
            step=max(int(shunt["steps_in_service"]), 1),
            max_step=shunt["steps"],
            name=shunt["id"],
            in_service=bool(shunt["in_service"]) and shunt["steps_in_service"] > 0,
        )
        result.shunt_index[shunt["id"]] = index

    # -- generation --------------------------------------------------------
    generators = {g["id"]: g for g in network["generators"]}
    slack_bus_id = config["slack_bus"]
    slack_assigned = False

    for gen_id, setpoint in case["generators"].items():
        record = generators[gen_id]
        bus_id = setpoint["bus"]
        if bus_id not in result.bus_index:
            continue
        bus = result.bus_index[bus_id]

        if setpoint["technology"] in {"solar", "storage"}:
            # Inverter-based plant: a static generator with no voltage control,
            # which is how these plants are actually operated in Mali today.
            index = pp.create_sgen(
                net,
                bus=bus,
                p_mw=setpoint["p_mw"],
                q_mvar=0.0,
                sn_mva=record["sn_mva"],
                name=gen_id,
                type="PV" if setpoint["technology"] == "solar" else "storage",
                in_service=bool(record["in_service"]) and setpoint["p_mw"] > 0,
                # Fault contribution of a current-limited converter, per the
                # IEC 60909 treatment of inverter-based sources.
                k=1.2,
                current_source=True,
            )
            result.sgen_index[gen_id] = index
            continue

        if bus_id == slack_bus_id and not slack_assigned and setpoint["p_mw"] > 0:
            index = pp.create_ext_grid(
                net,
                bus=bus,
                vm_pu=setpoint["target_vm_pu"] or 1.02,
                va_degree=0.0,
                name=f"SLACK_{gen_id}",
                # Short-circuit data of the machine acting as slack.
                s_sc_max_mva=record["sn_mva"] / max(record["xdpp_pu"], 0.05),
                s_sc_min_mva=record["sn_mva"] / max(record["xdpp_pu"], 0.05) * 0.8,
                rx_max=0.1,
                rx_min=0.1,
                x0x_max=3.0,
                r0x0_max=0.1,
                x0x_min=3.0,
                r0x0_min=0.1,
            )
            result.ext_grid_index[gen_id] = index
            slack_assigned = True
            result.notes.append(f"{gen_id} carries the slack at {bus_id}")
            continue

        if record["sn_mva"] < VOLTAGE_CONTROL_MIN_MVA:
            index = pp.create_sgen(
                net,
                bus=bus,
                p_mw=setpoint["p_mw"],
                q_mvar=setpoint["p_mw"] * math.tan(math.acos(record["cos_phi"])),
                sn_mva=record["sn_mva"],
                name=gen_id,
                type=setpoint["technology"],
                in_service=bool(record["in_service"]) and setpoint["p_mw"] > 0,
                k=1.8,
                current_source=False,
            )
            result.sgen_index[gen_id] = index
            result.notes.append(
                f"{gen_id} ({record['sn_mva']:.1f} MVA) injects at its rated power "
                "factor rather than regulating voltage"
            )
            continue

        index = pp.create_gen(
            net,
            bus=bus,
            p_mw=setpoint["p_mw"],
            vm_pu=setpoint["target_vm_pu"] or 1.0,
            sn_mva=record["sn_mva"],
            name=gen_id,
            min_p_mw=record["min_load_mw"],
            max_p_mw=setpoint["available_mw"],
            max_q_mvar=record["sn_mva"] * math.sin(math.acos(record["cos_phi"])),
            min_q_mvar=-record["sn_mva"] * math.sin(math.acos(record["cos_phi"])) * 0.6,
            in_service=bool(record["in_service"]) and setpoint["p_mw"] > 0,
            slack=False,
            # Machine data for IEC 60909 and for the dynamic branches.
            vn_kv=net.bus.at[bus, "vn_kv"],
            xdss_pu=max(record["xdpp_pu"], 0.05),
            rdss_ohm=0.0015 * net.bus.at[bus, "vn_kv"] ** 2 / max(record["sn_mva"], 1.0),
            cos_phi=record["cos_phi"],
            power_station_trafo=None,
        )
        result.gen_index[gen_id] = index

    # -- interconnections --------------------------------------------------
    for link in network["interconnections"]:
        bus_id = link["bus"]
        if bus_id not in result.bus_index:
            continue
        flow = case["interchange_mw"].get(link["id"], 0.0)
        bus = result.bus_index[bus_id]
        if not link["in_service"]:
            continue
        if not slack_assigned:
            index = pp.create_ext_grid(
                net, bus=bus, vm_pu=1.0, name=f"SLACK_{link['id']}"
            )
            result.ext_grid_index[link["id"]] = index
            slack_assigned = True
            continue
        # A neighbouring system is a voltage source delivering a scheduled
        # power: a PV bus, not a swing bus and not a plain injection.
        #
        # Modelling it as an infinite bus would let Cote d'Ivoire absorb the
        # Malian deficit and the study would report a system that never sheds
        # load. Modelling it as a fixed injection at a radial dead-end busbar
        # is just as wrong in the other direction: pushing 90 MW down 228 km of
        # line from a bus with no voltage support drives that bus to 1.4 pu.
        index = pp.create_gen(
            net,
            bus=bus,
            p_mw=flow,
            vm_pu=1.0,
            sn_mva=link["capacity_mw"],
            name=link["id"],
            min_p_mw=-link["capacity_mw"],
            max_p_mw=link["capacity_mw"],
            # A neighbouring national grid is a stiff node. Limiting its
            # reactive capability to a fraction of the scheduled transfer is
            # an artefact: when the limit binds, the border busbar sags to
            # 0.86 pu and the Malian result inherits a problem that belongs to
            # the model rather than to the system.
            max_q_mvar=link["capacity_mw"],
            min_q_mvar=-link["capacity_mw"],
            controllable=False,
            slack=False,
            type="interconnection",
            # Fault contribution of the neighbouring system, expressed as a
            # subtransient reactance on the interconnection rating. Without
            # it the IEC 60909 calculation divides by an undefined impedance
            # and every busbar current comes back as "not a number".
            vn_kv=net.bus.at[bus, "vn_kv"],
            xdss_pu=0.10,
            rdss_ohm=0.01 * net.bus.at[bus, "vn_kv"] ** 2 / max(link["capacity_mw"], 1.0),
            cos_phi=0.90,
        )
        result.gen_index[link["id"]] = index

    if not slack_assigned:
        raise ValueError(
            f"no slack could be assigned for case {case_name}: the slack bus "
            f"{slack_bus_id} carries no dispatched generation"
        )

    # -- unserved energy ---------------------------------------------------
    unserved = case["balance"].get("unserved_mw", 0.0)
    if unserved > 0.5:
        result.notes.append(
            f"{unserved:.1f} MW of demand is unserved at this operating point. "
            "The load flow below represents the network *after* that shedding "
            "has been applied pro rata; see apply_load_shedding()."
        )
    return result


def apply_load_shedding(result: BuildResult, unserved_mw: float) -> float:
    """Shed ``unserved_mw`` pro rata across the loads and return what was shed.

    A load flow of a case whose generation cannot meet demand is meaningless
    unless the shortfall is represented. Malian practice is rotating feeder
    disconnection, so the shortfall is removed proportionally rather than by
    dropping whole busbars, which would distort the flows.
    """
    net = result.net
    total = float(net.load.p_mw.sum())
    if total <= 0 or unserved_mw <= 0:
        return 0.0
    factor = max(0.0, 1.0 - unserved_mw / total)
    net.load["p_mw"] = net.load["p_mw"] * factor
    net.load["q_mvar"] = net.load["q_mvar"] * factor
    shed = total - float(net.load.p_mw.sum())
    result.notes.append(f"applied {shed:.1f} MW of pro rata load shedding")
    return shed


def build_all(exchange: dict | Path | str, **kwargs) -> dict[str, BuildResult]:
    """Build every operating point present in the exchange file."""
    if isinstance(exchange, (str, Path)):
        exchange = load_exchange(Path(exchange))
    return {name: build(exchange, name, **kwargs) for name in exchange["cases"]}

"""Photovoltaic hosting capacity.

How much photovoltaic power can be connected at a given busbar before a limit
is reached? The question decides where the next plant should go, and the
answer in Mali is rarely the same as the answer in a European network: the
binding constraint here is usually thermal loading on a long radial corridor
or reverse flow through a regional transformer, not the voltage rise that
dominates dense low-voltage networks.

The search is a bisection on injected power, re-solving the load flow at each
step, applied at the minimum-load operating point where hosting capacity is
lowest.
"""

from __future__ import annotations

import pandas as pd

import pandapower as pp
from mali_energy.config import VOLTAGE_LIMITS_PU

from ..builder import build
from ..operations import switch_shunts


def _limits_respected(net, voltage_limits, loading_limit) -> tuple[bool, str]:
    low, high = voltage_limits
    if float(net.res_bus.vm_pu.max()) > high:
        bus = net.bus.at[int(net.res_bus.vm_pu.idxmax()), "name"]
        return False, f"overvoltage at {bus}"
    if float(net.res_bus.vm_pu.min()) < low:
        bus = net.bus.at[int(net.res_bus.vm_pu.idxmin()), "name"]
        return False, f"undervoltage at {bus}"
    if float(net.res_line.loading_percent.max()) > loading_limit:
        line = net.line.at[int(net.res_line.loading_percent.idxmax()), "name"]
        return False, f"thermal limit on {line}"
    if len(net.res_trafo) and float(net.res_trafo.loading_percent.max()) > loading_limit:
        trafo = net.trafo.at[int(net.res_trafo.loading_percent.idxmax()), "name"]
        return False, f"thermal limit on {trafo}"
    return True, ""


def hosting_capacity(
    exchange: dict,
    *,
    case_name: str = "night_min",
    voltage_limits: tuple[float, float] = VOLTAGE_LIMITS_PU,
    loading_limit: float = 100.0,
    max_mw: float = 600.0,
    tolerance_mw: float = 5.0,
    buses: list[str] | None = None,
) -> pd.DataFrame:
    """Maximum additional photovoltaic injection at each candidate busbar.

    Parameters
    ----------
    case_name:
        Operating point to test against. ``night_min`` is the conservative
        choice for daytime injection studies because it combines low demand
        with the network configuration of the wet season; run ``solar_noon``
        as well to see the realistic case.
    """
    # The base case has to be brought into its normal operating state before
    # anything is added to it. Without the capacitor switching a control room
    # would do at light load, every candidate busbar reports zero hosting
    # capacity because the network is already outside its voltage band.
    template = build(exchange, case_name)
    switch_shunts(template, voltage_band=(voltage_limits[0] + 0.02, voltage_limits[1] - 0.02))
    base_shunt_state = template.net.shunt[["step", "in_service"]].copy()

    candidates = buses or [
        name
        for name, index in template.bus_index.items()
        if template.net.bus.at[index, "vn_kv"] >= 33.0
        and template.net.bus.at[index, "in_service"]
        and "External" not in str(template.net.bus.at[index, "zone"])
    ]

    rows: list[dict] = []
    for bus_name in candidates:
        low, high = 0.0, max_mw
        binding = "none within search range"

        while high - low > tolerance_mw:
            trial = (low + high) / 2.0
            result = build(exchange, case_name)
            net = result.net
            net.shunt[["step", "in_service"]] = base_shunt_state
            pp.create_sgen(
                net,
                bus=result.bus_index[bus_name],
                p_mw=trial,
                q_mvar=0.0,
                name="HOSTING_TEST",
                type="PV",
            )
            try:
                # Let the substations respond to the new injection, as they
                # would in service, before judging whether a limit is breached.
                switch_shunts(
                    result,
                    voltage_band=(voltage_limits[0] + 0.02, voltage_limits[1] - 0.02),
                    max_rounds=5,
                )
                pp.runpp(net, calculate_voltage_angles=True, init="dc", max_iteration=40)
                ok, reason = _limits_respected(net, voltage_limits, loading_limit)
            except pp.LoadflowNotConverged:
                ok, reason = False, "load flow did not converge"

            if ok:
                low = trial
            else:
                high = trial
                binding = reason

        rows.append(
            {
                "bus": bus_name,
                "vn_kv": float(template.net.bus.at[template.bus_index[bus_name], "vn_kv"]),
                "zone": str(template.net.bus.at[template.bus_index[bus_name], "zone"]),
                "hosting_capacity_mw": round(low, 1),
                "binding_constraint": binding,
            }
        )

    frame = pd.DataFrame(rows)
    return frame.sort_values("hosting_capacity_mw", ascending=False).reset_index(drop=True)

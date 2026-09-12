"""N-1 contingency screening.

Every in-service line and transformer is removed in turn and the case is
re-solved. Three outcomes are recorded, and the distinction between them is
the point of the exercise:

* **secure** — no limit exceeded;
* **violated** — the network still solves but a voltage or a thermal limit is
  breached, so the outage is survivable with post-fault action;
* **non-convergent** — no solution exists, which for a radial corridor means
  the load beyond it is simply lost.

A single-circuit radial system like the Malian one produces a lot of the third
kind, and reporting those as "not converged" without saying which demand goes
dark would understate the consequence. The screening therefore also reports
the demand isolated by each outage.
"""

from __future__ import annotations

import pandapower.topology as top
import pandas as pd

import pandapower as pp
from mali_energy.config import (
    LOADING_LIMIT_CONTINGENCY_PCT,
    VOLTAGE_LIMITS_PU_EMERGENCY,
)

from ..builder import apply_load_shedding, build


def _isolated_demand_mw(net) -> float:
    """Demand that no longer has a path to a source."""
    graph = top.create_nxgraph(net, respect_switches=True)
    supplied = set()
    for bus in list(net.ext_grid.bus[net.ext_grid.in_service]) + list(
        net.gen.bus[net.gen.in_service]
    ):
        if bus in graph:
            supplied.update(top.connected_component(graph, bus))
    lost = net.load[
        net.load.in_service & ~net.load.bus.isin(supplied)
    ]
    return float(lost.p_mw.sum())


def run_n1(
    exchange: dict,
    case_name: str = "dry_peak",
    *,
    voltage_limits: tuple[float, float] = VOLTAGE_LIMITS_PU_EMERGENCY,
    loading_limit: float = LOADING_LIMIT_CONTINGENCY_PCT,
    include_transformers: bool = True,
) -> pd.DataFrame:
    """Screen every single branch outage for the given operating point."""
    case = exchange["cases"][case_name]
    low, high = voltage_limits
    rows: list[dict] = []

    base = build(exchange, case_name)
    apply_load_shedding(base, case["balance"].get("unserved_mw", 0.0))
    try:
        pp.runpp(base.net, calculate_voltage_angles=True, init="dc", max_iteration=50)
        base_losses = float(base.net.res_line.pl_mw.sum() + base.net.res_trafo.pl_mw.sum())
    except pp.LoadflowNotConverged as error:
        raise RuntimeError(
            f"the base case {case_name} does not converge; fix it before screening outages"
        ) from error

    outages: list[tuple[str, str, int]] = [
        ("line", str(base.net.line.at[i, "name"]), i)
        for i in base.net.line.index
        if base.net.line.at[i, "in_service"]
    ]
    if include_transformers:
        outages += [
            ("transformer", str(base.net.trafo.at[i, "name"]), i)
            for i in base.net.trafo.index
            if base.net.trafo.at[i, "in_service"]
        ]

    for element, name, index in outages:
        result = build(exchange, case_name)
        apply_load_shedding(result, case["balance"].get("unserved_mw", 0.0))
        net = result.net
        table = net.line if element == "line" else net.trafo
        table.at[index, "in_service"] = False

        isolated = _isolated_demand_mw(net)
        row = {
            "case": case_name,
            "element": element,
            "outage": name,
            "isolated_demand_mw": round(isolated, 2),
        }
        try:
            pp.runpp(net, calculate_voltage_angles=True, init="dc", max_iteration=50)
        except pp.LoadflowNotConverged:
            row.update(
                {
                    "status": "non-convergent",
                    "vm_min_pu": None,
                    "vm_max_pu": None,
                    "max_loading_pct": None,
                    "delta_losses_mw": None,
                    "worst_element": "",
                    "violations": None,
                }
            )
            rows.append(row)
            continue

        vm_min = float(net.res_bus.vm_pu.min())
        vm_max = float(net.res_bus.vm_pu.max())
        line_loading = float(net.res_line.loading_percent.max())
        trafo_loading = float(net.res_trafo.loading_percent.max())
        if line_loading >= trafo_loading:
            max_loading, worst = line_loading, str(
                net.line.at[int(net.res_line.loading_percent.idxmax()), "name"]
            )
        else:
            max_loading, worst = trafo_loading, str(
                net.trafo.at[int(net.res_trafo.loading_percent.idxmax()), "name"]
            )

        violations = 0
        violations += int((net.res_bus.vm_pu < low).sum())
        violations += int((net.res_bus.vm_pu > high).sum())
        violations += int((net.res_line.loading_percent > loading_limit).sum())
        violations += int((net.res_trafo.loading_percent > loading_limit).sum())

        losses = float(net.res_line.pl_mw.sum() + net.res_trafo.pl_mw.sum())
        row.update(
            {
                "status": "violated" if violations else "secure",
                "vm_min_pu": round(vm_min, 4),
                "vm_max_pu": round(vm_max, 4),
                "max_loading_pct": round(max_loading, 1),
                "delta_losses_mw": round(losses - base_losses, 3),
                "worst_element": worst,
                "violations": violations,
            }
        )
        rows.append(row)

    frame = pd.DataFrame(rows)
    order = {"non-convergent": 0, "violated": 1, "secure": 2}
    frame["_order"] = frame["status"].map(order)
    frame = frame.sort_values(
        ["_order", "isolated_demand_mw", "violations"], ascending=[True, False, False]
    ).drop(columns="_order")
    return frame.reset_index(drop=True)


def critical_outages(frame: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """The outages a planner would act on first."""
    critical = frame[frame["status"] != "secure"]
    return critical.head(top_n).reset_index(drop=True)

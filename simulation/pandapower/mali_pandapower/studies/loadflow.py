"""Steady-state load flow on the four canonical operating points."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

import pandapower as pp
from mali_energy.config import LOADING_LIMIT_NORMAL_PCT, VOLTAGE_LIMITS_PU

from ..builder import BuildResult, apply_load_shedding, build
from ..operations import OperationLog, operate


@dataclass
class LoadFlowResult:
    case: str
    converged: bool
    build: BuildResult
    shed_mw: float = 0.0
    iterations: int = 0
    violations: pd.DataFrame = field(default_factory=pd.DataFrame)
    summary: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    operations: OperationLog | None = None

    @property
    def net(self):
        return self.build.net


def _violations(
    result: BuildResult,
    voltage_limits: tuple[float, float],
    loading_limit: float,
) -> pd.DataFrame:
    net = result.net
    rows: list[dict] = []
    low, high = voltage_limits

    for index, row in net.res_bus.iterrows():
        if pd.isna(row.vm_pu):
            continue
        name = net.bus.at[index, "name"]
        if row.vm_pu < low:
            rows.append({"element": "bus", "name": name, "quantity": "voltage",
                         "value": round(row.vm_pu, 4), "limit": low,
                         "severity": round((low - row.vm_pu) / low * 100, 2)})
        elif row.vm_pu > high:
            rows.append({"element": "bus", "name": name, "quantity": "voltage",
                         "value": round(row.vm_pu, 4), "limit": high,
                         "severity": round((row.vm_pu - high) / high * 100, 2)})

    for index, row in net.res_line.iterrows():
        if pd.isna(row.loading_percent) or row.loading_percent <= loading_limit:
            continue
        rows.append({"element": "line", "name": net.line.at[index, "name"],
                     "quantity": "loading", "value": round(row.loading_percent, 1),
                     "limit": loading_limit,
                     "severity": round(row.loading_percent - loading_limit, 1)})

    for index, row in net.res_trafo.iterrows():
        if pd.isna(row.loading_percent) or row.loading_percent <= loading_limit:
            continue
        rows.append({"element": "transformer", "name": net.trafo.at[index, "name"],
                     "quantity": "loading", "value": round(row.loading_percent, 1),
                     "limit": loading_limit,
                     "severity": round(row.loading_percent - loading_limit, 1)})

    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.sort_values("severity", ascending=False).reset_index(drop=True)
    return frame


def run_case(
    exchange: dict,
    case_name: str,
    *,
    voltage_limits: tuple[float, float] = VOLTAGE_LIMITS_PU,
    loading_limit: float = LOADING_LIMIT_NORMAL_PCT,
    shed_unserved: bool = True,
    algorithm: str = "nr",
    switch_capacitors: bool = True,
    loss_consistent_dispatch: bool = True,
) -> LoadFlowResult:
    """Solve one operating point and collect the diagnostics that matter.

    Load shedding is applied before solving when the dispatch cannot meet
    demand. Solving the unshed case would either fail to converge or, worse,
    converge with the deficit silently supplied by the slack machine.
    """
    result = build(exchange, case_name)
    case = exchange["cases"][case_name]
    shed = 0.0
    if shed_unserved:
        shed = apply_load_shedding(result, case["balance"].get("unserved_mw", 0.0))

    net = result.net
    operations = operate(
        result,
        exchange,
        case_name,
        switch_capacitors=switch_capacitors,
        loss_consistent_dispatch=loss_consistent_dispatch,
    )
    converged = operations.converged
    if converged:
        try:
            pp.runpp(
                net,
                algorithm=algorithm,
                calculate_voltage_angles=True,
                init="dc",
                max_iteration=50,
                enforce_q_lims=not operations.q_limits_relaxed,
            )
        except pp.LoadflowNotConverged:
            converged = False

    lf = LoadFlowResult(
        case=case_name, converged=converged, build=result, shed_mw=shed, operations=operations
    )
    lf.notes.extend(result.notes)
    lf.notes.extend(operations.notes)
    lf.iterations = operations.iterations
    if not converged:
        lf.notes.append(
            "load flow did not converge; the operating point is not feasible "
            "with this dispatch and network"
        )
        return lf

    losses_mw = float(net.res_line.pl_mw.sum() + net.res_trafo.pl_mw.sum())
    demand_mw = float(net.res_load.p_mw.sum())
    slack_mw = float(net.res_ext_grid.p_mw.sum())

    lf.violations = _violations(result, voltage_limits, loading_limit)
    lf.summary = {
        "case": case_name,
        "description": case["description"],
        "timestamp": case["timestamp"],
        "demand_mw": round(demand_mw, 2),
        "demand_mvar": round(float(net.res_load.q_mvar.sum()), 2),
        "shed_mw": round(shed, 2),
        "generation_mw": round(
            float(net.res_gen.p_mw.sum() + net.res_sgen.p_mw.sum() + slack_mw), 2
        ),
        "slack_mw": round(slack_mw, 2),
        "losses_mw": round(losses_mw, 3),
        "losses_pct": round(100.0 * losses_mw / demand_mw, 2) if demand_mw else 0.0,
        "line_losses_mw": round(float(net.res_line.pl_mw.sum()), 3),
        "transformer_losses_mw": round(float(net.res_trafo.pl_mw.sum()), 3),
        "reactive_losses_mvar": round(
            float(net.res_line.ql_mvar.sum() + net.res_trafo.ql_mvar.sum()), 2
        ),
        "vm_min_pu": round(float(net.res_bus.vm_pu.min()), 4),
        "vm_min_bus": result.bus_name(int(net.res_bus.vm_pu.idxmin())),
        "vm_max_pu": round(float(net.res_bus.vm_pu.max()), 4),
        "vm_max_bus": result.bus_name(int(net.res_bus.vm_pu.idxmax())),
        "max_line_loading_pct": round(float(net.res_line.loading_percent.max()), 1),
        "max_line": str(net.line.at[int(net.res_line.loading_percent.idxmax()), "name"]),
        "max_trafo_loading_pct": round(float(net.res_trafo.loading_percent.max()), 1),
        "violations": len(lf.violations),
        "dispatch_iterations": operations.iterations,
        "slack_mismatch_mw": operations.residual_mismatch_mw,
        "capacitor_actions": len(operations.shunt_actions),
        "q_limits_relaxed": operations.q_limits_relaxed,
        "reactive_shortfall_mvar": round(
            float(operations.reactive_shortfall["shortfall_mvar"].abs().sum()), 1
        )
        if not operations.reactive_shortfall.empty
        else 0.0,
        "compensation_mvar": round(float(net.res_shunt.q_mvar.sum()) * -1.0, 1)
        if len(net.res_shunt)
        else 0.0,
    }

    # The slack machine must stay inside the power it was scheduled to have.
    # If it does not, the case is balanced by a machine that cannot deliver.
    for gen_id in result.ext_grid_index:
        clean_id = gen_id.replace("SLACK_", "")
        setpoint = case["generators"].get(clean_id)
        if not setpoint:
            continue
        available = setpoint["available_mw"]
        if slack_mw > available + 1.0:
            lf.notes.append(
                f"the slack machine {clean_id} settles at {slack_mw:.1f} MW against "
                f"{available:.1f} MW available: the network loses more than the "
                "dispatch allowed for, and the balance is not physically covered"
            )
        elif slack_mw < setpoint["p_mw"] - 1.0:
            lf.notes.append(
                f"the slack machine {clean_id} backs down to {slack_mw:.1f} MW from a "
                f"scheduled {setpoint['p_mw']:.1f} MW: the dispatch over-generates"
            )
    return lf


def run_all_cases(exchange: dict, **kwargs) -> dict[str, LoadFlowResult]:
    """Solve every operating point in the exchange file."""
    return {name: run_case(exchange, name, **kwargs) for name in exchange["cases"]}


def voltage_profile(result: LoadFlowResult) -> pd.DataFrame:
    """Bus voltages sorted by voltage level, for plotting or tabulation."""
    net = result.net
    frame = pd.DataFrame(
        {
            "bus": net.bus.name,
            "vn_kv": net.bus.vn_kv,
            "zone": net.bus.zone,
            "vm_pu": net.res_bus.vm_pu,
            "va_degree": net.res_bus.va_degree,
            "p_mw": net.res_bus.p_mw,
            "q_mvar": net.res_bus.q_mvar,
        }
    )
    return frame.sort_values(["vn_kv", "vm_pu"], ascending=[False, True]).reset_index(drop=True)


def branch_flows(result: LoadFlowResult) -> pd.DataFrame:
    """Line and transformer flows with loading and losses."""
    net = result.net
    lines = pd.DataFrame(
        {
            "element": "line",
            "name": net.line.name,
            "from": net.bus.name[net.line.from_bus].to_numpy(),
            "to": net.bus.name[net.line.to_bus].to_numpy(),
            "vn_kv": net.bus.vn_kv[net.line.from_bus].to_numpy(),
            "length_km": net.line.length_km,
            "p_from_mw": net.res_line.p_from_mw,
            "q_from_mvar": net.res_line.q_from_mvar,
            "loading_percent": net.res_line.loading_percent,
            "losses_mw": net.res_line.pl_mw,
        }
    )
    trafos = pd.DataFrame(
        {
            "element": "transformer",
            "name": net.trafo.name,
            "from": net.bus.name[net.trafo.hv_bus].to_numpy(),
            "to": net.bus.name[net.trafo.lv_bus].to_numpy(),
            "vn_kv": net.trafo.vn_hv_kv,
            "length_km": 0.0,
            "p_from_mw": net.res_trafo.p_hv_mw,
            "q_from_mvar": net.res_trafo.q_hv_mvar,
            "loading_percent": net.res_trafo.loading_percent,
            "losses_mw": net.res_trafo.pl_mw,
        }
    )
    frame = pd.concat([lines, trafos], ignore_index=True)
    return frame.sort_values("loading_percent", ascending=False).reset_index(drop=True)

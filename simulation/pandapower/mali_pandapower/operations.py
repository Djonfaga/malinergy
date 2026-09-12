"""Operator actions that a load flow alone does not perform.

pandapower solves the network it is given. Two things a real control centre
does between solutions have to be written out explicitly here, and both change
the answer materially:

* **Capacitor switching.** Banks sized for the evening peak drive the network
  above its voltage limit at four in the morning. Leaving every step connected
  all year produces overvoltages that do not exist, and switching them all out
  produces a voltage collapse at peak that does not exist either.
* **Loss-consistent dispatch.** The dispatch in the exchange file allows a
  flat percentage for network losses. The load flow then computes what the
  losses actually are, which in this network ranges from under 4 % in the dry
  season to nearly 9 % when the western hydro is running and the power has to
  cross the country on a single circuit. The difference lands on the slack
  machine, which quietly exceeds what it is able to deliver unless the
  dispatch is corrected and the case re-solved.

Writing these out is also part of the comparison the repository exists for:
PowerFactory performs both as built-in station controllers and an active power
balancing option, and what that convenience is worth is one of the questions
the study asks.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

import pandapower as pp

from .builder import BuildResult


@dataclass
class OperationLog:
    """What was changed, so a result can be explained."""

    shunt_actions: list[str] = field(default_factory=list)
    dispatch_actions: list[str] = field(default_factory=list)
    iterations: int = 0
    converged: bool = True
    q_limits_relaxed: bool = False
    reactive_shortfall: pd.DataFrame = field(default_factory=pd.DataFrame)
    final_losses_mw: float = 0.0
    residual_mismatch_mw: float = 0.0

    @property
    def notes(self) -> list[str]:
        return self.shunt_actions + self.dispatch_actions


def _solve(net, *, enforce_q_lims: bool = True) -> bool:
    try:
        pp.runpp(
            net,
            calculate_voltage_angles=True,
            init="dc",
            max_iteration=50,
            enforce_q_lims=enforce_q_lims,
        )
        return True
    except pp.LoadflowNotConverged:
        return False


def reactive_shortfall(net) -> pd.DataFrame:
    """Machines asked for more reactive power than they can deliver.

    Called after a solution obtained with reactive limits relaxed. The result
    is the quantity a planner needs: not "the case did not converge" but "this
    busbar is short of so many Mvar".
    """
    rows: list[dict] = []
    for index in net.gen.index:
        if not bool(net.gen.at[index, "in_service"]):
            continue
        q = float(net.res_gen.at[index, "q_mvar"])
        low = float(net.gen.at[index, "min_q_mvar"])
        high = float(net.gen.at[index, "max_q_mvar"])
        if q > high + 0.1 or q < low - 0.1:
            excess = q - high if q > high else q - low
            rows.append(
                {
                    "generator": str(net.gen.at[index, "name"]),
                    "bus": str(net.bus.at[int(net.gen.at[index, "bus"]), "name"]),
                    "q_required_mvar": round(q, 1),
                    "q_limit_mvar": round(high if q > high else low, 1),
                    "shortfall_mvar": round(excess, 1),
                }
            )
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.reindex(
            frame["shortfall_mvar"].abs().sort_values(ascending=False).index
        ).reset_index(drop=True)
    return frame


def switch_shunts(
    result: BuildResult,
    *,
    voltage_band: tuple[float, float] = (0.97, 1.03),
    max_rounds: int = 8,
    log: OperationLog | None = None,
) -> OperationLog:
    """Switch capacitor steps to bring busbar voltages into ``voltage_band``.

    One step per bank per round, the way a substation voltage regulator works,
    rather than solving for an optimum that no operator could implement.
    """
    log = log or OperationLog()
    net = result.net
    low, high = voltage_band

    if not len(net.shunt):
        return log

    # A bank that has been asked to move in both directions is oscillating:
    # its busbar voltage cannot be brought inside the band by switching it, so
    # it is left alone and the condition is reported instead of being chased.
    history: dict[int, set[str]] = {index: set() for index in net.shunt.index}
    settled: set[int] = set()

    relax = bool(log.q_limits_relaxed)
    for _ in range(max_rounds):
        if not _solve(net, enforce_q_lims=not relax):
            log.converged = False
            return log

        changed = False
        for index in net.shunt.index:
            if index in settled:
                continue
            bus = int(net.shunt.at[index, "bus"])
            name = str(net.shunt.at[index, "name"])
            vm = float(net.res_bus.at[bus, "vm_pu"])
            step = int(net.shunt.at[index, "step"])
            max_step = int(net.shunt.at[index, "max_step"])
            in_service = bool(net.shunt.at[index, "in_service"])

            if vm > high and (step > 1 or in_service):
                if step > 1:
                    net.shunt.at[index, "step"] = step - 1
                else:
                    net.shunt.at[index, "in_service"] = False
                history[index].add("down")
                log.shunt_actions.append(
                    f"{name}: stepped down at {vm:.3f} pu on {result.bus_name(bus)}"
                )
                changed = True
            elif vm < low and (not in_service or step < max_step):
                if not in_service:
                    net.shunt.at[index, "in_service"] = True
                else:
                    net.shunt.at[index, "step"] = step + 1
                history[index].add("up")
                log.shunt_actions.append(
                    f"{name}: stepped up at {vm:.3f} pu on {result.bus_name(bus)}"
                )
                changed = True

            if len(history[index]) > 1:
                settled.add(index)
                log.shunt_actions.append(
                    f"{name}: left as found, switching it does not bring "
                    f"{result.bus_name(bus)} inside the band"
                )

        if not changed:
            break

    if _solve(net, enforce_q_lims=not relax):
        out_of_band = net.res_bus[
            (net.res_bus.vm_pu > high) | (net.res_bus.vm_pu < low)
        ]
        if len(out_of_band):
            worst = net.bus.at[int(out_of_band.vm_pu.idxmax()), "name"]
            log.shunt_actions.append(
                f"{len(out_of_band)} busbar(s) remain outside {low:.2f}-{high:.2f} pu "
                f"after switching, worst at {worst}: the network needs equipment "
                "it does not have, not a different switching order"
            )
    return log


def rebalance_dispatch(
    result: BuildResult,
    exchange: dict,
    case_name: str,
    *,
    max_rounds: int = 12,
    tolerance_mw: float = 1.0,
    log: OperationLog | None = None,
) -> OperationLog:
    """Correct the dispatch until the slack machine matches its schedule.

    The imbalance is given to the marginal units in merit order — the most
    expensive thermal plant first when generation has to come down, the
    cheapest available headroom when it has to go up. When no headroom is
    left, the shortfall is shed, because a slack machine delivering more than
    it has is not a result, it is a silent failure.
    """
    log = log or OperationLog()
    net = result.net
    case = exchange["cases"][case_name]
    generators = {g["id"]: g for g in exchange["network"]["generators"]}

    slack_ids = [g.replace("SLACK_", "") for g in result.ext_grid_index]
    scheduled_slack = sum(
        case["generators"][g]["p_mw"] for g in slack_ids if g in case["generators"]
    )
    slack_headroom = sum(
        case["generators"][g]["available_mw"] for g in slack_ids if g in case["generators"]
    )

    # Merit order of the thermal plant that can move, most expensive last.
    movable = [
        (gen_id, index)
        for gen_id, index in result.gen_index.items()
        if gen_id in generators and generators[gen_id]["technology"] == "thermal"
    ]
    movable.sort(
        key=lambda item: (
            0 if generators[item[0]]["fuel"] == "hfo" else 1,
            -generators[item[0]]["capacity_mw"],
        )
    )

    relax = bool(log.q_limits_relaxed)
    for round_index in range(max_rounds):
        if not _solve(net, enforce_q_lims=not relax):
            log.converged = False
            log.iterations = round_index
            return log

        slack_mw = float(net.res_ext_grid.p_mw.sum())
        mismatch = slack_mw - scheduled_slack
        log.final_losses_mw = float(net.res_line.pl_mw.sum() + net.res_trafo.pl_mw.sum())
        log.iterations = round_index + 1

        if abs(mismatch) <= tolerance_mw:
            log.residual_mismatch_mw = round(mismatch, 3)
            return log

        if mismatch > 0:
            # The slack is carrying more than its schedule: raise thermal output,
            # cheapest headroom first.
            remaining = mismatch
            for gen_id, index in movable:
                if remaining <= 0:
                    break
                capacity = generators[gen_id]["capacity_mw"]
                current = float(net.gen.at[index, "p_mw"])
                room = capacity - current
                if room <= 0.01:
                    continue
                take = min(room, remaining)
                net.gen.at[index, "p_mw"] = current + take
                net.gen.at[index, "in_service"] = True
                remaining -= take
                log.dispatch_actions.append(
                    f"{gen_id}: raised to {current + take:.1f} MW to relieve the slack"
                )
            if remaining > tolerance_mw:
                total_load = float(net.load.p_mw.sum())
                if total_load <= 0:
                    break
                factor = max(0.0, 1.0 - remaining / total_load)
                net.load["p_mw"] *= factor
                net.load["q_mvar"] *= factor
                log.dispatch_actions.append(
                    f"no thermal headroom left: shed a further {remaining:.1f} MW, "
                    "because the losses of this operating point exceed what the "
                    "dispatch allowed for"
                )
        else:
            # The slack is being pushed below its schedule: back off the most
            # expensive plant first.
            remaining = -mismatch
            for gen_id, index in reversed(movable):
                if remaining <= 0:
                    break
                minimum = generators[gen_id]["min_load_mw"]
                current = float(net.gen.at[index, "p_mw"])
                room = current - minimum
                if room <= 0.01:
                    continue
                give = min(room, remaining)
                net.gen.at[index, "p_mw"] = current - give
                remaining -= give
                log.dispatch_actions.append(
                    f"{gen_id}: reduced to {current - give:.1f} MW"
                )
            if remaining > tolerance_mw and slack_headroom > scheduled_slack:
                # The slack machine has room to absorb the surplus itself.
                log.dispatch_actions.append(
                    f"{remaining:.1f} MW absorbed by the slack machine within its "
                    f"{slack_headroom:.1f} MW availability"
                )
                break

    log.residual_mismatch_mw = round(
        float(net.res_ext_grid.p_mw.sum()) - scheduled_slack, 3
    )
    return log


def operate(
    result: BuildResult,
    exchange: dict,
    case_name: str,
    *,
    switch_capacitors: bool = True,
    loss_consistent_dispatch: bool = True,
    voltage_band: tuple[float, float] = (0.97, 1.03),
) -> OperationLog:
    """Run the operator actions in the order a control centre would."""
    log = OperationLog()
    net = result.net

    if not _solve(net, enforce_q_lims=True):
        # No solution exists that respects every machine's reactive capability.
        # Rather than report a bare non-convergence, solve with the limits
        # relaxed and quantify what is missing: that is the number a planner
        # can act on, and it turns a failed run into a finding.
        if _solve(net, enforce_q_lims=False):
            log.q_limits_relaxed = True
            log.reactive_shortfall = reactive_shortfall(net)
            if not log.reactive_shortfall.empty:
                worst = log.reactive_shortfall.iloc[0]
                log.dispatch_actions.append(
                    f"no solution respects the reactive limits: {worst['generator']} "
                    f"would have to supply {worst['q_required_mvar']:.0f} Mvar against "
                    f"{worst['q_limit_mvar']:.0f} Mvar of capability at "
                    f"{worst['bus']}. Solved with the limits relaxed; the busbar is "
                    f"short of about {abs(worst['shortfall_mvar']):.0f} Mvar of "
                    "compensation."
                )
        else:
            log.converged = False
            return log

    if loss_consistent_dispatch:
        rebalance_dispatch(result, exchange, case_name, log=log)
    if switch_capacitors:
        switch_shunts(result, voltage_band=voltage_band, log=log)
    if loss_consistent_dispatch:
        # Switching capacitors changes the losses, so the balance is checked once more.
        rebalance_dispatch(result, exchange, case_name, max_rounds=4, log=log)

    if log.q_limits_relaxed:
        _solve(net, enforce_q_lims=False)
        log.reactive_shortfall = reactive_shortfall(net)
    return log

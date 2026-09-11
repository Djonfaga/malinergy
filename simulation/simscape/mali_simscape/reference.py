"""Average-value EMT reference model of a grid-following photovoltaic inverter.

The deliverable of this branch is the Simulink and Simscape Electrical model in
``matlab/``. This module is the same plant and the same control law written
again in Python, for the same reason as in the Modelica branch: a control
design that has only been run in one tool has not been checked, and an unstable
loop can look perfectly damped if the plant is wrong in a compensating way.

The model is the standard synchronous-reference-frame design used by every
utility photovoltaic inverter in service:

* an averaged converter, so switching is not represented and the step size is
  set by the control bandwidth rather than the carrier;
* an L filter in series with the Thevenin impedance of the network, whose value
  comes from the IEC 60909 fault level at the real connection point;
* a phase-locked loop on the point of common coupling;
* proportional-integral current control in the dq frame with decoupling and
  voltage feed-forward.

What it is for: showing where the phase-locked loop and the network impedance
begin to interact. That is a Malian question, not a generic one — Kita sits at
a short-circuit ratio near 5.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.integrate import solve_ivp

OMEGA_NOM = 2 * math.pi * 50.0


@dataclass
class InverterDesign:
    """Plant and controller parameters, in SI referred to the plant terminals."""

    name: str = "plant"
    rating_mva: float = 50.0
    voltage_kv: float = 33.0
    #: Converter-side filter inductance, as a fraction of the base impedance.
    filter_l_pu: float = 0.10
    filter_r_pu: float = 0.005
    #: Network Thevenin impedance at the connection point.
    grid_l_h: float = 0.02
    grid_r_ohm: float = 0.5
    #: Current controller bandwidth in hertz. A tenth of the switching
    #: frequency is the usual upper bound; 300 Hz is typical for a 3 kHz plant.
    current_bandwidth_hz: float = 300.0
    #: Phase-locked loop bandwidth. This is the parameter the study varies.
    pll_bandwidth_hz: float = 40.0
    pll_damping: float = 0.707
    #: Combined sampling, computation and modulation delay. A converter running
    #: at a few kilohertz carries one and a half sample periods of it, and it
    #: is one of the two things that destabilises a weak-grid connection. The
    #: other is that the controller knows its own filter and not the network.
    control_delay_s: float = 3e-4
    #: Operating point.
    p_setpoint_pu: float = 0.9
    q_setpoint_pu: float = 0.0

    @property
    def base_impedance_ohm(self) -> float:
        return self.voltage_kv**2 / self.rating_mva

    @property
    def base_current_a(self) -> float:
        return self.rating_mva * 1e6 / (math.sqrt(3) * self.voltage_kv * 1e3)

    @property
    def filter_l_h(self) -> float:
        return self.filter_l_pu * self.base_impedance_ohm / OMEGA_NOM

    @property
    def filter_r_ohm(self) -> float:
        return self.filter_r_pu * self.base_impedance_ohm

    @property
    def total_l_h(self) -> float:
        return self.filter_l_h + self.grid_l_h

    @property
    def total_r_ohm(self) -> float:
        return self.filter_r_ohm + self.grid_r_ohm

    @property
    def short_circuit_ratio(self) -> float:
        z_grid = math.hypot(self.grid_r_ohm, OMEGA_NOM * self.grid_l_h)
        if z_grid <= 0:
            return float("inf")
        return (self.voltage_kv**2 / z_grid) / self.rating_mva

    # -- controller tuning -------------------------------------------------
    @property
    def current_kp(self) -> float:
        """Internal model control tuning: the loop cancels the plant pole."""
        return 2 * math.pi * self.current_bandwidth_hz * self.filter_l_h

    @property
    def current_ki(self) -> float:
        return 2 * math.pi * self.current_bandwidth_hz * self.filter_r_ohm

    @property
    def pll_kp(self) -> float:
        omega = 2 * math.pi * self.pll_bandwidth_hz
        return 2 * self.pll_damping * omega

    @property
    def pll_ki(self) -> float:
        omega = 2 * math.pi * self.pll_bandwidth_hz
        return omega**2


@dataclass
class EmtResult:
    design: InverterDesign
    time_s: np.ndarray
    id_pu: np.ndarray
    iq_pu: np.ndarray
    p_pu: np.ndarray
    q_pu: np.ndarray
    angle_error_rad: np.ndarray
    frequency_hz: np.ndarray
    metrics: dict = field(default_factory=dict)


def simulate_inverter(
    design: InverterDesign,
    *,
    duration_s: float = 1.5,
    step_s: float = 2e-4,
    p_step_pu: float = 0.0,
    p_step_time_s: float = 0.5,
    grid_voltage_step_pu: float = 0.0,
    grid_step_time_s: float = 1.0,
) -> EmtResult:
    """Integrate the averaged inverter model.

    State vector, in per unit except the angle:
    ``[i_d, i_q, gamma_d, gamma_q, delta, x_pll, vm_d, vm_q]`` where ``gamma``
    are the current controller integrators, ``delta`` is the angle of the
    phase-locked loop relative to the network, ``x_pll`` its integrator state,
    and ``vm`` the measured point-of-coupling voltage after the control delay.
    """
    base_z = design.base_impedance_ohm
    l_total_pu = design.total_l_h * OMEGA_NOM / base_z
    r_total_pu = design.total_r_ohm / base_z
    # The controller decouples with the inductance it knows, which is its own
    # filter. Using the total inductance here cancels the network impedance
    # exactly and makes every connection look strong: the weak-grid problem
    # disappears from the model rather than from the plant.
    l_filter_pu = design.filter_l_h * OMEGA_NOM / base_z
    lg_pu = design.grid_l_h * OMEGA_NOM / base_z
    rg_pu = design.grid_r_ohm / base_z
    kp_i = design.current_kp / base_z
    ki_i = design.current_ki / base_z

    def grid_voltage(t: float) -> float:
        return 1.0 + (grid_voltage_step_pu if t >= grid_step_time_s else 0.0)

    def setpoints(t: float) -> tuple[float, float]:
        p = design.p_setpoint_pu + (p_step_pu if t >= p_step_time_s else 0.0)
        return p, design.q_setpoint_pu

    def rhs(t, y):
        i_d, i_q, gamma_d, gamma_q, delta, x_pll, vm_d, vm_q = y
        vg = grid_voltage(t)

        # Network voltage seen in the loop's own frame.
        vg_d = vg * math.cos(delta)
        vg_q = -vg * math.sin(delta)

        p_ref, q_ref = setpoints(t)
        # With the loop aligned to the point of common coupling, d carries
        # active and q reactive power.
        v_pcc_d = vg_d + rg_pu * i_d - lg_pu * i_q
        v_pcc_q = vg_q + rg_pu * i_q + lg_pu * i_d
        v_pcc = math.hypot(v_pcc_d, v_pcc_q)

        id_ref = p_ref / max(v_pcc, 0.2)
        iq_ref = -q_ref / max(v_pcc, 0.2)
        # Converter current limit: real plant rides through, it does not trip.
        magnitude = math.hypot(id_ref, iq_ref)
        if magnitude > 1.2:
            id_ref *= 1.2 / magnitude
            iq_ref *= 1.2 / magnitude

        err_d = id_ref - i_d
        err_q = iq_ref - i_q
        # Feed-forward and decoupling use the delayed measurement and the
        # filter inductance, which is all a real controller has.
        v_cd = kp_i * err_d + gamma_d + vm_d - l_filter_pu * i_q
        v_cq = kp_i * err_q + gamma_q + vm_q + l_filter_pu * i_d

        d_id = (v_cd - vg_d - r_total_pu * i_d + l_total_pu * i_q) * OMEGA_NOM / l_total_pu
        d_iq = (v_cq - vg_q - r_total_pu * i_q - l_total_pu * i_d) * OMEGA_NOM / l_total_pu

        # Phase-locked loop: drive the q axis of the measured voltage to zero.
        # It sees the delayed measurement, not the instantaneous voltage.
        vm = math.hypot(vm_d, vm_q)
        error = vm_q / max(vm, 0.2)
        d_x = design.pll_ki * error
        omega_pll = OMEGA_NOM + design.pll_kp * error + x_pll
        d_delta = omega_pll - OMEGA_NOM

        tau = max(design.control_delay_s, 1e-6)
        d_vm_d = (v_pcc_d - vm_d) / tau
        d_vm_q = (v_pcc_q - vm_q) / tau

        return [d_id, d_iq, ki_i * err_d, ki_i * err_q, d_delta, d_x, d_vm_d, d_vm_q]

    y0 = [design.p_setpoint_pu, -design.q_setpoint_pu, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    times = np.arange(0.0, duration_s + step_s, step_s)
    times = times[times <= duration_s]
    solution = solve_ivp(
        rhs, (0.0, duration_s), y0, t_eval=times, method="LSODA",
        rtol=1e-7, atol=1e-9, max_step=2e-4,
    )
    if not solution.success:
        raise RuntimeError(f"integration failed: {solution.message}")

    i_d, i_q, _, _, delta, x_pll, _, _ = solution.y
    vg = np.array([grid_voltage(t) for t in solution.t])
    v_pcc_d = vg * np.cos(delta) + rg_pu * i_d - lg_pu * i_q
    v_pcc_q = -vg * np.sin(delta) + rg_pu * i_q + lg_pu * i_d
    p = v_pcc_d * i_d + v_pcc_q * i_q
    q = v_pcc_q * i_d - v_pcc_d * i_q
    frequency = (OMEGA_NOM + x_pll) / (2 * math.pi)

    # Stability is judged on the last quarter of the run, after transients.
    tail = solution.t >= solution.t[-1] * 0.75
    ripple = float(np.ptp(p[tail]))
    diverged = bool(
        not np.all(np.isfinite(p))
        or np.max(np.abs(i_d)) > 5.0
        or np.max(np.abs(delta)) > math.pi
    )
    stable = (not diverged) and ripple < 0.02

    settling = float("nan")
    if p_step_pu and not diverged:
        target = p[-1]
        after = solution.t >= p_step_time_s
        band = np.abs(p[after] - target) <= 0.02 * max(abs(target), 1e-6)
        if band.any():
            index = len(band) - np.argmin(band[::-1])
            index = min(index, len(band) - 1)
            settling = float(solution.t[after][index] - p_step_time_s)

    metrics = {
        "design": design.name,
        "scr": round(design.short_circuit_ratio, 2),
        "pll_bandwidth_hz": design.pll_bandwidth_hz,
        "current_bandwidth_hz": design.current_bandwidth_hz,
        "stable": stable,
        "diverged": diverged,
        "power_ripple_pu": round(ripple, 5) if np.isfinite(ripple) else None,
        "settling_time_ms": round(settling * 1000.0, 1) if np.isfinite(settling) else None,
        "final_p_pu": round(float(p[-1]), 4) if np.isfinite(p[-1]) else None,
        "max_angle_error_deg": round(float(np.max(np.abs(delta))) * 180.0 / math.pi, 2),
        "max_current_pu": round(float(np.max(np.hypot(i_d, i_q))), 3),
    }
    return EmtResult(
        design=design,
        time_s=solution.t,
        id_pu=i_d,
        iq_pu=i_q,
        p_pu=p,
        q_pu=q,
        angle_error_rad=delta,
        frequency_hz=frequency,
        metrics=metrics,
    )


def stability_sweep(
    base: InverterDesign,
    *,
    bandwidths_hz: tuple[float, ...] = (10.0, 20.0, 40.0, 60.0, 80.0, 120.0),
    duration_s: float = 1.2,
):
    """Phase-locked loop bandwidth against stability at a fixed grid strength."""
    import pandas as pd
    from dataclasses import replace

    rows = []
    for bandwidth in bandwidths_hz:
        design = replace(base, name=f"{base.name}@{bandwidth:.0f}Hz", pll_bandwidth_hz=bandwidth)
        try:
            metrics = simulate_inverter(
                design, duration_s=duration_s, p_step_pu=0.1, p_step_time_s=0.4
            ).metrics
        except RuntimeError:
            metrics = {
                "design": design.name, "scr": round(design.short_circuit_ratio, 2),
                "pll_bandwidth_hz": bandwidth, "stable": False, "diverged": True,
                "power_ripple_pu": None, "settling_time_ms": None,
            }
        rows.append(metrics)
    return pd.DataFrame(rows)

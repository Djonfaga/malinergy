"""Reference implementation of the Modelica equations, in Python.

Why this exists. The Modelica library in ``modelica/MaliEnergy`` is the
deliverable; it is compiled and simulated by OpenModelica through
:mod:`mali_openmodelica.driver`. But a model that has only ever been run by one
tool has never been checked — a sign error or a misplaced time constant
produces a curve that looks perfectly reasonable.

So the same equations are written a second time here, integrated with SciPy,
and the two are compared. Where they agree, the physics is not an artefact of
either implementation. Where they disagree, one of them is wrong and the
disagreement says where to look.

The equations below are transcribed from the Modelica source, component by
component, and the mapping is stated in each docstring.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.integrate import solve_ivp

F_NOM = 50.0


# ---------------------------------------------------------------------------
# System frequency: MaliEnergy.Systems.InterconnectedFrequency
# ---------------------------------------------------------------------------


@dataclass
class FrequencyCase:
    """One frequency-response experiment.

    Mirrors the parameters of ``MaliEnergy.Systems.InterconnectedFrequency``.
    """

    name: str = "dry_peak"
    s_base_mw: float = 500.0
    inertia_h_s: float = 4.2
    demand_mw: float = 385.0
    hydro_mw: float = 74.4
    thermal_mw: float = 245.0
    solar_mw: float = 0.0
    import_mw: float = 90.0
    #: Capacity synchronised and available to the governors. When output
    #: equals capacity there is no primary reserve, which is the normal state
    #: of the Malian system at the dry season peak and the reason a large trip
    #: cannot be arrested.
    hydro_capacity_mw: float = 74.4
    thermal_capacity_mw: float = 245.0
    trip_mw: float = 40.0
    trip_time_s: float = 5.0
    load_damping: float = 1.5
    solar_response: bool = False
    solar_headroom: float = 0.10
    hydro_droop: float = 0.04
    thermal_droop: float = 0.04
    hydro_tg: float = 0.2
    hydro_tt: float = 2.0
    hydro_ramp_pu_s: float = 0.05
    thermal_tg: float = 0.2
    thermal_tt: float = 6.0
    thermal_ramp_pu_s: float = 0.01
    inverter_tau_s: float = 0.05
    #: Under-frequency load shedding scheme. Eight stages from 49.0 Hz down to
    #: 47.6 Hz, shedding 40 % of demand in total, which is the depth West
    #: African schemes are set to.
    shed_stages_hz: tuple[float, ...] = (49.0, 48.8, 48.6, 48.4, 48.2, 48.0, 47.8, 47.6)
    shed_fractions: tuple[float, ...] = (0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05)
    underfrequency_shedding: bool = True
    #: Frequency below which the machines trip and the system is taken to have
    #: collapsed. Integrating past this point produces a curve with no physical
    #: meaning.
    collapse_frequency_hz: float = 47.0

    @property
    def primary_reserve_mw(self) -> float:
        """Headroom the governors can actually deliver."""
        return max(0.0, self.hydro_capacity_mw - self.hydro_mw) + max(
            0.0, self.thermal_capacity_mw - self.thermal_mw
        )

    @property
    def stored_energy_mws(self) -> float:
        """Kinetic energy of the running fleet: the quantity that sets RoCoF."""
        return self.inertia_h_s * self.s_base_mw

    @property
    def solar_share(self) -> float:
        generation = self.hydro_mw + self.thermal_mw + self.solar_mw + self.import_mw
        return self.solar_mw / generation if generation else 0.0


@dataclass
class FrequencyResult:
    case: FrequencyCase
    time_s: np.ndarray
    frequency_hz: np.ndarray
    hydro_mw: np.ndarray
    thermal_mw: np.ndarray
    solar_mw: np.ndarray
    demand_mw: np.ndarray
    shed_fraction: np.ndarray
    metrics: dict = field(default_factory=dict)


def _shed_fraction(frequency: float, minimum_seen: float, case: FrequencyCase) -> float:
    """Under-frequency relays latch: once a stage operates it stays operated.

    ``minimum_seen`` is the lowest frequency reached so far, which is how the
    Modelica model's ``pre(stageTripped[i])`` behaves.
    """
    if not case.underfrequency_shedding:
        return 0.0
    total = 0.0
    for stage, fraction in zip(case.shed_stages_hz, case.shed_fractions, strict=True):
        if minimum_seen < stage:
            total += fraction
    return total


def simulate_frequency(
    case: FrequencyCase | None = None, *, duration_s: float = 60.0, step_s: float = 0.01
) -> FrequencyResult:
    """Integrate the swing equation with governor and inverter dynamics.

    State vector: frequency, hydro valve, hydro mechanical power, thermal
    valve, thermal mechanical power, inverter output, minimum frequency seen.
    All powers are per unit of their own machine rating, as in the Modelica
    components.
    """
    case = case or FrequencyCase()

    hydro_init = case.hydro_mw / case.hydro_capacity_mw if case.hydro_capacity_mw > 0 else 0.0
    thermal_init = (
        case.thermal_mw / case.thermal_capacity_mw if case.thermal_capacity_mw > 0 else 0.0
    )
    # ``solar_mw`` is the output at the operating point. A plant holding
    # headroom is therefore a plant whose available power is higher than its
    # setpoint, not one whose setpoint is lower than its output: getting this
    # the wrong way round leaves the case unbalanced before anything trips and
    # the frequency starts moving on its own.
    if case.solar_mw > 0:
        solar_available = 1.0 / (1.0 - case.solar_headroom) if case.solar_response else 1.0
    else:
        solar_available = 0.0
    solar_init = 1.0 if case.solar_mw > 0 else 0.0

    def governor(p_init, droop, f, enabled=True):
        if not enabled:
            return p_init
        return p_init - (f - F_NOM) / F_NOM / droop

    def rhs(t, y):
        """Right hand side. State order is fixed here and unpacked in one
        place only, because a transposed state vector produces a model that
        integrates happily and is quietly wrong."""
        f, hv, hm, tv, tm, pv_out, f_min = y
        f_min_new = min(f_min, f)
        hydro_ref = min(1.0, max(0.0, governor(hydro_init, case.hydro_droop, f)))
        thermal_ref = min(1.0, max(0.0, governor(thermal_init, case.thermal_droop, f)))
        d_hv = float(
            np.clip((hydro_ref - hv) / case.hydro_tg, -case.hydro_ramp_pu_s, case.hydro_ramp_pu_s)
        )
        d_tv = float(
            np.clip(
                (thermal_ref - tv) / case.thermal_tg,
                -case.thermal_ramp_pu_s,
                case.thermal_ramp_pu_s,
            )
        )
        d_hm = (hv - hm) / case.hydro_tt
        d_tm = (tv - tm) / case.thermal_tt

        if case.solar_response:
            setpoint = 1.0 - ((f - F_NOM) / F_NOM / case.thermal_droop) * solar_available
        else:
            setpoint = solar_available
        setpoint = min(solar_available, max(0.0, setpoint))
        d_pv = (setpoint - pv_out) / case.inverter_tau_s

        tripped = case.trip_mw if t >= case.trip_time_s else 0.0
        generation = (
            hm * case.hydro_capacity_mw
            + tm * case.thermal_capacity_mw
            + pv_out * case.solar_mw
            + case.import_mw
            - tripped
        )
        shed = _shed_fraction(f, f_min_new, case)
        demand = case.demand_mw * (1 - shed) * (1 + case.load_damping * (f - F_NOM) / F_NOM)
        df = (generation - demand) * F_NOM / (2 * case.inertia_h_s * case.s_base_mw)
        d_fmin = min(0.0, df) if f <= f_min + 1e-12 else 0.0
        return [df, d_hv, d_hm, d_tv, d_tm, d_pv, d_fmin]

    def collapse(t, y):
        return y[0] - case.collapse_frequency_hz

    collapse.terminal = True
    collapse.direction = -1

    y0 = [F_NOM, hydro_init, hydro_init, thermal_init, thermal_init, solar_init, F_NOM]
    times = np.arange(0.0, duration_s + step_s, step_s)
    times = times[times <= duration_s]
    solution = solve_ivp(
        rhs,
        (0.0, duration_s),
        y0,
        t_eval=times,
        method="LSODA",
        rtol=1e-6,
        atol=1e-8,
        max_step=0.05,
        events=collapse,
    )
    if not solution.success and solution.status != 1:
        raise RuntimeError(f"integration failed: {solution.message}")
    collapsed = solution.status == 1

    f = solution.y[0]
    hydro = solution.y[2] * case.hydro_capacity_mw
    thermal = solution.y[4] * case.thermal_capacity_mw
    solar = solution.y[5] * case.solar_mw
    running_min = np.minimum.accumulate(f)
    shed = np.array(
        [_shed_fraction(fi, mi, case) for fi, mi in zip(f, running_min, strict=True)]
    )
    demand = case.demand_mw * (1 - shed) * (1 + case.load_damping * (f - F_NOM) / F_NOM)

    after_trip = solution.t >= case.trip_time_s
    # RoCoF is measured over the 500 ms window the relays use, not as an
    # instantaneous derivative, which would be dominated by the step itself.
    window = (solution.t >= case.trip_time_s) & (solution.t <= case.trip_time_s + 0.5)
    if window.sum() > 1:
        rocof = float((f[window][-1] - f[window][0]) / (solution.t[window][-1] - solution.t[window][0]))
    else:
        rocof = float("nan")

    nadir = float(f[after_trip].min()) if after_trip.any() else F_NOM
    nadir_time = float(solution.t[after_trip][np.argmin(f[after_trip])]) if after_trip.any() else 0.0
    settled = float(f[-1])

    metrics = {
        "case": case.name,
        "collapsed": collapsed,
        "collapse_time_s": round(float(solution.t_events[0][0]), 2)
        if collapsed and len(solution.t_events[0])
        else None,
        "primary_reserve_mw": round(case.primary_reserve_mw, 2),
        "stored_energy_mws": round(case.stored_energy_mws, 1),
        "solar_share": round(case.solar_share, 3),
        "trip_mw": case.trip_mw,
        "rocof_hz_s": round(rocof, 4),
        "nadir_hz": round(nadir, 4),
        "nadir_time_s": round(nadir_time, 2),
        "settled_hz": round(settled, 4),
        "shed_fraction": round(float(shed[-1]), 4),
        "shed_mw": round(float(shed[-1] * case.demand_mw), 2),
        "governor_response_mw": round(
            float(hydro[-1] + thermal[-1] - (case.hydro_mw + case.thermal_mw)), 2
        ),
    }
    if collapsed:
        metrics["finding"] = (
            f"the frequency reached {case.collapse_frequency_hz:.1f} Hz "
            f"{metrics['collapse_time_s']}s after the trip with only "
            f"{case.primary_reserve_mw:.0f} MW of primary reserve behind it: "
            "load shedding did not arrest the fall and the system separates"
        )
    return FrequencyResult(
        case=case,
        time_s=solution.t,
        frequency_hz=f,
        hydro_mw=hydro,
        thermal_mw=thermal,
        solar_mw=solar,
        demand_mw=demand,
        shed_fraction=shed,
        metrics=metrics,
    )


# ---------------------------------------------------------------------------
# Village mini-grid: MaliEnergy.Systems.VillageMinigrid
# ---------------------------------------------------------------------------


@dataclass
class MinigridDesign:
    """Mirrors the parameters of ``MaliEnergy.Systems.VillageMinigrid``."""

    name: str = "village"
    pv_kw: float = 150.0
    diesel_kw: float = 100.0
    battery_kw: float = 80.0
    battery_kwh: float = 320.0
    peak_demand_kw: float = 120.0
    soc_start_diesel: float = 0.25
    soc_stop_diesel: float = 0.60
    soc_min: float = 0.15
    soc_max: float = 0.95
    eta_charge: float = 0.95
    eta_discharge: float = 0.95
    diesel_min_load: float = 0.30
    fuel_no_load_l_per_kw_h: float = 0.08
    fuel_slope_l_per_kwh: float = 0.25


def simulate_minigrid(
    design: MinigridDesign,
    irradiance_pu: np.ndarray,
    load_pu: np.ndarray,
    *,
    step_hours: float = 1.0,
    temperature_derate: float = 0.88,
) -> dict:
    """Chronological simulation of the mini-grid dispatch rule.

    The rule is the one in the Modelica model and the one used on real Malian
    mini-grids: the array serves the load, the battery takes the difference,
    and the diesel set starts only when the state of charge falls below
    ``soc_start_diesel``, then charges the battery to ``soc_stop_diesel``
    before stopping. The hysteresis is what stops the set cycling.
    """
    steps = min(len(irradiance_pu), len(load_pu))
    soc = 0.6
    diesel_running = False
    fuel_litres = 0.0
    diesel_hours = 0.0
    diesel_starts = 0
    served = unserved = curtailed = pv_energy = diesel_energy = 0.0
    soc_trace = np.zeros(steps)
    diesel_trace = np.zeros(steps)

    for i in range(steps):
        pv_kw = min(design.pv_kw, design.pv_kw * irradiance_pu[i] * temperature_derate)
        load_kw = design.peak_demand_kw * load_pu[i]
        pv_energy += pv_kw * step_hours
        net_kw = load_kw - pv_kw

        was_running = diesel_running
        # The start rule has to watch power as well as energy. A controller
        # that starts only on state of charge leaves the set standing while the
        # battery converter, rated well below the village peak, fails to cover
        # the evening load: the battery has the energy and cannot deliver it
        # fast enough, and the village is shed with a full battery.
        power_short = net_kw > design.battery_kw
        if soc < design.soc_start_diesel or power_short:
            diesel_running = True
        elif soc >= design.soc_stop_diesel and not power_short:
            diesel_running = False
        if diesel_running and not was_running:
            diesel_starts += 1

        battery_kw = 0.0
        diesel_kw = 0.0

        if diesel_running:
            # The set runs at least at its minimum load; the surplus charges
            # the battery rather than being spilled.
            diesel_kw = max(design.diesel_min_load * design.diesel_kw, min(net_kw, design.diesel_kw))
            surplus = diesel_kw - net_kw
            if surplus > 0 and soc < design.soc_max:
                battery_kw = -min(surplus, design.battery_kw)
            elif net_kw > diesel_kw and soc > design.soc_min:
                battery_kw = min(net_kw - diesel_kw, design.battery_kw)
        elif net_kw > 0:
            if soc > design.soc_min:
                battery_kw = min(net_kw, design.battery_kw)
        else:
            if soc < design.soc_max:
                battery_kw = -min(-net_kw, design.battery_kw)

        if battery_kw > 0:
            energy = battery_kw * step_hours / design.eta_discharge
            available = (soc - design.soc_min) * design.battery_kwh
            if energy > available:
                battery_kw = available * design.eta_discharge / step_hours
                energy = available
            soc -= energy / design.battery_kwh
        elif battery_kw < 0:
            energy = -battery_kw * step_hours * design.eta_charge
            room = (design.soc_max - soc) * design.battery_kwh
            if energy > room:
                battery_kw = -room / design.eta_charge / step_hours
                energy = room
            soc += energy / design.battery_kwh

        supply_kw = pv_kw + diesel_kw + max(battery_kw, 0.0)
        delivered = min(load_kw, supply_kw)
        served += delivered * step_hours
        unserved += max(0.0, load_kw - supply_kw) * step_hours
        spill = max(0.0, supply_kw - load_kw - max(-battery_kw, 0.0))
        curtailed += spill * step_hours

        if diesel_running:
            diesel_energy += diesel_kw * step_hours
            diesel_hours += step_hours
            fuel_litres += (
                design.fuel_no_load_l_per_kw_h * design.diesel_kw
                + design.fuel_slope_l_per_kwh * diesel_kw
            ) * step_hours

        soc_trace[i] = soc
        diesel_trace[i] = diesel_kw

    demand_total = served + unserved
    return {
        "design": design.name,
        "steps": steps,
        "demand_kwh": round(demand_total, 1),
        "served_kwh": round(served, 1),
        "unserved_kwh": round(unserved, 1),
        "unserved_pct": round(100.0 * unserved / max(demand_total, 1e-9), 2),
        "pv_generated_kwh": round(pv_energy, 1),
        "spilled_kwh": round(curtailed, 1),
        # Spill is only meaningful as a share of what could have been generated;
        # dividing by zero photovoltaic output produces a number with fifteen
        # digits and no meaning, which is how a diesel-only design ends up
        # reported as curtailing solar.
        "pv_curtailed_pct": round(100.0 * curtailed / pv_energy, 1) if pv_energy > 1e-6 else 0.0,
        "diesel_kwh": round(diesel_energy, 1),
        # Share of generation, not of demand served: a set held at its minimum
        # load generates more than the village takes, and the surplus is spilled
        # or stored rather than delivered. Measured against demand the share
        # exceeds one hundred per cent, which is a reporting error, not a
        # physical one.
        "diesel_share_pct": round(
            100.0 * diesel_energy / max(diesel_energy + pv_energy, 1e-9), 1
        ),
        "diesel_hours": round(diesel_hours, 1),
        "diesel_starts": diesel_starts,
        "fuel_litres": round(fuel_litres, 1),
        "specific_fuel_l_per_kwh": round(fuel_litres / max(diesel_energy, 1e-9), 3),
        "fuel_per_delivered_kwh": round(fuel_litres / max(served, 1e-9), 4),
        "soc_min": round(float(soc_trace.min()), 3),
        "soc_max": round(float(soc_trace.max()), 3),
        "soc_final": round(soc, 3),
        "soc_trace": soc_trace,
        "diesel_trace": diesel_trace,
    }

"""Converter studies at the real Malian connection points."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd

from mali_energy.config import BUILD_DIR
from mali_energy.exchange import load_exchange

from .grid_strength import ConnectionPoint, connection_points, strength_table
from .reference import InverterDesign, simulate_inverter, stability_sweep

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SHORT_CIRCUIT = DATA_DIR / "shortcircuit_dry_peak.csv"


def load_default_exchange() -> dict:
    path = BUILD_DIR / "mali_case.json"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run 'mali-energy build' in simulation/core first."
        )
    return load_exchange(path)


def load_short_circuit() -> pd.DataFrame:
    if SHORT_CIRCUIT.exists():
        return pd.read_csv(SHORT_CIRCUIT)
    return pd.DataFrame()


def design_from_point(point: ConnectionPoint, **overrides) -> InverterDesign:
    """Build an inverter design matched to a real connection point."""
    design = InverterDesign(
        name=point.plant,
        rating_mva=point.plant_mw / 0.95,
        voltage_kv=point.vn_kv,
        grid_l_h=point.grid_inductance_h,
        grid_r_ohm=point.grid_resistance_ohm,
        pll_bandwidth_hz=point.recommended_pll_bandwidth_hz,
    )
    return replace(design, **overrides) if overrides else design


def grid_strength_study(exchange: dict | None = None) -> pd.DataFrame:
    """Short-circuit ratio at every photovoltaic connection point."""
    exchange = exchange or load_default_exchange()
    return strength_table(connection_points(exchange, load_short_circuit()))


def step_response_study(exchange: dict | None = None) -> pd.DataFrame:
    """Response to a ten per cent power step at each plant, as designed."""
    exchange = exchange or load_default_exchange()
    rows = []
    for point in connection_points(exchange, load_short_circuit()):
        design = design_from_point(point)
        result = simulate_inverter(design, duration_s=1.0, p_step_pu=0.1, p_step_time_s=0.4)
        rows.append({"bus": point.bus, "strength": point.strength, **result.metrics})
    frame = pd.DataFrame(rows)
    keep = [
        "design", "bus", "scr", "strength", "pll_bandwidth_hz", "stable",
        "settling_time_ms", "power_ripple_pu", "max_current_pu",
    ]
    return frame[[c for c in keep if c in frame.columns]]


def bandwidth_study(
    exchange: dict | None = None, *, plant: str | None = None
) -> pd.DataFrame:
    """Phase-locked loop bandwidth against stability at the weakest connection.

    This is the design question the branch exists to answer. A bandwidth that
    is perfectly stable at Segou will not necessarily be stable at Kita, and
    the difference is the network, not the inverter.
    """
    exchange = exchange or load_default_exchange()
    points = connection_points(exchange, load_short_circuit())
    if plant:
        points = [p for p in points if p.plant == plant]
    else:
        points = sorted(points, key=lambda p: p.scr)[:1]
    if not points:
        return pd.DataFrame()

    point = points[0]
    base = design_from_point(point)
    frame = stability_sweep(base)
    frame.insert(0, "bus", point.bus)
    return frame


def weak_grid_comparison(exchange: dict | None = None, *, bandwidth_hz: float = 60.0):
    """The same controller at every connection point.

    A single fixed design applied across the fleet, which is what happens when
    a supplier ships one product. Where it fails is where the network is weak.
    """
    exchange = exchange or load_default_exchange()
    rows = []
    for point in connection_points(exchange, load_short_circuit()):
        design = design_from_point(point, pll_bandwidth_hz=bandwidth_hz)
        try:
            metrics = simulate_inverter(
                design, duration_s=1.0, p_step_pu=0.1, p_step_time_s=0.4
            ).metrics
        except RuntimeError:
            metrics = {
                "design": design.name, "scr": round(design.short_circuit_ratio, 2),
                "pll_bandwidth_hz": bandwidth_hz, "stable": False, "diverged": True,
            }
        rows.append({"bus": point.bus, "strength": point.strength, **metrics})
    frame = pd.DataFrame(rows)
    keep = ["design", "bus", "scr", "strength", "pll_bandwidth_hz", "stable",
            "settling_time_ms", "power_ripple_pu", "max_angle_error_deg"]
    return frame[[c for c in keep if c in frame.columns]].sort_values("scr")


def converter_limit_study(exchange: dict | None = None) -> pd.DataFrame:
    """How much converter capacity each busbar can carry.

    The short-circuit ratio falls as plant is added at a fixed busbar, and the
    reference model puts the limits where the textbooks do: comfortable above
    3, a visible power-transfer limit near 1.5, loss of synchronism below about
    1.2. This turns the fault levels into the number a developer needs — the
    megawatts a connection point can take before the converter, not the
    thermal rating, becomes the constraint.
    """
    exchange = exchange or load_default_exchange()
    rows = []
    for point in connection_points(exchange, load_short_circuit()):
        rows.append(
            {
                "bus": point.bus,
                "vn_kv": point.vn_kv,
                "sk_mva": round(point.short_circuit_mva, 1),
                "connected_mw": point.plant_mw,
                "scr_now": round(point.scr, 2),
                "mw_at_scr_3": round(point.short_circuit_mva / 3.0, 1),
                "headroom_to_scr_3_mw": round(
                    point.short_circuit_mva / 3.0 - point.plant_mw, 1
                ),
                "mw_at_scr_1_5": round(point.short_circuit_mva / 1.5, 1),
                "limiting_factor": (
                    "already below a short-circuit ratio of 3"
                    if point.scr < 3.0
                    else "converter control"
                    if point.short_circuit_mva / 3.0 < point.plant_mw * 3
                    else "thermal rating of the network"
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("headroom_to_scr_3_mw").reset_index(drop=True)


def strength_sweep(
    *, voltage_kv: float = 33.0, rating_mva: float = 52.6,
    ratios: tuple[float, ...] = (8.0, 5.0, 3.0, 2.0, 1.5, 1.2, 1.0),
    bandwidth_hz: float = 20.0,
) -> pd.DataFrame:
    """Validation sweep: the same converter against a weakening network.

    This is what establishes that the model reproduces the known behaviour
    before any Malian conclusion is drawn from it.
    """
    import math

    rows = []
    for scr in ratios:
        z = voltage_kv**2 / (scr * rating_mva)
        x_over_r = 6.0
        r = z / math.hypot(1.0, x_over_r)
        inductance = (r * x_over_r) / (2 * math.pi * 50.0)
        design = InverterDesign(
            name=f"scr_{scr}", rating_mva=rating_mva, voltage_kv=voltage_kv,
            grid_l_h=inductance, grid_r_ohm=r, pll_bandwidth_hz=bandwidth_hz,
        )
        try:
            metrics = simulate_inverter(
                design, duration_s=1.0, p_step_pu=0.1, p_step_time_s=0.4
            ).metrics
        except RuntimeError:
            metrics = {"design": design.name, "scr": scr, "stable": False, "diverged": True}
        metrics["target_scr"] = scr
        rows.append(metrics)
    frame = pd.DataFrame(rows)
    keep = ["target_scr", "stable", "diverged", "final_p_pu",
            "max_angle_error_deg", "max_current_pu", "power_ripple_pu"]
    return frame[[c for c in keep if c in frame.columns]]


def voltage_dip_study(exchange: dict | None = None, *, dip_pu: float = -0.4) -> pd.DataFrame:
    """Response to a network voltage dip, the low-voltage ride-through case."""
    exchange = exchange or load_default_exchange()
    rows = []
    for point in connection_points(exchange, load_short_circuit()):
        design = design_from_point(point)
        result = simulate_inverter(
            design, duration_s=1.2, grid_voltage_step_pu=dip_pu, grid_step_time_s=0.5
        )
        metrics = result.metrics
        metrics["dip_pu"] = dip_pu
        # The current limit is what decides whether the plant rides through or
        # trips on over-current; a plant at 1.2 pu is on its limit.
        metrics["on_current_limit"] = metrics["max_current_pu"] >= 1.19
        rows.append({"bus": point.bus, **metrics})
    frame = pd.DataFrame(rows)
    keep = ["design", "bus", "scr", "dip_pu", "stable", "max_current_pu",
            "on_current_limit", "final_p_pu", "max_angle_error_deg"]
    return frame[[c for c in keep if c in frame.columns]]

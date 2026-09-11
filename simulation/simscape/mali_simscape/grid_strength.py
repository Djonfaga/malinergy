"""Grid strength at the connection points of the Malian photovoltaic plants.

This is the bridge between the steady-state branch and this one. The
short-circuit levels computed to IEC 60909 in ``sim/pandapower`` decide whether
a converter can be controlled at all: below a short-circuit ratio of about 3 a
grid-following inverter's phase-locked loop and its current controller start to
interact with the network impedance, and the design that works at Segou will
oscillate at Kita.

Nothing here is assumed. The ratios come from the fault levels of the same
network the load flows use.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

#: Below this ratio a plant is "very weak" and a grid-following converter needs
#: either a different control structure or synchronous support.
SCR_VERY_WEAK = 3.0
#: Between the two a plant is weak: stable, but the phase-locked loop bandwidth
#: has to be reduced and the current controller retuned.
SCR_WEAK = 5.0


@dataclass
class ConnectionPoint:
    plant: str
    bus: str
    vn_kv: float
    plant_mw: float
    short_circuit_mva: float
    x_over_r: float = 10.0

    @property
    def scr(self) -> float:
        """Short-circuit ratio: fault level divided by plant rating."""
        return self.short_circuit_mva / self.plant_mw if self.plant_mw else float("inf")

    @property
    def grid_impedance_ohm(self) -> float:
        return self.vn_kv**2 / self.short_circuit_mva if self.short_circuit_mva else 0.0

    @property
    def grid_inductance_h(self) -> float:
        reactance = self.grid_impedance_ohm * self.x_over_r / math.hypot(1.0, self.x_over_r)
        return reactance / (2 * math.pi * 50.0)

    @property
    def grid_resistance_ohm(self) -> float:
        return self.grid_impedance_ohm / math.hypot(1.0, self.x_over_r)

    @property
    def strength(self) -> str:
        if self.scr < SCR_VERY_WEAK:
            return "very weak"
        if self.scr < SCR_WEAK:
            return "weak"
        if self.scr < 10.0:
            return "moderate"
        return "strong"

    @property
    def recommended_pll_bandwidth_hz(self) -> float:
        """Phase-locked loop bandwidth a plant at this strength can carry.

        The usual rule is that the loop must be slow compared with the network
        it is locking to. A bandwidth of about the short-circuit ratio times
        two hertz keeps the interaction out of the control band, and is capped
        at the 50 Hz a strong grid allows.
        """
        return max(2.0, min(50.0, 2.0 * self.scr))


def connection_points(
    exchange: dict, short_circuit: pd.DataFrame | None = None
) -> list[ConnectionPoint]:
    """Build a connection point for every photovoltaic plant in the catalogue.

    ``short_circuit`` is the table produced by
    ``mali_pandapower.studies.shortcircuit.run_short_circuit``. Where it is not
    supplied, the fault level is estimated from the impedance of the network
    between the plant and the nearest transmission busbar, and the result says
    so through ``x_over_r`` defaults.
    """
    levels: dict[str, float] = {}
    if short_circuit is not None and not short_circuit.empty:
        column = "sk_max_mva" if "sk_max_mva" in short_circuit else None
        if column:
            levels = dict(zip(short_circuit["bus"], short_circuit[column]))

    buses = {b["id"]: b for b in exchange["network"]["buses"]}
    points: list[ConnectionPoint] = []
    for generator in exchange["network"]["generators"]:
        if generator["technology"] != "solar":
            continue
        bus = buses[generator["bus"]]
        level = levels.get(bus["id"])
        if level is None:
            # Fall back on a rule of thumb tied to the voltage level, and mark
            # it by leaving the X/R at the default rather than inventing one.
            level = 300.0 if bus["vn_kv"] <= 33.0 else 1200.0
        points.append(
            ConnectionPoint(
                plant=generator["id"],
                bus=bus["id"],
                vn_kv=bus["vn_kv"],
                plant_mw=generator["capacity_mw"],
                short_circuit_mva=float(level),
                x_over_r=10.0 if bus["vn_kv"] >= 150 else 6.0,
            )
        )
    return points


def strength_table(points: list[ConnectionPoint]) -> pd.DataFrame:
    rows = [
        {
            "plant": p.plant,
            "bus": p.bus,
            "vn_kv": p.vn_kv,
            "plant_mw": p.plant_mw,
            "sk_mva": round(p.short_circuit_mva, 1),
            "scr": round(p.scr, 2),
            "strength": p.strength,
            "grid_r_ohm": round(p.grid_resistance_ohm, 4),
            "grid_l_mh": round(p.grid_inductance_h * 1000.0, 3),
            "pll_bandwidth_hz": round(p.recommended_pll_bandwidth_hz, 1),
        }
        for p in points
    ]
    return pd.DataFrame(rows).sort_values("scr").reset_index(drop=True)

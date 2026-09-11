"""Water network catalogue for Bamako.

Same discipline as the electrical catalogue in ``simulation/core``: every row
carries a source and a confidence level, and the loader refuses a row without
them. The water data is weaker than the electrical data — most of it is
engineering estimate rather than published record — and the point of saying so
in every record is that a reader can see exactly which conclusions rest on
which kind of number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from mali_energy.grid.schema import haversine_km

REFERENCE_DIR = Path(__file__).resolve().parents[2] / "data" / "reference"

WATER_DENSITY_KG_M3 = 1000.0
GRAVITY_M_S2 = 9.81
#: Kinematic viscosity of water at 27 degC, the Niger's temperature for most
#: of the year. Colder-water values would understate the friction losses.
KINEMATIC_VISCOSITY_M2_S = 0.85e-6


class WaterCatalogError(ValueError):
    pass


@dataclass
class WaterNode:
    id: str
    name: str
    type: str                 # source | plant | reservoir | demand | junction
    latitude: float
    longitude: float
    elevation_m: float
    pressure_bar: float = 1.0
    district: str = ""
    in_service: bool = True
    source: str = ""
    confidence: str = ""
    note: str = ""


@dataclass
class WaterPipe:
    id: str
    name: str
    from_node: str
    to_node: str
    diameter_mm: float
    length_km: float
    material: str = "ductile_iron"
    roughness_mm: float = 0.26
    parallel: int = 1
    in_service: bool = True
    peak_in_service: bool = True
    source: str = ""
    confidence: str = ""
    note: str = ""
    length_is_measured: bool = False

    @property
    def area_m2(self) -> float:
        return math.pi * (self.diameter_mm / 2000.0) ** 2

    def velocity_m_s(self, flow_m3_h: float) -> float:
        return flow_m3_h / 3600.0 / (self.area_m2 * self.parallel)


@dataclass
class WaterPump:
    id: str
    name: str
    from_node: str
    to_node: str
    rated_flow_m3_h: float
    rated_head_m: float
    units: int = 1
    efficiency: float = 0.75
    motor_efficiency: float = 0.94
    electrical_bus: str = ""
    in_service: bool = True
    peak_in_service: bool = True
    source: str = ""
    confidence: str = ""
    note: str = ""

    @property
    def total_flow_m3_h(self) -> float:
        return self.rated_flow_m3_h * self.units

    def shaft_power_kw(self, flow_m3_h: float, head_m: float | None = None) -> float:
        """Hydraulic power divided by pump efficiency."""
        head = self.rated_head_m if head_m is None else head_m
        flow_m3_s = flow_m3_h / 3600.0
        hydraulic_w = WATER_DENSITY_KG_M3 * GRAVITY_M_S2 * flow_m3_s * head
        return hydraulic_w / max(self.efficiency, 0.01) / 1000.0

    def electrical_power_kw(self, flow_m3_h: float, head_m: float | None = None) -> float:
        return self.shaft_power_kw(flow_m3_h, head_m) / max(self.motor_efficiency, 0.01)

    @property
    def rated_electrical_power_kw(self) -> float:
        return self.electrical_power_kw(self.total_flow_m3_h)

    def head_at_flow(self, flow_m3_h: float) -> float:
        """Quadratic pump curve through the duty point, shut-off at 1.25 x head.

        Manufacturers' curves are not published for these stations, so a
        conventional parabola is used. It is exact at the duty point and
        approximate away from it, which is stated wherever a result depends on
        off-duty operation.
        """
        if self.total_flow_m3_h <= 0:
            return self.rated_head_m
        ratio = flow_m3_h / self.total_flow_m3_h
        return self.rated_head_m * (1.25 - 0.25 * ratio**2 - 0.0 * ratio)


@dataclass
class WaterControl:
    """A production setpoint or a pressure-reducing valve.

    Both exist in the real system and both change the answer. Without
    production setpoints the plant with the highest pump head takes the whole
    load and backfeeds the others. Without pressure reduction the districts
    below the Point G escarpment sit at 115 m of head, which no distribution
    network is built for.
    """

    id: str
    name: str
    type: str                 # flow | pressure
    from_node: str
    to_node: str
    controlled_node: str = ""
    setpoint: float = 0.0
    unit: str = "m3_per_h"
    in_service: bool = True
    peak_in_service: bool = True
    source: str = ""
    confidence: str = ""
    note: str = ""

    @property
    def mass_flow_kg_s(self) -> float:
        if self.type != "flow":
            return 0.0
        return self.setpoint * WATER_DENSITY_KG_M3 / 3600.0


@dataclass
class WaterDemand:
    node: str
    population_served: int
    litres_per_capita_day: float
    non_revenue_water: float
    peak_factor: float
    demand_class: str = "residential"
    source: str = ""
    confidence: str = ""
    note: str = ""

    @property
    def average_demand_m3_day(self) -> float:
        """Production needed at the plant, including what is lost in the network."""
        consumed = self.population_served * self.litres_per_capita_day / 1000.0
        return consumed / (1.0 - self.non_revenue_water)

    @property
    def average_flow_m3_h(self) -> float:
        return self.average_demand_m3_day / 24.0

    @property
    def peak_flow_m3_h(self) -> float:
        return self.average_flow_m3_h * self.peak_factor

    @property
    def mass_flow_kg_s(self) -> float:
        return self.average_flow_m3_h * WATER_DENSITY_KG_M3 / 3600.0


@dataclass
class WaterCatalog:
    nodes: dict[str, WaterNode] = field(default_factory=dict)
    pipes: dict[str, WaterPipe] = field(default_factory=dict)
    pumps: dict[str, WaterPump] = field(default_factory=dict)
    demands: dict[str, WaterDemand] = field(default_factory=dict)
    controls: dict[str, WaterControl] = field(default_factory=dict)
    meta: dict = field(default_factory=dict)

    @property
    def production_capacity_m3_h(self) -> float:
        return sum(
            c.setpoint for c in self.controls.values() if c.type == "flow" and c.in_service
        )

    @property
    def total_production_m3_day(self) -> float:
        return sum(d.average_demand_m3_day for d in self.demands.values())

    @property
    def population_served(self) -> int:
        return sum(d.population_served for d in self.demands.values())

    @property
    def installed_pump_power_mw(self) -> float:
        return sum(
            p.rated_electrical_power_kw for p in self.pumps.values() if p.in_service
        ) / 1000.0


def _bool(value, default=True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    return str(value).strip().upper() in {"TRUE", "1", "YES", "OUI"}


def _str(value, default="") -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    return str(value).strip()


def _float(value, default=0.0) -> float:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_water_catalog(directory: Path | None = None, *, route_factor: float = 1.30) -> WaterCatalog:
    """Assemble the Bamako water network from the reference tables.

    ``route_factor`` converts straight-line distance between nodes into pipe
    length. Water mains follow the street grid far more closely than a
    transmission line follows its corridor, so the factor is higher than the
    1.10-1.25 used for overhead lines.
    """
    directory = Path(directory or REFERENCE_DIR)
    catalog = WaterCatalog()

    for row in pd.read_csv(directory / "water_nodes.csv").to_dict("records"):
        node = WaterNode(
            id=_str(row["id"]),
            name=_str(row["name"]),
            type=_str(row["type"]),
            latitude=_float(row["latitude"]),
            longitude=_float(row["longitude"]),
            elevation_m=_float(row["elevation_m"]),
            pressure_bar=_float(row.get("pressure_bar"), 1.0),
            district=_str(row.get("district")),
            in_service=_bool(row.get("in_service")),
            source=_str(row.get("source")),
            confidence=_str(row.get("confidence")),
            note=_str(row.get("note")),
        )
        if not (node.source and node.confidence):
            raise WaterCatalogError(f"node {node.id} has no provenance")
        catalog.nodes[node.id] = node

    for row in pd.read_csv(directory / "water_pipes.csv").to_dict("records"):
        pipe_id = _str(row["id"])
        for key in ("from_node", "to_node"):
            if _str(row[key]) not in catalog.nodes:
                raise WaterCatalogError(f"pipe {pipe_id} references unknown node {row[key]!r}")
        a, b = catalog.nodes[_str(row["from_node"])], catalog.nodes[_str(row["to_node"])]
        stated = _float(row.get("length_km"))
        if stated > 0:
            length, measured = stated, True
        else:
            length = haversine_km(a.latitude, a.longitude, b.latitude, b.longitude) * route_factor
            measured = False
            length = max(length, 0.15)
        catalog.pipes[pipe_id] = WaterPipe(
            id=pipe_id,
            name=_str(row["name"]),
            from_node=a.id,
            to_node=b.id,
            diameter_mm=_float(row["diameter_mm"]),
            length_km=round(length, 3),
            material=_str(row.get("material"), "ductile_iron"),
            roughness_mm=_float(row.get("roughness_mm"), 0.26),
            parallel=int(_float(row.get("parallel"), 1)),
            in_service=_bool(row.get("in_service")),
            peak_in_service=_bool(row.get("peak_in_service")),
            source=_str(row.get("source")),
            confidence=_str(row.get("confidence")),
            note=_str(row.get("note")),
            length_is_measured=measured,
        )

    for row in pd.read_csv(directory / "water_pumps.csv").to_dict("records"):
        pump_id = _str(row["id"])
        for key in ("from_node", "to_node"):
            if _str(row[key]) not in catalog.nodes:
                raise WaterCatalogError(f"pump {pump_id} references unknown node {row[key]!r}")
        catalog.pumps[pump_id] = WaterPump(
            id=pump_id,
            name=_str(row["name"]),
            from_node=_str(row["from_node"]),
            to_node=_str(row["to_node"]),
            rated_flow_m3_h=_float(row["rated_flow_m3_h"]),
            rated_head_m=_float(row["rated_head_m"]),
            units=int(_float(row.get("units"), 1)),
            efficiency=_float(row.get("efficiency"), 0.75),
            motor_efficiency=_float(row.get("motor_efficiency"), 0.94),
            electrical_bus=_str(row.get("electrical_bus")),
            in_service=_bool(row.get("in_service")),
            peak_in_service=_bool(row.get("peak_in_service")),
            source=_str(row.get("source")),
            confidence=_str(row.get("confidence")),
            note=_str(row.get("note")),
        )

    for row in pd.read_csv(directory / "water_demand.csv").to_dict("records"):
        node = _str(row["node"])
        if node not in catalog.nodes:
            raise WaterCatalogError(f"demand references unknown node {node!r}")
        catalog.demands[node] = WaterDemand(
            node=node,
            population_served=int(_float(row["population_served"])),
            litres_per_capita_day=_float(row["litres_per_capita_day"]),
            non_revenue_water=_float(row["non_revenue_water"]),
            peak_factor=_float(row.get("peak_factor"), 1.5),
            demand_class=_str(row.get("demand_class"), "residential"),
            source=_str(row.get("source")),
            confidence=_str(row.get("confidence")),
            note=_str(row.get("note")),
        )

    controls_path = directory / "water_controls.csv"
    if controls_path.exists():
        for row in pd.read_csv(controls_path).to_dict("records"):
            control_id = _str(row["id"])
            for key in ("from_node", "to_node"):
                if _str(row[key]) not in catalog.nodes:
                    raise WaterCatalogError(
                        f"control {control_id} references unknown node {row[key]!r}"
                    )
            controlled = _str(row.get("controlled_node")) or _str(row["to_node"])
            if controlled not in catalog.nodes:
                raise WaterCatalogError(
                    f"control {control_id} controls unknown node {controlled!r}"
                )
            catalog.controls[control_id] = WaterControl(
                id=control_id,
                name=_str(row["name"]),
                type=_str(row["type"]),
                from_node=_str(row["from_node"]),
                to_node=_str(row["to_node"]),
                controlled_node=controlled,
                setpoint=_float(row["setpoint"]),
                unit=_str(row.get("unit"), "m3_per_h"),
                in_service=_bool(row.get("in_service")),
                source=_str(row.get("source")),
                confidence=_str(row.get("confidence")),
                note=_str(row.get("note")),
            )

    # Fixed production plus fixed demand is an over-determined system: if the
    # setpoints supply more than the sinks take, the surplus has nowhere to go
    # and the hydraulic solution returns nothing at all. At least one plant has
    # to float and follow the demand.
    fixed_production = sum(
        c.setpoint for c in catalog.controls.values() if c.type == "flow" and c.in_service
    )
    average_demand = sum(d.average_flow_m3_h for d in catalog.demands.values())
    if fixed_production >= average_demand:
        raise WaterCatalogError(
            f"production setpoints total {fixed_production:.0f} m3/h against "
            f"{average_demand:.0f} m3/h of demand: leave at least one plant "
            "without a flow control so that it can follow the load"
        )

    # A pump connected between the same two nodes as a pipe is short-circuited
    # by it: the pump pushes water forward through itself and straight back
    # through the pipe, and the hydraulic solution does not converge. The
    # remedy is a discharge node between the pump and its rising main.
    pipe_pairs = {
        frozenset((pipe.from_node, pipe.to_node)) for pipe in catalog.pipes.values()
    }
    for element in list(catalog.pumps.values()) + list(catalog.controls.values()):
        if frozenset((element.from_node, element.to_node)) in pipe_pairs:
            raise WaterCatalogError(
                f"{element.id} is in parallel with a pipe between "
                f"{element.from_node} and {element.to_node}; the pipe short-circuits "
                "it and the solution recirculates. Insert an intermediate node so "
                "the two are in series"
            )

    catalog.meta = {
        "nodes": len(catalog.nodes),
        "pipes": len(catalog.pipes),
        "pumps": len(catalog.pumps),
        "population_served": catalog.population_served,
        "production_m3_day": round(catalog.total_production_m3_day, 0),
        "installed_pump_power_mw": round(catalog.installed_pump_power_mw, 3),
        "production_capacity_m3_h": catalog.production_capacity_m3_h,
        "controls": len(catalog.controls),
    }
    return catalog

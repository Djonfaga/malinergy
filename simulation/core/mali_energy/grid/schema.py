"""Typed records for the network catalogue.

These dataclasses are the single definition of what a bus, line, transformer,
generator or load *is* in this project. Every tool adapter (pandapower,
PowerFactory, Simscape, Modelica) consumes them or the JSON produced from
them, which is what makes the cross-tool comparison meaningful: the five
models are not five independent transcriptions of a one-line diagram, they are
five renderings of one dataset.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


@dataclass
class Bus:
    id: str
    name: str
    vn_kv: float
    zone: str
    latitude: float
    longitude: float
    type: str = "transmission"       # transmission | distribution | external
    in_service: bool = True
    source: str = ""
    confidence: str = ""
    note: str = ""

    @property
    def is_external(self) -> bool:
        return self.type == "external"


@dataclass
class Line:
    id: str
    name: str
    from_bus: str
    to_bus: str
    vn_kv: float
    circuits: int
    conductor: str
    tower: str
    length_km: float
    route_factor: float = 1.15
    in_service: bool = True
    commissioned: str = ""
    source: str = ""
    confidence: str = ""
    note: str = ""
    length_is_measured: bool = False
    # Filled in by the catalogue from the conductor library.
    r_ohm_per_km: float = 0.0
    x_ohm_per_km: float = 0.0
    c_nf_per_km: float = 0.0
    r0_ohm_per_km: float = 0.0
    x0_ohm_per_km: float = 0.0
    c0_nf_per_km: float = 0.0
    max_i_ka: float = 0.0
    derating_factor: float = 1.0
    ampacity_ambient_c: float = 40.0

    @property
    def thermal_rating_mva(self) -> float:
        return math.sqrt(3) * self.vn_kv * self.max_i_ka * self.circuits


@dataclass
class Transformer:
    id: str
    name: str
    hv_bus: str
    lv_bus: str
    sn_mva: float
    vk_percent: float
    vkr_percent: float
    pfe_kw: float = 0.0
    i0_percent: float = 0.0
    vector_group: str = "YNd11"
    tap_side: str = "hv"
    tap_neutral: int = 0
    tap_min: int = -8
    tap_max: int = 8
    tap_step_percent: float = 1.25
    parallel: int = 1
    in_service: bool = True
    source: str = ""
    confidence: str = ""
    note: str = ""


@dataclass
class Generator:
    id: str
    name: str
    bus: str
    technology: str                  # hydro | thermal | solar | storage
    fuel: str
    capacity_mw: float
    units: int = 1
    unit_mw: float = 0.0
    min_load_mw: float = 0.0
    mali_share: float = 1.0
    sn_mva: float = 0.0
    cos_phi: float = 0.85
    inertia_h_s: float = 0.0
    xdpp_pu: float = 0.0
    xdp_pu: float = 0.0
    xd_pu: float = 0.0
    droop_pct: float = 0.0
    ramp_mw_per_min: float = 0.0
    commissioned: str = ""
    operator: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    in_service: bool = True
    source: str = ""
    confidence: str = ""
    note: str = ""

    @property
    def is_inverter_based(self) -> bool:
        return self.technology in {"solar", "wind", "storage"}

    @property
    def provides_inertia(self) -> bool:
        return self.inertia_h_s > 0 and not self.is_inverter_based

    @property
    def stored_energy_mws(self) -> float:
        """Kinetic energy at rated speed, the quantity that sets RoCoF."""
        return self.inertia_h_s * self.sn_mva


@dataclass
class Load:
    id: str
    name: str
    bus: str
    zone: str
    weight: float
    customer_class: str = "urban_mixed"
    power_factor: float = 0.92
    source: str = ""
    confidence: str = ""
    note: str = ""
    # Filled in by the demand allocation step.
    p_mw: float = 0.0
    q_mvar: float = 0.0


@dataclass
class Shunt:
    """A switchable capacitor or reactor bank.

    Malian distribution substations carry capacitor banks, and leaving them
    out of a network model is not a harmless simplification: without them the
    peak case cannot hold voltage in Bamako once generator reactive limits are
    enforced, and the load flow either collapses or converges only because the
    limits were ignored.
    """

    id: str
    name: str
    bus: str
    q_mvar_per_step: float
    steps: int = 1
    steps_in_service: int = 1
    type: str = "capacitor"
    in_service: bool = True
    source: str = ""
    confidence: str = ""
    note: str = ""

    @property
    def installed_mvar(self) -> float:
        return self.q_mvar_per_step * self.steps

    @property
    def connected_mvar(self) -> float:
        """Reactive power delivered at nominal voltage; positive is capacitive."""
        sign = 1.0 if self.type == "capacitor" else -1.0
        return sign * self.q_mvar_per_step * self.steps_in_service


@dataclass
class Interconnection:
    id: str
    name: str
    bus: str
    partner: str
    capacity_mw: float
    direction: str = "import"
    typical_import_mw: float = 0.0
    in_service: bool = True
    source: str = ""
    confidence: str = ""
    note: str = ""


@dataclass
class GridCatalog:
    """The complete network description, before any tool-specific translation."""

    buses: dict[str, Bus] = field(default_factory=dict)
    lines: dict[str, Line] = field(default_factory=dict)
    transformers: dict[str, Transformer] = field(default_factory=dict)
    generators: dict[str, Generator] = field(default_factory=dict)
    loads: dict[str, Load] = field(default_factory=dict)
    shunts: dict[str, Shunt] = field(default_factory=dict)
    interconnections: dict[str, Interconnection] = field(default_factory=dict)
    hydro_availability: dict[str, dict[int, float]] = field(default_factory=dict)
    meta: dict = field(default_factory=dict)

    # -- convenience views -------------------------------------------------
    def active_buses(self) -> list[Bus]:
        return [b for b in self.buses.values() if b.in_service]

    def active_lines(self) -> list[Line]:
        return [ln for ln in self.lines.values() if ln.in_service]

    def active_generators(self) -> list[Generator]:
        return [g for g in self.generators.values() if g.in_service]

    def generators_by_technology(self, technology: str) -> list[Generator]:
        return [g for g in self.active_generators() if g.technology == technology]

    def installed_capacity_mw(self, *, technology: str | None = None, mali_share: bool = False) -> float:
        gens = self.active_generators()
        if technology:
            gens = [g for g in gens if g.technology == technology]
        factor = (lambda g: g.mali_share) if mali_share else (lambda g: 1.0)
        return sum(g.capacity_mw * factor(g) for g in gens)

    def installed_compensation_mvar(self) -> float:
        return sum(s.installed_mvar for s in self.shunts.values() if s.in_service)

    def system_inertia_mws(self) -> float:
        return sum(g.stored_energy_mws for g in self.active_generators() if g.provides_inertia)

    def to_dict(self) -> dict:
        return {
            "meta": self.meta,
            "buses": [asdict(b) for b in self.buses.values()],
            "lines": [asdict(line) for line in self.lines.values()],
            "transformers": [asdict(t) for t in self.transformers.values()],
            "generators": [asdict(g) for g in self.generators.values()],
            "loads": [asdict(load) for load in self.loads.values()],
            "shunts": [asdict(s) for s in self.shunts.values()],
            "interconnections": [asdict(x) for x in self.interconnections.values()],
            "hydro_availability": {
                k: {str(m): v for m, v in months.items()}
                for k, months in self.hydro_availability.items()
            },
        }

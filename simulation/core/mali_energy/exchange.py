"""The canonical study case: one dataset, five simulators.

This module produces the artefact that makes the comparison in this repository
a benchmark rather than five separate models. ``build_case`` freezes a complete
operating point — network, demand at every bus, dispatch of every unit,
interchange with the neighbours — into a plain dictionary that each tool
adapter translates into its own object model without any further judgement.

Four operating points are defined, chosen because they bracket the year that
Malian system operators actually face:

``dry_peak``
    April evening. Hydro at its annual minimum, no sun, demand at its maximum
    because of cooling load. This is the hour the system is planned for.
``wet_peak``
    September evening. Hydro at its maximum, demand slightly lower.
``solar_noon``
    April midday. Maximum photovoltaic infeed against a high but not peak
    demand: the hour that sets curtailment and voltage-rise questions.
``night_min``
    Off-peak hours of the wet season, which sets minimum-load and
    reactive-absorption problems.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

from .config import BASE_MVA, NOMINAL_FREQUENCY_HZ, StudyConfig
from .demand.allocation import ZONE_STATION, allocate_timeseries, national_to_utility
from .grid.catalog import data_card, load_catalog
from .grid.schema import GridCatalog
from .solar.pv import design_from_generator, plant_output

#: Definition of the four canonical operating points.
OPERATING_POINTS: dict[str, dict] = {
    "dry_peak": {
        "month": 4,
        "hour": 20,
        "description": "April evening peak, hydro at the annual minimum",
    },
    "wet_peak": {
        "month": 9,
        "hour": 20,
        "description": "September evening peak, hydro at the annual maximum",
    },
    "solar_noon": {
        "month": 4,
        "hour": 13,
        "description": "April midday, maximum photovoltaic infeed",
    },
    "night_min": {
        "month": 8,
        "hour": 4,
        "description": "Wet season night, minimum demand",
    },
}


@dataclass
class GeneratorSetpoint:
    id: str
    bus: str
    technology: str
    p_mw: float
    q_mvar: float
    available_mw: float
    capacity_mw: float
    is_slack: bool = False
    is_voltage_controlled: bool = False
    target_vm_pu: float = 1.0


@dataclass
class CaseSnapshot:
    """One fully specified operating point."""

    name: str
    description: str
    timestamp: str
    config: dict
    total_demand_mw: float
    total_demand_mvar: float
    loads: dict[str, dict] = field(default_factory=dict)
    generators: dict[str, GeneratorSetpoint] = field(default_factory=dict)
    interchange_mw: dict[str, float] = field(default_factory=dict)
    balance: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "timestamp": self.timestamp,
            "config": self.config,
            "total_demand_mw": round(self.total_demand_mw, 3),
            "total_demand_mvar": round(self.total_demand_mvar, 3),
            "loads": self.loads,
            "generators": {k: asdict(v) for k, v in self.generators.items()},
            "interchange_mw": self.interchange_mw,
            "balance": self.balance,
            "notes": self.notes,
        }


def _hydro_available(catalog: GridCatalog, generator_id: str, month: int) -> float:
    """Power a Malian dispatcher can actually call on from a hydro plant.

    Two limits apply and both matter. The river sets a seasonal ceiling, and on
    the OMVS schemes — Manantali, Gouina and Felou — Mali is entitled to only
    its share of the output, the balance belonging to Senegal and Mauritania.
    Treating the full 400 MW of OMVS capacity as Malian is the single largest
    error a desk study of this system can make.
    """
    generator = catalog.generators[generator_id]
    availability = catalog.hydro_availability.get(generator_id, {}).get(month, 1.0)
    return generator.capacity_mw * availability * generator.mali_share


def _solar_available(
    catalog: GridCatalog,
    config: StudyConfig,
    month: int,
    hour: int,
    *,
    cache: dict[str, pd.Series],
    allow_network: bool = False,
) -> dict[str, float]:
    """Photovoltaic infeed of every in-service plant at the operating point."""
    output: dict[str, float] = {}
    for generator in catalog.generators_by_technology("solar"):
        if generator.id not in cache:
            bus = catalog.buses[generator.bus]
            design = design_from_generator(
                generator, station=ZONE_STATION.get(bus.zone, "Bamako")
            )
            cache[generator.id] = plant_output(
                design, config.year, allow_network=allow_network
            ).ac_mw
        series = cache[generator.id]
        mask = (series.index.month == month) & (series.index.hour == hour)
        output[generator.id] = float(series[mask].mean()) if mask.any() else 0.0
    return output


def dispatch(
    catalog: GridCatalog,
    config: StudyConfig,
    demand_mw: float,
    month: int,
    hour: int,
    *,
    solar_cache: dict[str, pd.Series] | None = None,
    allow_network: bool = False,
) -> tuple[dict[str, GeneratorSetpoint], dict[str, float], dict[str, float]]:
    """Merit-order dispatch for one operating point.

    The order reflects Malian operating practice rather than a market: run the
    hydro that the river allows, take every kilowatt-hour of solar, then use
    contracted imports, and cover the remainder with thermal plant, starting
    with the heavy-fuel-oil units and finishing with the expensive distillate
    and rental sets.
    """
    solar_cache = solar_cache if solar_cache is not None else {}
    # Only the losses of the modelled network have to be generated on top of
    # the bus demands: the demands themselves already carry the low-voltage
    # losses downstream of them.
    required = demand_mw / (1.0 - config.transmission_loss_fraction)

    setpoints: dict[str, GeneratorSetpoint] = {}
    remaining = required
    dispatched: dict[str, float] = {}

    # 1. Hydro, limited by the season.
    for generator in catalog.generators_by_technology("hydro"):
        available = _hydro_available(catalog, generator.id, month)
        p = min(available, max(remaining, 0.0))
        dispatched[generator.id] = p
        remaining -= p
        setpoints[generator.id] = GeneratorSetpoint(
            id=generator.id,
            bus=generator.bus,
            technology="hydro",
            p_mw=round(p, 3),
            q_mvar=0.0,
            available_mw=round(available, 3),
            capacity_mw=generator.capacity_mw,
            is_slack=generator.bus == config.slack_bus,
            is_voltage_controlled=True,
            target_vm_pu=1.02,
        )

    # 2. Solar, taken in full.
    solar = _solar_available(
        catalog, config, month, hour, cache=solar_cache, allow_network=allow_network
    )
    for generator in catalog.generators_by_technology("solar"):
        p = min(solar.get(generator.id, 0.0), generator.capacity_mw)
        dispatched[generator.id] = p
        remaining -= p
        setpoints[generator.id] = GeneratorSetpoint(
            id=generator.id,
            bus=generator.bus,
            technology="solar",
            p_mw=round(p, 3),
            q_mvar=0.0,
            available_mw=round(p, 3),
            capacity_mw=generator.capacity_mw,
            is_voltage_controlled=False,
        )

    # 3. Contracted imports.
    interchange: dict[str, float] = {}
    for link in catalog.interconnections.values():
        if not link.in_service:
            interchange[link.id] = 0.0
            continue
        typical = link.typical_import_mw
        if typical >= 0:
            p = min(typical, max(remaining, 0.0), link.capacity_mw)
        else:
            p = max(typical, -link.capacity_mw)      # export commitment
        interchange[link.id] = round(p, 3)
        remaining -= p

    # 4. Thermal, cheapest first.
    thermal = sorted(
        catalog.generators_by_technology("thermal"),
        key=lambda g: (0 if g.fuel == "hfo" else 1, -g.capacity_mw),
    )
    for generator in thermal:
        if remaining <= 0:
            p = 0.0
        else:
            p = min(generator.capacity_mw, remaining)
            if 0 < p < generator.min_load_mw:
                p = generator.min_load_mw
        dispatched[generator.id] = p
        remaining -= p
        setpoints[generator.id] = GeneratorSetpoint(
            id=generator.id,
            bus=generator.bus,
            technology="thermal",
            p_mw=round(p, 3),
            q_mvar=0.0,
            available_mw=generator.capacity_mw,
            capacity_mw=generator.capacity_mw,
            is_slack=generator.bus == config.slack_bus,
            is_voltage_controlled=True,
            target_vm_pu=1.0,
        )

    # 5. Storage, if a scenario has enabled it: discharge to close the gap.
    for generator in catalog.generators_by_technology("storage"):
        p = min(generator.capacity_mw, max(remaining, 0.0))
        dispatched[generator.id] = p
        remaining -= p
        setpoints[generator.id] = GeneratorSetpoint(
            id=generator.id,
            bus=generator.bus,
            technology="storage",
            p_mw=round(p, 3),
            q_mvar=0.0,
            available_mw=generator.capacity_mw,
            capacity_mw=generator.capacity_mw,
        )

    balance = {
        "demand_mw": round(demand_mw, 3),
        "transmission_loss_allowance_mw": round(required - demand_mw, 3),
        "generation_required_mw": round(required, 3),
        "hydro_mw": round(sum(v for k, v in dispatched.items() if catalog.generators[k].technology == "hydro"), 3),
        "solar_mw": round(sum(v for k, v in dispatched.items() if catalog.generators[k].technology == "solar"), 3),
        "thermal_mw": round(sum(v for k, v in dispatched.items() if catalog.generators[k].technology == "thermal"), 3),
        "storage_mw": round(sum(v for k, v in dispatched.items() if catalog.generators[k].technology == "storage"), 3),
        "net_import_mw": round(sum(interchange.values()), 3),
        "unserved_mw": round(max(remaining, 0.0), 3),
        "surplus_mw": round(max(-remaining, 0.0), 3),
    }
    return setpoints, interchange, balance


def build_case(
    name: str = "dry_peak",
    *,
    catalog: GridCatalog | None = None,
    config: StudyConfig | None = None,
    demand: pd.DataFrame | None = None,
    allow_network: bool = False,
    solar_cache: dict[str, pd.Series] | None = None,
) -> CaseSnapshot:
    """Freeze one operating point into a :class:`CaseSnapshot`."""
    if name not in OPERATING_POINTS:
        raise KeyError(f"unknown operating point {name!r}; choose from {list(OPERATING_POINTS)}")
    config = config or StudyConfig()
    catalog = catalog or load_catalog()
    point = OPERATING_POINTS[name]
    month, hour = point["month"], point["hour"]

    if demand is None:
        demand, _ = allocate_timeseries(catalog, config)

    mask = (demand.index.month == month) & (demand.index.hour == hour)
    if not mask.any():
        raise ValueError(f"operating point {name} not present in the demand series")
    if name == "night_min":
        window = demand[mask]
        moment = window.sum(axis=1).idxmin()
    else:
        window = demand[mask]
        moment = window.sum(axis=1).idxmax()
    slice_ = demand.loc[moment]

    loads: dict[str, dict] = {}
    total_p = total_q = 0.0
    import numpy as np

    for load_id, p_mw in slice_.items():
        load = catalog.loads[load_id]
        q_mvar = float(p_mw) * float(np.tan(np.arccos(load.power_factor)))
        loads[load_id] = {
            "bus": load.bus,
            "p_mw": round(float(p_mw), 4),
            "q_mvar": round(q_mvar, 4),
            "customer_class": load.customer_class,
            "power_factor": load.power_factor,
        }
        total_p += float(p_mw)
        total_q += q_mvar

    setpoints, interchange, balance = dispatch(
        catalog,
        config,
        total_p,
        month,
        hour,
        solar_cache=solar_cache,
        allow_network=allow_network,
    )

    notes: list[str] = []
    if balance["unserved_mw"] > 0.5:
        notes.append(
            f"{balance['unserved_mw']:.0f} MW of demand cannot be served at this "
            "operating point with the catalogue capacity and contracted imports"
        )
    if balance["surplus_mw"] > 0.5:
        notes.append(
            f"{balance['surplus_mw']:.0f} MW of surplus: the merit order has more "
            "must-run capacity than the demand at this hour"
        )

    return CaseSnapshot(
        name=name,
        description=point["description"],
        timestamp=str(moment),
        config={
            "year": config.year,
            "scenario": config.scenario,
            "utility_demand_share": config.utility_demand_share,
            "network_loss_fraction": config.network_loss_fraction,
            "transmission_loss_fraction": config.transmission_loss_fraction,
            "distribution_loss_fraction": round(config.distribution_loss_fraction, 6),
            "base_mva": BASE_MVA,
            "frequency_hz": NOMINAL_FREQUENCY_HZ,
            "slack_bus": config.slack_bus,
            "voltage_limits_pu": list(config.voltage_limits_pu),
        },
        total_demand_mw=total_p,
        total_demand_mvar=total_q,
        loads=loads,
        generators=setpoints,
        interchange_mw=interchange,
        balance=balance,
        notes=notes,
    )


def build_all_cases(
    *,
    catalog: GridCatalog | None = None,
    config: StudyConfig | None = None,
    allow_network: bool = False,
) -> dict[str, CaseSnapshot]:
    """Build every canonical operating point, sharing the expensive computations."""
    config = config or StudyConfig()
    catalog = catalog or load_catalog()
    demand, _ = allocate_timeseries(catalog, config)
    solar_cache: dict[str, pd.Series] = {}
    return {
        name: build_case(
            name,
            catalog=catalog,
            config=config,
            demand=demand,
            allow_network=allow_network,
            solar_cache=solar_cache,
        )
        for name in OPERATING_POINTS
    }


def export_exchange(
    path: Path,
    *,
    catalog: GridCatalog | None = None,
    config: StudyConfig | None = None,
    allow_network: bool = False,
) -> Path:
    """Write ``mali_case.json``: the file every tool adapter reads."""
    config = config or StudyConfig()
    catalog = catalog or load_catalog()
    cases = build_all_cases(catalog=catalog, config=config, allow_network=allow_network)
    summary = national_to_utility(config)

    payload = {
        "format": "mali-energy-exchange/1.0",
        "generated": datetime.now().isoformat(timespec="seconds"),
        "country": "Mali",
        "base_mva": BASE_MVA,
        "frequency_hz": NOMINAL_FREQUENCY_HZ,
        "calibration": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in summary.items()},
        "network": catalog.to_dict(),
        "cases": {name: case.to_dict() for name, case in cases.items()},
        "data_card": json.loads(data_card(catalog).to_json()),
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_exchange(path: Path) -> dict:
    """Read an exchange file written by :func:`export_exchange`."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    fmt = payload.get("format", "")
    if not fmt.startswith("mali-energy-exchange/"):
        raise ValueError(f"{path} is not a Mali energy exchange file")
    return payload

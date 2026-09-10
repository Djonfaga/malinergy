"""Assembly of the network catalogue from the reference tables.

Loading is deliberately strict. A row with an unknown bus reference, an unknown
conductor or an empty provenance field stops the build instead of quietly
producing a network that looks plausible and is wrong.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..config import REFERENCE_DIR
from ..provenance import Confidence, DataCard
from . import electrical
from .schema import (
    Bus,
    Generator,
    GridCatalog,
    Interconnection,
    Line,
    Load,
    Transformer,
    haversine_km,
)


class CatalogError(ValueError):
    """Raised when the reference tables are inconsistent."""


def _bool(value, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    return str(value).strip().upper() in {"TRUE", "1", "YES", "Y", "OUI"}


def _str(value, default: str = "") -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    return str(value).strip()


def _float(value, default: float = 0.0) -> float:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _read(name: str, directory: Path) -> pd.DataFrame:
    path = directory / name
    if not path.exists():
        raise CatalogError(f"missing reference table: {path}")
    return pd.read_csv(path)


def load_catalog(
    directory: Path | None = None,
    *,
    ambient_c: float = 40.0,
    conductor_temp_c: float = 75.0,
    strict_provenance: bool = True,
) -> GridCatalog:
    """Build the :class:`GridCatalog` from ``data/reference``.

    Parameters
    ----------
    ambient_c:
        Ambient temperature used to derate line ampacities. The default is the
        design value for a Malian hot-season afternoon.
    conductor_temp_c:
        Conductor temperature at which resistances are evaluated.
    """
    directory = Path(directory or REFERENCE_DIR)
    catalog = GridCatalog()

    # -- buses -------------------------------------------------------------
    for row in _read("buses.csv", directory).to_dict("records"):
        bus = Bus(
            id=_str(row["id"]),
            name=_str(row["name"]),
            vn_kv=_float(row["vn_kv"]),
            zone=_str(row.get("zone")),
            latitude=_float(row.get("latitude")),
            longitude=_float(row.get("longitude")),
            type=_str(row.get("type"), "transmission"),
            in_service=_bool(row.get("in_service")),
            source=_str(row.get("source")),
            confidence=_str(row.get("confidence")),
            note=_str(row.get("note")),
        )
        if strict_provenance and not (bus.source and bus.confidence):
            raise CatalogError(f"bus {bus.id} has no provenance")
        catalog.buses[bus.id] = bus

    def require_bus(bus_id: str, owner: str) -> Bus:
        if bus_id not in catalog.buses:
            raise CatalogError(f"{owner} references unknown bus {bus_id!r}")
        return catalog.buses[bus_id]

    # -- lines -------------------------------------------------------------
    for row in _read("lines.csv", directory).to_dict("records"):
        line_id = _str(row["id"])
        a = require_bus(_str(row["from_bus"]), f"line {line_id}")
        b = require_bus(_str(row["to_bus"]), f"line {line_id}")
        if abs(a.vn_kv - b.vn_kv) > 1e-6:
            raise CatalogError(
                f"line {line_id} connects {a.vn_kv} kV to {b.vn_kv} kV; use a transformer"
            )

        route_factor = _float(row.get("route_factor"), 1.15) or 1.15
        stated_length = _float(row.get("length_km"))
        if stated_length > 0:
            length_km, measured = stated_length, True
        else:
            straight = haversine_km(a.latitude, a.longitude, b.latitude, b.longitude)
            length_km, measured = straight * route_factor, False
            if length_km <= 0:
                raise CatalogError(f"line {line_id} has zero length; check bus coordinates")

        conductor = _str(row["conductor"])
        tower = _str(row["tower"])
        if conductor not in electrical.CONDUCTORS:
            raise CatalogError(f"line {line_id}: unknown conductor {conductor!r}")
        if tower not in electrical.TOWERS:
            raise CatalogError(f"line {line_id}: unknown tower family {tower!r}")

        params = electrical.line_parameters(
            conductor, tower, ambient_c=ambient_c, operating_temp_c=conductor_temp_c
        )
        line = Line(
            id=line_id,
            name=_str(row["name"]),
            from_bus=a.id,
            to_bus=b.id,
            vn_kv=_float(row["vn_kv"]),
            circuits=int(_float(row.get("circuits"), 1)),
            conductor=conductor,
            tower=tower,
            length_km=round(length_km, 3),
            route_factor=route_factor,
            in_service=_bool(row.get("in_service")),
            commissioned=_str(row.get("commissioned")),
            source=_str(row.get("source")),
            confidence=_str(row.get("confidence")),
            note=_str(row.get("note")),
            length_is_measured=measured,
            r_ohm_per_km=params.r_ohm_km,
            x_ohm_per_km=params.x_ohm_km,
            c_nf_per_km=params.c_nf_km,
            r0_ohm_per_km=params.r0_ohm_km,
            x0_ohm_per_km=params.x0_ohm_km,
            c0_nf_per_km=params.c0_nf_km,
            max_i_ka=params.rated_current_a / 1000.0,
            derating_factor=params.derating_factor,
            ampacity_ambient_c=ambient_c,
        )
        catalog.lines[line.id] = line

    # -- transformers ------------------------------------------------------
    for row in _read("transformers.csv", directory).to_dict("records"):
        tid = _str(row["id"])
        hv = require_bus(_str(row["hv_bus"]), f"transformer {tid}")
        lv = require_bus(_str(row["lv_bus"]), f"transformer {tid}")
        if hv.vn_kv <= lv.vn_kv:
            raise CatalogError(f"transformer {tid}: hv bus is not the higher voltage")
        catalog.transformers[tid] = Transformer(
            id=tid,
            name=_str(row["name"]),
            hv_bus=hv.id,
            lv_bus=lv.id,
            sn_mva=_float(row["sn_mva"]),
            vk_percent=_float(row["vk_percent"]),
            vkr_percent=_float(row["vkr_percent"]),
            pfe_kw=_float(row.get("pfe_kw")),
            i0_percent=_float(row.get("i0_percent")),
            vector_group=_str(row.get("vector_group"), "YNd11"),
            tap_side=_str(row.get("tap_side"), "hv"),
            tap_neutral=int(_float(row.get("tap_neutral"))),
            tap_min=int(_float(row.get("tap_min"), -8)),
            tap_max=int(_float(row.get("tap_max"), 8)),
            tap_step_percent=_float(row.get("tap_step_percent"), 1.25),
            parallel=int(_float(row.get("parallel"), 1)),
            in_service=_bool(row.get("in_service")),
            source=_str(row.get("source")),
            confidence=_str(row.get("confidence")),
            note=_str(row.get("note")),
        )

    # -- generators --------------------------------------------------------
    for row in _read("plants.csv", directory).to_dict("records"):
        gid = _str(row["id"])
        bus = require_bus(_str(row["bus"]), f"generator {gid}")
        capacity = _float(row["capacity_mw"])
        units = int(_float(row.get("units"), 1)) or 1
        catalog.generators[gid] = Generator(
            id=gid,
            name=_str(row["name"]),
            bus=bus.id,
            technology=_str(row["technology"]),
            fuel=_str(row.get("fuel")),
            capacity_mw=capacity,
            units=units,
            unit_mw=_float(row.get("unit_mw"), capacity / units),
            min_load_mw=_float(row.get("min_load_mw")),
            mali_share=_float(row.get("mali_share"), 1.0),
            sn_mva=_float(row.get("sn_mva"), capacity / 0.85),
            cos_phi=_float(row.get("cos_phi"), 0.85),
            inertia_h_s=_float(row.get("inertia_h_s")),
            xdpp_pu=_float(row.get("xdpp_pu")),
            xdp_pu=_float(row.get("xdp_pu")),
            xd_pu=_float(row.get("xd_pu")),
            droop_pct=_float(row.get("droop_pct")),
            ramp_mw_per_min=_float(row.get("ramp_mw_per_min")),
            commissioned=_str(row.get("commissioned")),
            operator=_str(row.get("operator")),
            latitude=_float(row.get("latitude"), bus.latitude),
            longitude=_float(row.get("longitude"), bus.longitude),
            in_service=_bool(row.get("in_service")),
            source=_str(row.get("source")),
            confidence=_str(row.get("confidence")),
            note=_str(row.get("note")),
        )

    # -- loads -------------------------------------------------------------
    for row in _read("loads.csv", directory).to_dict("records"):
        lid = _str(row["id"])
        bus = require_bus(_str(row["bus"]), f"load {lid}")
        catalog.loads[lid] = Load(
            id=lid,
            name=_str(row["name"]),
            bus=bus.id,
            zone=_str(row.get("zone")),
            weight=_float(row["weight"]),
            customer_class=_str(row.get("customer_class"), "urban_mixed"),
            power_factor=_float(row.get("power_factor"), 0.92),
            source=_str(row.get("source")),
            confidence=_str(row.get("confidence")),
            note=_str(row.get("note")),
        )

    # -- interconnections --------------------------------------------------
    for row in _read("interconnections.csv", directory).to_dict("records"):
        xid = _str(row["id"])
        bus = require_bus(_str(row["bus"]), f"interconnection {xid}")
        catalog.interconnections[xid] = Interconnection(
            id=xid,
            name=_str(row["name"]),
            bus=bus.id,
            partner=_str(row.get("partner")),
            capacity_mw=_float(row["capacity_mw"]),
            direction=_str(row.get("direction"), "import"),
            typical_import_mw=_float(row.get("typical_import_mw")),
            in_service=_bool(row.get("in_service")),
            source=_str(row.get("source")),
            confidence=_str(row.get("confidence")),
            note=_str(row.get("note")),
        )

    # -- hydro availability ------------------------------------------------
    hydro = _read("hydro_availability.csv", directory)
    for plant, group in hydro.groupby("plant"):
        plant = _str(plant)
        if plant not in catalog.generators:
            raise CatalogError(f"hydro availability references unknown plant {plant!r}")
        catalog.hydro_availability[plant] = {
            int(r["month"]): float(r["availability"]) for _, r in group.iterrows()
        }

    catalog.meta = {
        "reference_dir": str(directory),
        "ambient_temperature_c": ambient_c,
        "conductor_temperature_c": conductor_temp_c,
        "buses": len(catalog.buses),
        "lines": len(catalog.lines),
        "transformers": len(catalog.transformers),
        "generators": len(catalog.generators),
        "loads": len(catalog.loads),
    }
    return catalog


def data_card(catalog: GridCatalog) -> DataCard:
    """Summarise provenance and confidence across the whole catalogue."""
    records = 0
    sources: list[str] = []
    mix: dict[str, int] = {}
    warnings: list[str] = []

    groups = (
        catalog.buses.values(),
        catalog.lines.values(),
        catalog.transformers.values(),
        catalog.generators.values(),
        catalog.loads.values(),
        catalog.interconnections.values(),
    )
    for group in groups:
        for item in group:
            records += 1
            if item.source and item.source not in sources:
                sources.append(item.source)
            mix[item.confidence] = mix.get(item.confidence, 0) + 1

    estimated = mix.get(Confidence.ESTIMATED.value, 0)
    if estimated:
        warnings.append(
            f"{estimated} of {records} records are engineering estimates; see "
            "docs/verification_checklist.md before quoting absolute figures"
        )
    return DataCard(
        name="mali-grid-catalog",
        records=records,
        sources=sources,
        confidence_mix=mix,
        warnings=warnings,
    )


def export_json(catalog: GridCatalog, path: Path) -> Path:
    """Write the canonical exchange file consumed by every tool adapter."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = catalog.to_dict()
    payload["data_card"] = json.loads(data_card(catalog).to_json())
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path

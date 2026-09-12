"""Export of the canonical case to the DIgSILENT DGS interchange format.

PowerFactory is licensed software and cannot be run from this repository's
continuous checks. What can be done, and is done here, is to produce the
project in the format PowerFactory imports natively and to verify that export
against the source data — every busbar, every impedance, every setpoint.

The DGS ASCII format is a sequence of tables. Each begins with a header line
naming the PowerFactory class and its attributes with their types:

    $$ElmTerm;ID(a:40);loc_name(a:40);fold_id(p);uknom(r);iUsage(i)

followed by one line per object. Types are ``a`` for text, ``r`` for real,
``i`` for integer and ``p`` for a reference to another object's ID.

Importing the result: File, Import, DGS, select the ``.dgs`` file. The grid
appears as a new project with the network, the types and one study case per
operating point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from mali_energy.exchange import load_exchange

DGS_VERSION = "5.0"

#: PowerFactory bus usage codes.
USAGE_BUSBAR = 0
USAGE_JUNCTION = 1
USAGE_INTERNAL = 2


@dataclass
class DgsTable:
    """One class table in the export."""

    name: str
    columns: list[tuple[str, str]]     # (attribute, type code such as "a:40")
    rows: list[list] = field(default_factory=list)

    def header(self) -> str:
        parts = [f"$${self.name}", "ID(a:40)"]
        parts += [f"{attribute}({code})" for attribute, code in self.columns]
        return ";".join(parts)

    def render(self) -> list[str]:
        lines = [self.header()]
        for row in self.rows:
            lines.append(";".join(_format(value) for value in row))
        return lines


def _format(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".") or "0"
    return str(value)


class DgsExport:
    """Builds the tables and writes the file."""

    def __init__(self, exchange: dict, *, project_name: str = "Mali_Interconnected"):
        self.exchange = exchange
        self.project_name = project_name
        self._next_id = 1
        self.ids: dict[str, int] = {}
        self.tables: dict[str, DgsTable] = {}
        self.warnings: list[str] = []

    # -- identifiers -------------------------------------------------------
    def _id(self, key: str) -> int:
        if key not in self.ids:
            self.ids[key] = self._next_id
            self._next_id += 1
        return self.ids[key]

    def _table(self, name: str, columns: list[tuple[str, str]]) -> DgsTable:
        if name not in self.tables:
            self.tables[name] = DgsTable(name=name, columns=columns)
        return self.tables[name]

    # -- construction ------------------------------------------------------
    def build(self, case_name: str = "dry_peak") -> DgsExport:
        network = self.exchange["network"]
        case = self.exchange["cases"][case_name]
        self.case_name = case_name

        self._general()
        grid_id = self._grid()
        self._line_types(network)
        self._transformer_types(network)
        self._machine_types(network)
        self._buses(network, grid_id)
        self._lines(network, grid_id)
        self._transformers(network, grid_id)
        self._shunts(network, grid_id)
        self._loads(case, grid_id)
        self._generators(network, case, grid_id)
        self._external_grids(network, case, grid_id)
        return self

    def _general(self) -> None:
        table = self._table("General", [("Descr", "a:40"), ("Val", "a:40")])
        table.rows = [
            [self._id("general.version"), "Version", DGS_VERSION],
            [self._id("general.tool"), "ToolName", "mali-powerfactory"],
            [
                self._id("general.date"),
                "Date",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ],
        ]

    def _grid(self) -> int:
        table = self._table("ElmNet", [("loc_name", "a:40"), ("frnom", "r")])
        grid_id = self._id("grid")
        table.rows.append([grid_id, self.project_name, self.exchange["frequency_hz"]])
        return grid_id

    def _buses(self, network: dict, grid_id: int) -> None:
        table = self._table(
            "ElmTerm",
            [
                ("loc_name", "a:40"),
                ("fold_id", "p"),
                ("uknom", "r"),
                ("iUsage", "i"),
                ("outserv", "i"),
                ("GPSlat", "r"),
                ("GPSlon", "r"),
                ("cpZone", "a:40"),
            ],
        )
        for bus in network["buses"]:
            usage = USAGE_BUSBAR if bus["vn_kv"] >= 33.0 else USAGE_JUNCTION
            table.rows.append(
                [
                    self._id(f"bus.{bus['id']}"),
                    bus["id"],
                    grid_id,
                    bus["vn_kv"],
                    usage,
                    0 if bus["in_service"] else 1,
                    bus["latitude"],
                    bus["longitude"],
                    bus["zone"],
                ]
            )

    def _line_types(self, network: dict) -> None:
        table = self._table(
            "TypLne",
            [
                ("loc_name", "a:40"),
                ("uline", "r"),
                ("sline", "r"),
                ("rline", "r"),
                ("xline", "r"),
                ("cline", "r"),
                ("rline0", "r"),
                ("xline0", "r"),
                ("cline0", "r"),
                ("nlnph", "i"),
                ("nneutral", "i"),
                ("cohl_", "i"),
            ],
        )
        seen: set[str] = set()
        for line in network["lines"]:
            # One type per conductor and voltage: PowerFactory keys the type on
            # the per-kilometre values, so two corridors with the same
            # conductor and tower share a type, exactly as in a real project.
            key = f"{line['conductor']}_{line['tower']}_{line['vn_kv']:.0f}"
            if key in seen:
                continue
            seen.add(key)
            table.rows.append(
                [
                    self._id(f"typlne.{key}"),
                    key.replace(" ", "_"),
                    line["vn_kv"],
                    line["max_i_ka"],
                    line["r_ohm_per_km"],
                    line["x_ohm_per_km"],
                    line["c_nf_per_km"],
                    line["r0_ohm_per_km"],
                    line["x0_ohm_per_km"],
                    line["c0_nf_per_km"],
                    3,
                    0,
                    1,      # overhead line
                ]
            )

    def _lines(self, network: dict, grid_id: int) -> None:
        table = self._table(
            "ElmLne",
            [
                ("loc_name", "a:40"),
                ("fold_id", "p"),
                ("bus1", "p"),
                ("bus2", "p"),
                ("typ_id", "p"),
                ("dline", "r"),
                ("nlnum", "i"),
                ("outserv", "i"),
            ],
        )
        for line in network["lines"]:
            key = f"{line['conductor']}_{line['tower']}_{line['vn_kv']:.0f}"
            table.rows.append(
                [
                    self._id(f"line.{line['id']}"),
                    line["id"],
                    grid_id,
                    self._id(f"bus.{line['from_bus']}"),
                    self._id(f"bus.{line['to_bus']}"),
                    self._id(f"typlne.{key}"),
                    line["length_km"],
                    line["circuits"],
                    0 if line["in_service"] else 1,
                ]
            )

    def _transformer_types(self, network: dict) -> None:
        table = self._table(
            "TypTr2",
            [
                ("loc_name", "a:40"),
                ("strn", "r"),
                ("utrn_h", "r"),
                ("utrn_l", "r"),
                ("uktr", "r"),
                ("pcutr", "r"),
                ("uk0tr", "r"),
                ("ur0tr", "r"),
                ("curmg", "r"),
                ("pfe", "r"),
                ("tap_side", "i"),
                ("dutap", "r"),
                ("nntap0", "i"),
                ("ntpmn", "i"),
                ("ntpmx", "i"),
                ("tr2cn_h", "a:4"),
                ("tr2cn_l", "a:4"),
                ("nt2ag", "r"),
            ],
        )
        buses = {b["id"]: b for b in network["buses"]}
        for trafo in network["transformers"]:
            hv = buses[trafo["hv_bus"]]["vn_kv"]
            lv = buses[trafo["lv_bus"]]["vn_kv"]
            key = f"{trafo['sn_mva']:.0f}_{hv:.0f}_{lv:.0f}_{trafo['vector_group']}"
            if f"typtr2.{key}" in self.ids:
                continue
            group = trafo["vector_group"]
            hv_connection = "YN" if group.upper().startswith("YN") else group[0].upper()
            lv_connection = "d" if "d" in group.lower() else "yn" if "yn" in group.lower() else "y"
            clock = 11 if group.endswith("11") else 0
            # Copper losses from the resistive component of the short-circuit
            # voltage, which is how PowerFactory expects the data.
            pcutr_kw = trafo["vkr_percent"] / 100.0 * trafo["sn_mva"] * 1000.0
            table.rows.append(
                [
                    self._id(f"typtr2.{key}"),
                    key,
                    trafo["sn_mva"],
                    hv,
                    lv,
                    trafo["vk_percent"],
                    pcutr_kw,
                    trafo["vk_percent"],
                    trafo["vkr_percent"],
                    trafo["i0_percent"],
                    trafo["pfe_kw"],
                    0 if trafo["tap_side"] == "hv" else 1,
                    trafo["tap_step_percent"],
                    trafo["tap_neutral"],
                    trafo["tap_min"],
                    trafo["tap_max"],
                    hv_connection,
                    lv_connection,
                    clock,
                ]
            )

    def _transformers(self, network: dict, grid_id: int) -> None:
        table = self._table(
            "ElmTr2",
            [
                ("loc_name", "a:40"),
                ("fold_id", "p"),
                ("bushv", "p"),
                ("buslv", "p"),
                ("typ_id", "p"),
                ("nntap", "i"),
                ("ntnum", "i"),
                ("outserv", "i"),
            ],
        )
        buses = {b["id"]: b for b in network["buses"]}
        for trafo in network["transformers"]:
            hv = buses[trafo["hv_bus"]]["vn_kv"]
            lv = buses[trafo["lv_bus"]]["vn_kv"]
            key = f"{trafo['sn_mva']:.0f}_{hv:.0f}_{lv:.0f}_{trafo['vector_group']}"
            table.rows.append(
                [
                    self._id(f"trafo.{trafo['id']}"),
                    trafo["id"],
                    grid_id,
                    self._id(f"bus.{trafo['hv_bus']}"),
                    self._id(f"bus.{trafo['lv_bus']}"),
                    self._id(f"typtr2.{key}"),
                    trafo["tap_neutral"],
                    trafo["parallel"],
                    0 if trafo["in_service"] else 1,
                ]
            )

    def _shunts(self, network: dict, grid_id: int) -> None:
        shunts = network.get("shunts", [])
        if not shunts:
            return
        table = self._table(
            "ElmShnt",
            [
                ("loc_name", "a:40"),
                ("fold_id", "p"),
                ("bus1", "p"),
                ("shtype", "i"),
                ("qcapn", "r"),
                ("ncapx", "i"),
                ("ncapa", "i"),
                ("outserv", "i"),
            ],
        )
        for shunt in shunts:
            table.rows.append(
                [
                    self._id(f"shunt.{shunt['id']}"),
                    shunt["id"],
                    grid_id,
                    self._id(f"bus.{shunt['bus']}"),
                    2 if shunt["type"] == "capacitor" else 1,
                    shunt["q_mvar_per_step"],
                    shunt["steps"],
                    shunt["steps_in_service"],
                    0 if shunt["in_service"] else 1,
                ]
            )

    def _loads(self, case: dict, grid_id: int) -> None:
        table = self._table(
            "ElmLod",
            [
                ("loc_name", "a:40"),
                ("fold_id", "p"),
                ("bus1", "p"),
                ("plini", "r"),
                ("qlini", "r"),
                ("scale0", "r"),
                ("outserv", "i"),
            ],
        )
        for load_id, load in case["loads"].items():
            table.rows.append(
                [
                    self._id(f"load.{load_id}"),
                    load_id,
                    grid_id,
                    self._id(f"bus.{load['bus']}"),
                    load["p_mw"],
                    load["q_mvar"],
                    1.0,
                    0,
                ]
            )

    def _machine_types(self, network: dict) -> None:
        table = self._table(
            "TypSym",
            [
                ("loc_name", "a:40"),
                ("sgn", "r"),
                ("ugn", "r"),
                ("cosn", "r"),
                ("xd", "r"),
                ("xds", "r"),
                ("xdss", "r"),
                ("h", "r"),
                ("rstr", "r"),
                ("iturbo", "i"),
            ],
        )
        buses = {b["id"]: b for b in network["buses"]}
        for generator in network["generators"]:
            if generator["technology"] in {"solar", "storage"}:
                continue
            key = generator["id"]
            table.rows.append(
                [
                    self._id(f"typsym.{key}"),
                    f"TYP_{key}",
                    generator["sn_mva"] / max(generator["units"], 1),
                    buses[generator["bus"]]["vn_kv"],
                    generator["cos_phi"],
                    generator["xd_pu"],
                    generator["xdp_pu"],
                    generator["xdpp_pu"],
                    generator["inertia_h_s"],
                    0.003,
                    0 if generator["technology"] == "hydro" else 1,
                ]
            )

    def _generators(self, network: dict, case: dict, grid_id: int) -> None:
        synchronous = self._table(
            "ElmSym",
            [
                ("loc_name", "a:40"),
                ("fold_id", "p"),
                ("bus1", "p"),
                ("typ_id", "p"),
                ("ngnum", "i"),
                ("pgini", "r"),
                ("qgini", "r"),
                ("usetp", "r"),
                ("iv_mode", "i"),
                ("Pmax_uc", "r"),
                ("Pmin_uc", "r"),
                ("outserv", "i"),
            ],
        )
        static = self._table(
            "ElmGenstat",
            [
                ("loc_name", "a:40"),
                ("fold_id", "p"),
                ("bus1", "p"),
                ("sgn", "r"),
                ("pgini", "r"),
                ("qgini", "r"),
                ("cosn", "r"),
                ("av_mode", "a:20"),
                ("iSCM", "i"),
                ("cSav", "r"),
                ("outserv", "i"),
            ],
        )

        records = {g["id"]: g for g in network["generators"]}
        for gen_id, setpoint in case["generators"].items():
            record = records[gen_id]
            out_of_service = 0 if (record["in_service"] and setpoint["p_mw"] > 0) else 1

            if setpoint["technology"] in {"solar", "storage"}:
                static.rows.append(
                    [
                        self._id(f"genstat.{gen_id}"),
                        gen_id,
                        grid_id,
                        self._id(f"bus.{setpoint['bus']}"),
                        record["sn_mva"],
                        setpoint["p_mw"],
                        0.0,
                        1.0,
                        "constq",
                        1,          # current-limited fault contribution
                        1.2,
                        out_of_service,
                    ]
                )
                continue

            # PowerFactory multiplies pgini by ngnum: the attribute is the
            # output of ONE machine, not of the station. Exporting the station
            # total against a machine count of five gives a load flow with five
            # times the generation, which converges and is nonsense.
            units = max(record["units"], 1)
            synchronous.rows.append(
                [
                    self._id(f"sym.{gen_id}"),
                    gen_id,
                    grid_id,
                    self._id(f"bus.{setpoint['bus']}"),
                    self._id(f"typsym.{gen_id}"),
                    units,
                    setpoint["p_mw"] / units,
                    0.0,
                    setpoint["target_vm_pu"] or 1.0,
                    1 if setpoint["is_voltage_controlled"] else 0,
                    setpoint["available_mw"] / units,
                    record["min_load_mw"] / units,
                    out_of_service,
                ]
            )

    def _external_grids(self, network: dict, case: dict, grid_id: int) -> None:
        table = self._table(
            "ElmXnet",
            [
                ("loc_name", "a:40"),
                ("fold_id", "p"),
                ("bus1", "p"),
                ("bustp", "a:2"),
                ("pgini", "r"),
                ("qgini", "r"),
                ("usetp", "r"),
                ("snss", "r"),
                ("rntxn", "r"),
                ("snssmin", "r"),
                ("outserv", "i"),
            ],
        )
        config = case["config"]
        slack_bus = config["slack_bus"]
        records = {g["id"]: g for g in network["generators"]}

        # The slack machine. PowerFactory needs exactly one reference; the
        # dispatched machine at the slack busbar carries it, and its
        # short-circuit contribution comes from its own subtransient reactance
        # rather than from an assumed infinite bus.
        slack_generator = next(
            (
                gen_id
                for gen_id, setpoint in case["generators"].items()
                if setpoint["bus"] == slack_bus and setpoint["p_mw"] > 0
            ),
            None,
        )
        if slack_generator:
            record = records[slack_generator]
            sk = record["sn_mva"] / max(record["xdpp_pu"], 0.05)
            table.rows.append(
                [
                    self._id(f"xnet.SLACK_{slack_generator}"),
                    f"SLACK_{slack_generator}",
                    grid_id,
                    self._id(f"bus.{slack_bus}"),
                    "SL",
                    0.0,
                    0.0,
                    1.02,
                    sk,
                    0.1,
                    sk * 0.8,
                    0,
                ]
            )
        else:
            self.warnings.append(
                f"no dispatched machine at the slack busbar {slack_bus}: "
                "PowerFactory will have no reference"
            )

        # Neighbouring systems: voltage-controlled nodes delivering a schedule,
        # not swing buses. An infinite bus at Ferkessedougou would let Cote
        # d'Ivoire absorb the Malian deficit.
        for link in network["interconnections"]:
            if not link["in_service"]:
                continue
            flow = case["interchange_mw"].get(link["id"], 0.0)
            table.rows.append(
                [
                    self._id(f"xnet.{link['id']}"),
                    link["id"],
                    grid_id,
                    self._id(f"bus.{link['bus']}"),
                    "PV",
                    flow,
                    0.0,
                    1.0,
                    link["capacity_mw"] * 10.0,
                    0.1,
                    link["capacity_mw"] * 8.0,
                    0,
                ]
            )

    # -- output ------------------------------------------------------------
    def render(self) -> str:
        order = [
            "General", "ElmNet", "TypLne", "TypTr2", "TypSym",
            "ElmTerm", "ElmLne", "ElmTr2", "ElmShnt", "ElmLod",
            "ElmSym", "ElmGenstat", "ElmXnet",
        ]
        lines = [
            "*",
            f"** DGS Version {DGS_VERSION}",
            f"** Mali interconnected network, case {getattr(self, 'case_name', 'unknown')}",
            "** Generated from build/mali_case.json - do not edit by hand",
            "*",
        ]
        for name in order:
            table = self.tables.get(name)
            if table and table.rows:
                lines.extend(table.render())
        return "\n".join(lines) + "\n"

    def write(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render(), encoding="utf-8")
        return path

    def statistics(self) -> dict:
        return {
            name: len(table.rows) for name, table in self.tables.items() if table.rows
        }


def export_case(
    exchange: dict | Path | str, case_name: str, path: Path, *, project_name: str | None = None
) -> DgsExport:
    """Export one operating point as a DGS file."""
    if isinstance(exchange, (str, Path)):
        exchange = load_exchange(Path(exchange))
    export = DgsExport(
        exchange, project_name=project_name or f"Mali_{case_name}"
    ).build(case_name)
    export.write(path)
    return export

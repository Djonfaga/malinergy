"""Verification of the DGS export against the canonical case.

PowerFactory cannot be run from here, so the export is checked instead: every
busbar present, every impedance carried across unchanged, every reference
resolving to an object that exists, exactly one slack. An export that passes
this is not guaranteed to import cleanly, but an export that fails it is
guaranteed not to be the network the rest of the repository studied.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .dgs import DgsExport


@dataclass
class VerificationReport:
    findings: list[tuple[str, str, str]] = field(default_factory=list)

    def add(self, level: str, check: str, message: str) -> None:
        self.findings.append((level, check, message))

    @property
    def errors(self):
        return [f for f in self.findings if f[0] == "error"]

    @property
    def warnings(self):
        return [f for f in self.findings if f[0] == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def render(self) -> str:
        if not self.findings:
            return "No findings."
        return "\n".join(f"[{level.upper():7s}] {check}: {message}"
                         for level, check, message in self.findings)


def parse(text: str) -> dict[str, list[dict]]:
    """Read a DGS file back into tables, as a PowerFactory import would."""
    tables: dict[str, list[dict]] = {}
    columns: list[str] = []
    current: str | None = None

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        if line.startswith("$$"):
            parts = line.split(";")
            current = parts[0][2:]
            columns = [re.sub(r"\(.*\)$", "", p) for p in parts[1:]]
            tables[current] = []
            continue
        if current is None:
            continue
        values = line.split(";")
        # A short row is a malformed row; padding it would hide the problem.
        record = {
            column: values[index] if index < len(values) else None
            for index, column in enumerate(columns)
        }
        record["_fields"] = len(values)
        record["_expected"] = len(columns)
        tables[current].append(record)
    return tables


def verify(export: DgsExport, *, case_name: str | None = None) -> VerificationReport:
    """Check an export against the exchange data it came from."""
    report = VerificationReport()
    case_name = case_name or getattr(export, "case_name", None)
    if case_name is None:
        report.add("error", "case", "the export was never built")
        return report

    network = export.exchange["network"]
    case = export.exchange["cases"][case_name]
    tables = parse(export.render())

    # -- completeness ------------------------------------------------------
    exported_buses = {row["loc_name"] for row in tables.get("ElmTerm", [])}
    expected_buses = {bus["id"] for bus in network["buses"]}
    missing = expected_buses - exported_buses
    if missing:
        report.add("error", "buses", f"{len(missing)} missing: {sorted(missing)[:5]}")
    else:
        report.add("info", "buses", f"{len(exported_buses)} exported")

    for label, source_key, table_name in (
        ("lines", "lines", "ElmLne"),
        ("transformers", "transformers", "ElmTr2"),
        ("shunts", "shunts", "ElmShnt"),
    ):
        expected = {item["id"] for item in network.get(source_key, [])}
        exported = {row["loc_name"] for row in tables.get(table_name, [])}
        if expected - exported:
            report.add(
                "error", label, f"{len(expected - exported)} missing from {table_name}"
            )
        else:
            report.add("info", label, f"{len(exported)} exported")

    exported_loads = {row["loc_name"] for row in tables.get("ElmLod", [])}
    if set(case["loads"]) - exported_loads:
        report.add("error", "loads", "some loads were not exported")
    else:
        report.add("info", "loads", f"{len(exported_loads)} exported")

    # -- row shape ---------------------------------------------------------
    for name, rows in tables.items():
        ragged = [r for r in rows if r["_fields"] != r["_expected"]]
        if ragged:
            report.add(
                "error", "row-width",
                f"{name}: {len(ragged)} row(s) do not match the header width",
            )

    # -- referential integrity --------------------------------------------
    known_ids = {row["ID"] for rows in tables.values() for row in rows}
    reference_columns = {
        "ElmTerm": ["fold_id"],
        "ElmLne": ["fold_id", "bus1", "bus2", "typ_id"],
        "ElmTr2": ["fold_id", "bushv", "buslv", "typ_id"],
        "ElmLod": ["fold_id", "bus1"],
        "ElmSym": ["fold_id", "bus1", "typ_id"],
        "ElmGenstat": ["fold_id", "bus1"],
        "ElmXnet": ["fold_id", "bus1"],
        "ElmShnt": ["fold_id", "bus1"],
    }
    dangling = 0
    for name, columns in reference_columns.items():
        for row in tables.get(name, []):
            for column in columns:
                value = row.get(column)
                if value and value not in known_ids:
                    dangling += 1
    if dangling:
        report.add("error", "references", f"{dangling} reference(s) point at no object")
    else:
        report.add("info", "references", "every reference resolves")

    # -- electrical values carried across unchanged ------------------------
    types = {row["loc_name"]: row for row in tables.get("TypLne", [])}
    mismatches = 0
    for line in network["lines"]:
        key = f"{line['conductor']}_{line['tower']}_{line['vn_kv']:.0f}".replace(" ", "_")
        record = types.get(key)
        if record is None:
            report.add("error", "line-type", f"no type exported for {line['id']}")
            continue
        for attribute, source in (
            ("rline", "r_ohm_per_km"),
            ("xline", "x_ohm_per_km"),
            ("cline", "c_nf_per_km"),
        ):
            if abs(float(record[attribute]) - line[source]) > 1e-4:
                mismatches += 1
    if mismatches:
        report.add("error", "impedances", f"{mismatches} value(s) differ from the source")
    else:
        report.add("info", "impedances", "line impedances match the catalogue")

    lengths = {row["loc_name"]: float(row["dline"]) for row in tables.get("ElmLne", [])}
    for line in network["lines"]:
        exported = lengths.get(line["id"])
        if exported is not None and abs(exported - line["length_km"]) > 1e-3:
            report.add(
                "error", "line-length",
                f"{line['id']}: exported {exported} km against {line['length_km']} km",
            )

    # -- dispatch ----------------------------------------------------------
    # PowerFactory multiplies pgini by ngnum, so what the load flow sees is the
    # product. Checking it is what catches a per-station figure exported into a
    # per-machine attribute, which is the easiest way to produce a network that
    # solves and is wrong by a factor of five.
    dispatched = 0.0
    for row in tables.get("ElmSym", []):
        if row["outserv"] == "0":
            dispatched += float(row["pgini"]) * float(row["ngnum"] or 1)
    for row in tables.get("ElmGenstat", []):
        if row["outserv"] == "0":
            dispatched += float(row["pgini"])
    expected = sum(
        setpoint["p_mw"] for setpoint in case["generators"].values() if setpoint["p_mw"] > 0
    )
    difference = abs(dispatched - expected)
    if difference > max(1.0, 0.01 * expected):
        report.add(
            "error", "dispatch",
            f"PowerFactory would see {dispatched:.1f} MW against {expected:.1f} MW in the "
            "case: check whether a per-station figure has been written into a "
            "per-machine attribute",
        )
    else:
        report.add(
            "info", "dispatch",
            f"exported {dispatched:.1f} MW against {expected:.1f} MW in the case",
        )

    # -- exactly one reference --------------------------------------------
    slacks = [row for row in tables.get("ElmXnet", []) if row.get("bustp") == "SL"]
    if len(slacks) != 1:
        report.add("error", "slack", f"{len(slacks)} slack node(s); PowerFactory needs one")
    else:
        report.add("info", "slack", f"reference at {slacks[0]['loc_name']}")

    for warning in export.warnings:
        report.add("warning", "export", warning)

    return report

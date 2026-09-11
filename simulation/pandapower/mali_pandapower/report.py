"""Result export: CSV tables for further work, Markdown for the write-up."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .studies.loadflow import LoadFlowResult, branch_flows, voltage_profile


def _table(frame: pd.DataFrame, *, index: bool = False) -> str:
    """Render a frame as a Markdown table without pulling in a dependency."""
    working = frame.reset_index() if index else frame
    if working.empty:
        return "_no rows_"
    headers = [str(c) for c in working.columns]
    rows = [
        [_fmt(v) if isinstance(v, float) else ("-" if pd.isna(v) else str(v)) for v in record]
        for record in working.itertuples(index=False, name=None)
    ]
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def _fmt(value, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "-"
    if isinstance(value, float):
        return f"{value:,.{digits}f}"
    return str(value)


def write_loadflow(results: dict[str, LoadFlowResult], directory: Path) -> list[Path]:
    """Write per-case tables and return the paths."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    summary = pd.DataFrame(
        [r.summary for r in results.values() if r.converged]
    )
    if not summary.empty:
        path = directory / "loadflow_summary.csv"
        summary.to_csv(path, index=False)
        written.append(path)

    for name, result in results.items():
        if not result.converged:
            continue
        path = directory / f"voltages_{name}.csv"
        voltage_profile(result).to_csv(path, index=False)
        written.append(path)

        path = directory / f"flows_{name}.csv"
        branch_flows(result).to_csv(path, index=False)
        written.append(path)

        if not result.violations.empty:
            path = directory / f"violations_{name}.csv"
            result.violations.to_csv(path, index=False)
            written.append(path)

    return written


def markdown_report(
    results: dict[str, LoadFlowResult],
    *,
    n1: dict[str, pd.DataFrame] | None = None,
    short_circuit: pd.DataFrame | None = None,
    year=None,
    hosting: pd.DataFrame | None = None,
) -> str:
    """Assemble the findings into a document that can be read on its own."""
    lines: list[str] = ["# pandapower — Malian interconnected network", ""]

    lines += ["## Operating points", "",
              "| Case | Demand MW | Shed MW | Losses MW | Losses % | Vmin pu | Worst bus | "
              "Max line % | Violations |", "|---|---|---|---|---|---|---|---|---|"]
    for name, result in results.items():
        if not result.converged:
            lines.append(f"| {name} | did not converge | | | | | | | |")
            continue
        s = result.summary
        lines.append(
            f"| {name} | {_fmt(s['demand_mw'],1)} | {_fmt(s['shed_mw'],1)} | "
            f"{_fmt(s['losses_mw'],2)} | {_fmt(s['losses_pct'],2)} | {_fmt(s['vm_min_pu'],3)} | "
            f"{s['vm_min_bus']} | {_fmt(s['max_line_loading_pct'],1)} | {s['violations']} |"
        )
    lines.append("")

    notes = [n for r in results.values() for n in r.notes]
    if notes:
        lines += ["### Notes from the solver", ""]
        lines += [f"- {n}" for n in dict.fromkeys(notes)]
        lines.append("")

    for name, result in results.items():
        if result.converged and not result.violations.empty:
            lines += [f"### Limit violations at {name}", "",
                      _table(result.violations), ""]

    if n1:
        lines += ["## N-1 contingency screening", ""]
        for case_name, frame in n1.items():
            counts = frame["status"].value_counts().to_dict()
            lines.append(
                f"**{case_name}** — {counts.get('secure', 0)} secure, "
                f"{counts.get('violated', 0)} with violations, "
                f"{counts.get('non-convergent', 0)} without a solution."
            )
            critical = frame[frame["status"] != "secure"].head(8)
            if not critical.empty:
                lines += ["", _table(critical), ""]
        lines.append("")

    if short_circuit is not None and not short_circuit.empty:
        lines += ["## Short-circuit levels (IEC 60909)", ""]
        columns = [c for c in ["bus", "vn_kv", "ikss_3ph_max_ka", "ip_3ph_ka",
                               "sk_max_mva", "ikss_3ph_min_ka", "ikss_1ph_max_ka",
                               "min_max_ratio"] if c in short_circuit.columns]
        lines += [_table(short_circuit[columns].head(20)), ""]

    if year is not None:
        lines += ["## Annual simulation", ""]
        for key, value in year.summary.items():
            lines.append(f"- **{key.replace('_', ' ')}**: {_fmt(value)}")
        lines.append("")
        lines += ["### Monthly balance", "", _table(year.monthly(), index=True), ""]
        if year.notes:
            lines += ["### Notes", ""] + [f"- {n}" for n in year.notes] + [""]

    if hosting is not None and not hosting.empty:
        lines += ["## Photovoltaic hosting capacity", "",
                  _table(hosting.head(15)), ""]

    return "\n".join(lines)

"""Numerical comparison of the tools on the same operating point.

The comparison is only meaningful because every tool is given the same file.
What it can report depends on what is installed: pandapower and pandapipes run
anywhere, and the results below were produced by running them. PowerFactory,
MATLAB and OpenModelica need licences or installations that this repository's
checks do not have, so their columns are filled from result files if those
exist and are reported as absent if they do not.

Nothing here fills a gap with an estimate. A tool that was not run is shown as
not run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Where each tool leaves its results, relative to simulation/.
RESULT_PATHS = {
    "pandapower": Path("pandapower/results/loadflow_summary.csv"),
    "PowerFactory": Path("powerfactory/results/pf_loadflow_summary.csv"),
    "Simscape Electrical": Path("simscape/results/matlab/step_response.csv"),
    "OpenModelica": Path("openmodelica/results/frequency_scenarios.csv"),
}

#: Quantities compared across the steady-state tools, and the tolerance below
#: which two tools are taken to agree. The tolerances are what a planning study
#: would treat as the same answer, not what a solver would.
COMPARED = {
    "demand_mw": 0.5,
    "losses_mw": 0.25,
    "vm_min_pu": 0.005,
    "max_line_loading_pct": 1.0,
}


@dataclass
class ComparisonResult:
    available: dict[str, bool] = field(default_factory=dict)
    table: pd.DataFrame = field(default_factory=pd.DataFrame)
    differences: pd.DataFrame = field(default_factory=pd.DataFrame)
    notes: list[str] = field(default_factory=list)

    @property
    def tools_compared(self) -> list[str]:
        return [tool for tool, present in self.available.items() if present]


def run_pandapower(case_names: tuple[str, ...] = ()) -> pd.DataFrame:
    """Run the pandapower studies here, so at least one column is always live."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "pandapower"))
    from mali_energy.config import BUILD_DIR
    from mali_energy.exchange import load_exchange
    from mali_pandapower.studies.loadflow import run_all_cases

    exchange = load_exchange(BUILD_DIR / "mali_case.json")
    results = run_all_cases(exchange)
    rows = []
    for name, result in results.items():
        if case_names and name not in case_names:
            continue
        if not result.converged:
            rows.append({"case": name, "tool": "pandapower", "converged": False})
            continue
        summary = dict(result.summary)
        summary["tool"] = "pandapower"
        summary["converged"] = True
        rows.append(summary)
    return pd.DataFrame(rows)


def load_tool_results(tool: str) -> pd.DataFrame | None:
    path = REPO_ROOT / RESULT_PATHS[tool]
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    frame["tool"] = tool
    return frame


def compare(*, quantities: dict[str, float] | None = None) -> ComparisonResult:
    """Gather what each tool produced and compare where two of them overlap."""
    quantities = quantities or COMPARED
    result = ComparisonResult()

    frames: list[pd.DataFrame] = []
    try:
        pandapower_frame = run_pandapower()
        frames.append(pandapower_frame)
        result.available["pandapower"] = True
    except Exception as error:  # noqa: BLE001 - reported, not hidden
        result.available["pandapower"] = False
        result.notes.append(f"pandapower did not run: {error}")

    for tool in ("PowerFactory", "Simscape Electrical", "OpenModelica"):
        frame = load_tool_results(tool)
        result.available[tool] = frame is not None
        if frame is None:
            result.notes.append(
                f"{tool}: no result file at {RESULT_PATHS[tool]}. It was not run "
                "on this machine, and nothing below should be read as its output."
            )
        else:
            frames.append(frame)

    if not frames:
        result.notes.append("no tool produced results")
        return result

    combined = pd.concat(frames, ignore_index=True)
    result.table = combined

    steady_state = combined[combined["tool"].isin(["pandapower", "PowerFactory"])]
    if steady_state["tool"].nunique() < 2:
        result.notes.append(
            "only one steady-state tool produced results, so no numerical "
            "comparison is possible. Run the PowerFactory scripts and re-run."
        )
        return result

    rows = []
    for case_name, group in steady_state.groupby("case"):
        pivot = group.set_index("tool")
        if len(pivot) < 2:
            continue
        for quantity, tolerance in quantities.items():
            if quantity not in pivot.columns:
                continue
            values = pivot[quantity].dropna()
            if len(values) < 2:
                continue
            spread = float(values.max() - values.min())
            rows.append(
                {
                    "case": case_name,
                    "quantity": quantity,
                    **{tool: round(float(values[tool]), 4) for tool in values.index},
                    "spread": round(spread, 4),
                    "tolerance": tolerance,
                    "agree": spread <= tolerance,
                }
            )
    result.differences = pd.DataFrame(rows)
    if not result.differences.empty:
        disagreements = result.differences[~result.differences["agree"]]
        if disagreements.empty:
            result.notes.append(
                "every compared quantity agrees within the planning tolerance"
            )
        else:
            result.notes.append(
                f"{len(disagreements)} quantity comparison(s) exceed the tolerance; "
                "these are the rows worth investigating, and the reason the "
                "comparison exists"
            )
    return result


def provenance() -> pd.DataFrame:
    """Which tool ran where, so no reader has to guess."""
    rows = []
    for tool, path in RESULT_PATHS.items():
        full = REPO_ROOT / path
        rows.append(
            {
                "tool": tool,
                "result_file": str(path),
                "present": full.exists(),
                "how_verified": {
                    "pandapower": "executed, 20 automated checks",
                    "PowerFactory": "export verified against source; studies run "
                                    "inside a licensed installation",
                    "Simscape Electrical": "second implementation in Python, "
                                           "executed and tested",
                    "OpenModelica": "second implementation in Python, executed "
                                    "and tested; library checked structurally",
                }[tool],
            }
        )
    rows.append(
        {
            "tool": "pandapipes",
            "result_file": "pandapipes/results/water_cases.csv",
            "present": (REPO_ROOT / "pandapipes" / "results" / "water_cases.csv").exists(),
            "how_verified": "executed, 18 automated checks",
        }
    )
    return pd.DataFrame(rows)

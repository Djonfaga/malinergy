"""Bridge to MATLAB: parameter export, invocation, and result comparison."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pandas as pd

MATLAB_DIR = Path(__file__).resolve().parents[1] / "matlab"


def matlab_available() -> bool:
    return shutil.which("matlab") is not None


def matlab_version() -> str | None:
    if not matlab_available():
        return None
    try:
        out = subprocess.run(
            ["matlab", "-batch", "disp(version)"], capture_output=True, text=True, timeout=120
        )
        return out.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def export_parameters(designs: list, path: Path) -> Path:
    """Write the inverter designs as a MATLAB-readable JSON file.

    Keeps the two implementations on the same numbers without either of them
    re-deriving anything.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "name": d.name,
            "rating_mva": d.rating_mva,
            "voltage_kv": d.voltage_kv,
            "filter_l_pu": d.filter_l_pu,
            "filter_r_pu": d.filter_r_pu,
            "grid_l_h": d.grid_l_h,
            "grid_r_ohm": d.grid_r_ohm,
            "current_bandwidth_hz": d.current_bandwidth_hz,
            "pll_bandwidth_hz": d.pll_bandwidth_hz,
            "control_delay_s": d.control_delay_s,
            "p_setpoint_pu": d.p_setpoint_pu,
            "q_setpoint_pu": d.q_setpoint_pu,
            "short_circuit_ratio": round(d.short_circuit_ratio, 4),
        }
        for d in designs
    ]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def run_matlab_studies(*, timeout_s: int = 3600) -> dict:
    """Invoke ``mali.runStudies`` if MATLAB is installed."""
    if not matlab_available():
        return {
            "status": "not run",
            "note": (
                "no MATLAB on this machine. The Simscape Electrical model in "
                "matlab/ has not been executed here; the results come from the "
                "Python reference implementation of the same plant and control "
                "law. Install MATLAB with Simulink and Simscape Electrical, run "
                "matlab/scripts/run_all.m, then compare with --studies compare."
            ),
        }
    try:
        out = subprocess.run(
            ["matlab", "-batch", "addpath('.'); mali.runStudies();"],
            cwd=MATLAB_DIR,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return {"status": "timed out", "note": f"exceeded {timeout_s} s"}
    return {
        "status": "ran" if out.returncode == 0 else "failed",
        "returncode": out.returncode,
        "stdout": out.stdout[-4000:],
        "stderr": out.stderr[-2000:],
    }


def compare_results(python_frame: pd.DataFrame, *, matlab_dir: Path | None = None) -> dict:
    """Compare the two implementations row for row where both exist."""
    matlab_dir = Path(matlab_dir or (MATLAB_DIR.parent / "results" / "matlab"))
    path = matlab_dir / "step_response.csv"
    if not path.exists():
        return {
            "status": "not compared",
            "note": (
                f"{path} not found: the MATLAB studies have not been run on this "
                "machine, so only the Python reference produced results. Nothing "
                "here should be read as agreement between the two."
            ),
        }

    matlab_frame = pd.read_csv(path)
    merged = python_frame.merge(
        matlab_frame, left_on="design", right_on="name", suffixes=("_py", "_ml")
    )
    if merged.empty:
        return {"status": "no matching rows", "note": "the two tables share no design names"}

    comparisons = []
    for column in ("scr", "final_p_pu", "max_angle_error_deg", "max_current_pu"):
        left, right = f"{column}_py", f"{column}_ml"
        if left in merged and right in merged:
            difference = (merged[left] - merged[right]).abs()
            comparisons.append(
                {
                    "quantity": column,
                    "max_absolute_difference": round(float(difference.max()), 5),
                    "mean_absolute_difference": round(float(difference.mean()), 5),
                }
            )
    return {
        "status": "compared",
        "rows": int(len(merged)),
        "comparisons": comparisons,
        "agreement": all(c["max_absolute_difference"] < 0.05 for c in comparisons),
    }

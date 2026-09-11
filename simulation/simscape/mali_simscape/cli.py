"""Command line entry point: ``mali-simscape``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .matlab import compare_results, matlab_version, run_matlab_studies
from .studies import (
    converter_limit_study,
    grid_strength_study,
    load_default_exchange,
    step_response_study,
    strength_sweep,
    voltage_dip_study,
    weak_grid_comparison,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mali-simscape",
        description="Converter studies at the Malian photovoltaic connection points",
    )
    parser.add_argument("--output", default="results")
    parser.add_argument(
        "--studies",
        default="strength,sweep,step,limits,dip",
        help="comma separated: strength, sweep, step, limits, dip, fleet, matlab, compare, all",
    )
    args = parser.parse_args(argv)

    requested = {s.strip() for s in args.studies.split(",")}
    if "all" in requested:
        requested = {"strength", "sweep", "step", "limits", "dip", "fleet", "compare"}
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    version = matlab_version()
    print(f"MATLAB: {version or 'not installed on this machine'}")
    if version is None:
        print("  results below come from the Python reference implementation")

    exchange = load_default_exchange()
    lines = ["# Simscape Electrical — converters on the Malian network", ""]
    step_frame = None

    if "strength" in requested:
        print("\nGrid strength at each connection point")
        frame = grid_strength_study(exchange)
        print(frame.to_string(index=False))
        frame.to_csv(out / "grid_strength.csv", index=False)
        lines += ["## Grid strength", "", _table(frame), ""]

    if "sweep" in requested:
        print("\nValidation: the same converter against a weakening network")
        frame = strength_sweep()
        print(frame.to_string(index=False))
        frame.to_csv(out / "strength_sweep.csv", index=False)
        lines += ["## Validation sweep", "", _table(frame), ""]

    if "step" in requested:
        print("\nStep response at each connection point")
        step_frame = step_response_study(exchange)
        print(step_frame.to_string(index=False))
        step_frame.to_csv(out / "step_response.csv", index=False)
        lines += ["## Step response", "", _table(step_frame), ""]

    if "limits" in requested:
        print("\nConverter capacity limits")
        frame = converter_limit_study(exchange)
        print(frame.to_string(index=False))
        frame.to_csv(out / "converter_limits.csv", index=False)
        lines += ["## Converter capacity limits", "", _table(frame), ""]

    if "dip" in requested:
        print("\nLow-voltage ride-through, 40 per cent dip")
        frame = voltage_dip_study(exchange)
        print(frame.to_string(index=False))
        frame.to_csv(out / "voltage_dip.csv", index=False)
        lines += ["## Voltage dip", "", _table(frame), ""]

    if "fleet" in requested:
        print("\nOne fixed controller across the fleet")
        frame = weak_grid_comparison(exchange)
        print(frame.to_string(index=False))
        frame.to_csv(out / "fleet_comparison.csv", index=False)
        lines += ["## One controller across the fleet", "", _table(frame), ""]

    if "matlab" in requested:
        print("\nRunning the MATLAB studies")
        outcome = run_matlab_studies()
        print(f"  {outcome['status']}: {outcome.get('note', '')}")
        (out / "matlab_run.json").write_text(json.dumps(outcome, indent=2))

    if "compare" in requested:
        print("\nComparing the two implementations")
        if step_frame is None:
            step_frame = step_response_study(exchange)
        outcome = compare_results(step_frame)
        for key, value in outcome.items():
            print(f"  {key}: {value}")
        (out / "comparison.json").write_text(json.dumps(outcome, indent=2, ensure_ascii=False))
        lines += ["## Cross-check with MATLAB", "", f"`{outcome['status']}`",
                  "", outcome.get("note", ""), ""]

    report = out / "report.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nreport -> {report}")
    return 0


def _table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_no rows_"
    headers = [str(c) for c in frame.columns]
    rows = [
        [f"{v:,.4g}" if isinstance(v, float) else ("-" if pd.isna(v) else str(v)) for v in record]
        for record in frame.itertuples(index=False, name=None)
    ]
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


if __name__ == "__main__":
    raise SystemExit(main())

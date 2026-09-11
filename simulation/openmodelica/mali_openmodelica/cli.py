"""Command line entry point: ``mali-openmodelica``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .driver import openmodelica_available, openmodelica_version
from .generate import (
    frequency_case,
    high_solar_case,
    load_default_exchange,
    village_profiles,
    write_modelica_parameters,
    write_village_profile_table,
)
from .reference import simulate_frequency
from .studies import cross_check, frequency_scenarios, inertia_report, minigrid_study


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mali-openmodelica",
        description="Dynamic studies of the Malian power system",
    )
    parser.add_argument("--output", default="results")
    parser.add_argument(
        "--studies",
        default="inertia,frequency,minigrid,crosscheck,generate",
        help="comma separated: inertia, frequency, minigrid, crosscheck, generate, all",
    )
    parser.add_argument("--year", type=int, default=2024)
    args = parser.parse_args(argv)

    requested = {s.strip() for s in args.studies.split(",")}
    if "all" in requested:
        requested = {"inertia", "frequency", "minigrid", "crosscheck", "generate"}
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    version = openmodelica_version()
    print(f"OpenModelica: {version or 'not installed on this machine'}")
    if not openmodelica_available():
        print("  the SciPy reference implementation of the same equations will be used")

    exchange = load_default_exchange()
    lines = ["# OpenModelica — dynamics of the Malian power system", ""]

    if "inertia" in requested:
        print("\nSystem inertia by operating point")
        frame = inertia_report(exchange)
        print(frame.to_string(index=False))
        frame.to_csv(out / "inertia.csv", index=False)
        lines += ["## System inertia", "", _table(frame), ""]

    if "frequency" in requested:
        print("\nFrequency response scenarios")
        frame = frequency_scenarios(exchange)
        print(frame.to_string(index=False))
        frame.to_csv(out / "frequency_scenarios.csv", index=False)
        lines += ["## Frequency response", "", _table(frame), ""]

        traces = {}
        for name, case in (
            ("dry_peak_unit_trip", frequency_case(exchange, "dry_peak", trip_mw=40.0)),
            ("dry_peak_interconnection", frequency_case(exchange, "dry_peak")),
            ("high_solar", high_solar_case(exchange, solar_mw=250.0)),
            ("high_solar_ffr", high_solar_case(exchange, solar_mw=250.0, solar_response=True)),
        ):
            result = simulate_frequency(case)
            traces[name] = pd.Series(result.frequency_hz, index=result.time_s)
        pd.DataFrame(traces).to_csv(out / "frequency_traces.csv")
        print(f"    -> {out / 'frequency_traces.csv'}")

    if "minigrid" in requested:
        print(f"\nVillage mini-grid, {args.year}, one year of hourly irradiance")
        frame = minigrid_study(year=args.year)
        print(frame.to_string(index=False))
        frame.to_csv(out / "minigrid.csv", index=False)
        lines += ["## Village mini-grid", "", _table(frame), ""]

    if "crosscheck" in requested:
        print("\nCross-check between the two implementations")
        outcome = cross_check(exchange)
        for key, value in outcome.items():
            print(f"  {key}: {value}")
        (out / "cross_check.json").write_text(json.dumps(outcome, indent=2, ensure_ascii=False))
        lines += ["## Cross-check", "", _table(pd.DataFrame([outcome])), ""]

    if "generate" in requested:
        print("\nGenerating Modelica inputs")
        scripts = Path("modelica")
        for name in exchange["cases"]:
            case = frequency_case(exchange, name)
            path = write_modelica_parameters(case, scripts / f"run_{name}.mos")
            print(f"  {path}")
        profiles = village_profiles(year=args.year)
        table = write_village_profile_table(profiles, scripts / "village_profiles.txt")
        print(f"  {table}")

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

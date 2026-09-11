"""Command line entry point: ``mali-pandapower``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mali_energy.config import BUILD_DIR, StudyConfig
from mali_energy.exchange import load_exchange
from mali_energy.grid import load_catalog

from .report import markdown_report, write_loadflow
from .studies.contingency import run_n1
from .studies.hosting import hosting_capacity
from .studies.loadflow import run_all_cases
from .studies.shortcircuit import run_short_circuit
from .studies.timeseries import run_year

DEFAULT_EXCHANGE = BUILD_DIR / "mali_case.json"


def _load(path: str | None) -> dict:
    exchange_path = Path(path or DEFAULT_EXCHANGE)
    if not exchange_path.exists():
        raise SystemExit(
            f"{exchange_path} not found. Run 'mali-energy build' in simulation/core first."
        )
    return load_exchange(exchange_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mali-pandapower",
        description="pandapower studies of the Malian interconnected network",
    )
    parser.add_argument("--exchange", help="path to mali_case.json")
    parser.add_argument("--output", default="results", help="output directory")
    parser.add_argument(
        "--studies",
        default="loadflow,n1,shortcircuit",
        help="comma separated: loadflow, n1, shortcircuit, year, hosting, all",
    )
    parser.add_argument("--case", default="dry_peak", help="case for N-1 and short circuit")
    parser.add_argument("--step-hours", type=int, default=3, help="annual run sampling")
    parser.add_argument("--year", type=int, default=StudyConfig().year)
    args = parser.parse_args(argv)

    exchange = _load(args.exchange)
    requested = {s.strip() for s in args.studies.split(",")}
    if "all" in requested:
        requested = {"loadflow", "n1", "shortcircuit", "year", "hosting"}

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    print("Load flow on every operating point")
    results = run_all_cases(exchange)
    for name, result in results.items():
        if result.converged:
            s = result.summary
            print(f"  {name:<11} demand {s['demand_mw']:>7.1f} MW  losses {s['losses_mw']:>6.2f} MW "
                  f"({s['losses_pct']:.2f} %)  Vmin {s['vm_min_pu']:.3f}  "
                  f"violations {s['violations']}")
        else:
            print(f"  {name:<11} did not converge")
    for path in write_loadflow(results, out):
        print(f"    -> {path}")

    n1_frames = None
    if "n1" in requested:
        print(f"N-1 contingency screening on {args.case}")
        frame = run_n1(exchange, args.case)
        n1_frames = {args.case: frame}
        counts = frame["status"].value_counts().to_dict()
        print(f"  {counts.get('secure',0)} secure, {counts.get('violated',0)} violated, "
              f"{counts.get('non-convergent',0)} without solution")
        path = out / f"n1_{args.case}.csv"
        frame.to_csv(path, index=False)
        print(f"    -> {path}")

    sc_frame = None
    if "shortcircuit" in requested:
        print(f"Short-circuit levels on {args.case}")
        sc_frame = run_short_circuit(exchange, args.case)
        path = out / f"shortcircuit_{args.case}.csv"
        sc_frame.to_csv(path, index=False)
        if "sk_max_mva" in sc_frame:
            print(f"  highest short-circuit power {sc_frame['sk_max_mva'].max():.0f} MVA "
                  f"at {sc_frame.iloc[0]['bus']}")
        print(f"    -> {path}")

    year_result = None
    if "year" in requested:
        print(f"Annual simulation, {args.step_hours} hour steps")
        catalog = load_catalog()
        year_result = run_year(
            exchange, catalog, config=StudyConfig(year=args.year), step_hours=args.step_hours
        )
        for key in ("demand_gwh", "unserved_gwh", "unserved_pct", "hours_with_shedding",
                    "hydro_gwh", "solar_gwh", "thermal_gwh", "losses_gwh"):
            if key in year_result.summary:
                print(f"  {key:<20} {year_result.summary[key]}")
        path = out / "annual_timeseries.csv"
        year_result.frame.to_csv(path)
        year_result.monthly().to_csv(out / "annual_monthly.csv")
        print(f"    -> {path}")

    hosting = None
    if "hosting" in requested:
        print("Photovoltaic hosting capacity")
        hosting = hosting_capacity(exchange)
        path = out / "hosting_capacity.csv"
        hosting.to_csv(path, index=False)
        print(f"  best site {hosting.iloc[0]['bus']} at {hosting.iloc[0]['hosting_capacity_mw']} MW")
        print(f"    -> {path}")

    report = markdown_report(
        results, n1=n1_frames, short_circuit=sc_frame, year=year_result, hosting=hosting
    )
    report_path = out / "report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nreport -> {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

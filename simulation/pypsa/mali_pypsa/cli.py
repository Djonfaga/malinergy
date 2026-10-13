"""Command line entry point: ``mali-pypsa``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .dispatch import check_results, solve
from .network import build_network
from .report import markdown_report, write_tables
from .resource import build_cutout, cutout_path


def _cmd_cutout(args: argparse.Namespace) -> int:
    print(f"Preparing an ERA5 cutout over Mali for {args.year}")
    print("  This needs a Copernicus Climate Data Store account and a ~/.cdsapirc.")
    print(f"  Target: {cutout_path(args.year)}")
    try:
        cutout = build_cutout(args.year)
    except Exception as error:  # noqa: BLE001 - reported, not hidden
        print(f"\n  failed: {error}")
        print("  Without a cutout the model falls back on the clear-sky resource")
        print("  from simulation/core, and every result says so.")
        return 1
    print(f"  done: {cutout.path}")
    return 0


def _cmd_solve(args: argparse.Namespace) -> int:
    print(f"Building the v0.1 network for {args.year}, {args.step_hours}-hourly")
    build = build_network(
        year=args.year,
        step_hours=args.step_hours,
        import_basis=args.import_basis,
        prefer_atlite=not args.no_atlite,
        include_scenario_assets=args.scenario_assets,
    )
    print(f"  demand {build.demand.annual_energy_gwh:,.0f} GWh, "
          f"peak {build.demand.peak_mw:,.0f} MW")
    print(f"  resource: {build.resource.provider}")
    print(f"  fleet: {len(build.fleet)} plants")

    print("\nSolving")
    result = solve(build, solver_name=args.solver)
    if not result.ok:
        print(f"  did not solve: {result.condition}")
        return 1

    problems = check_results(result)
    print(f"  {result.status}, checks: {'passed' if not problems else problems}")
    if problems:
        return 1

    s = result.summary
    print(f"\n  demand        {s['demand_gwh']:>9,.1f} GWh")
    print(f"  unserved      {s['unserved_gwh']:>9,.1f} GWh  ({s['unserved_pct']} %, "
          f"{s['hours_with_unserved']:,} hours)")
    print(f"  operating     {s['operating_cost_musd']:>9,.1f} MUSD  "
          f"({s['average_cost_usd_per_mwh']} USD/MWh served)")
    print(f"  emissions     {s['co2_kt']:>9,.1f} kt    ({s['co2_kg_per_kwh']} kg/kWh)")
    print("\n  energy by carrier, GWh:")
    for carrier, value in result.by_carrier_gwh.items():
        print(f"    {carrier:<10} {value:>9,.1f}")

    out = Path(args.output)
    for path in write_tables(result, out):
        print(f"\n  -> {path}" if path.name == "summary.csv" else f"  -> {path}")
    report = out / "report.md"
    report.write_text(markdown_report(result), encoding="utf-8")
    print(f"\nreport -> {report}")
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    """Both import bases, since the gap between them is a result."""
    rows = []
    for basis in ("contracted", "capacity"):
        build = build_network(
            year=args.year, step_hours=args.step_hours, import_basis=basis,
            prefer_atlite=not args.no_atlite,
        )
        result = solve(build, solver_name=args.solver)
        if not result.ok:
            print(f"{basis}: did not solve")
            continue
        s = result.summary
        rows.append({"import_basis": basis, **{
            k: s[k] for k in (
                "unserved_gwh", "unserved_pct", "hours_with_unserved",
                "operating_cost_musd", "average_cost_usd_per_mwh", "co2_kt",
            )
        }, **{f"{c}_gwh": round(v, 1) for c, v in result.by_carrier_gwh.items()}})

    import pandas as pd  # noqa: PLC0415

    frame = pd.DataFrame(rows)
    print(frame.to_string(index=False))
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out / "import_basis_comparison.csv", index=False)
    print(f"\n-> {out / 'import_basis_comparison.csv'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mali-pypsa",
        description="Single-node PyPSA dispatch model of the Malian power system",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--year", type=int, default=2024)
    common.add_argument("--step-hours", type=int, default=1)
    common.add_argument("--solver", default="highs")
    common.add_argument("--output", default="results")
    common.add_argument("--no-atlite", action="store_true",
                        help="skip the ERA5 path and use the clear-sky resource")

    p_solve = sub.add_parser("solve", parents=[common], help="run the dispatch")
    p_solve.add_argument("--import-basis", choices=["contracted", "capacity"],
                         default="contracted")
    p_solve.add_argument("--scenario-assets", action="store_true",
                         help="include plant the catalogue marks out of service")
    p_solve.set_defaults(func=_cmd_solve)

    p_compare = sub.add_parser("compare", parents=[common],
                               help="solve on both import bases and tabulate the gap")
    p_compare.set_defaults(func=_cmd_compare)

    p_cutout = sub.add_parser("cutout", help="prepare the ERA5 cutout (needs Copernicus)")
    p_cutout.add_argument("--year", type=int, default=2024)
    p_cutout.set_defaults(func=_cmd_cutout)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

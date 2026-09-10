"""Command line entry point: ``mali-energy``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .config import BUILD_DIR, StudyConfig
from .exchange import OPERATING_POINTS, build_all_cases, export_exchange
from .grid.catalog import data_card, export_json, load_catalog
from .grid.validation import validate


def _cmd_fetch(args: argparse.Namespace) -> int:
    from .cache import FetchError
    from .sources import owid, population, worldbank

    ok = True
    print("Fetching reference data")
    try:
        frame = owid.write_snapshot(refresh=args.refresh)
        print(f"  OWID energy          : {len(frame)} Malian rows "
              f"({int(frame.year.min())}-{int(frame.year.max())})")
    except FetchError as exc:
        ok = False
        print(f"  OWID energy          : FAILED - {exc}")

    try:
        pop, cities = population.write_snapshots(refresh=args.refresh)
        print(f"  Population           : {len(pop)} years")
        print(f"  Populated places     : {len(cities)} Malian entries")
    except FetchError as exc:
        print(f"  Population           : FAILED - {exc}")

    try:
        wb = worldbank.write_snapshot(refresh=args.refresh)
        print(f"  World Bank indicators: {len(wb)} years")
    except FetchError as exc:
        print(f"  World Bank indicators: unavailable - {exc}")

    if args.pvgis:
        from .sources import pvgis

        catalog = load_catalog()
        for generator in catalog.generators_by_technology("solar"):
            try:
                series = pvgis.hourly_series(
                    generator.latitude,
                    generator.longitude,
                    start_year=args.year,
                    end_year=args.year,
                    refresh=args.refresh,
                )
                print(f"  PVGIS {generator.id:<16}: {len(series)} hours")
            except FetchError as exc:
                ok = False
                print(f"  PVGIS {generator.id:<16}: FAILED - {exc}")
    return 0 if ok else 1


def _cmd_validate(args: argparse.Namespace) -> int:
    config = StudyConfig(year=args.year)
    catalog = load_catalog(ambient_c=args.ambient)
    report = validate(catalog, config)
    print(report.render())
    print()
    print(data_card(catalog).to_json())
    if report.errors:
        print(f"\n{len(report.errors)} error(s) found.", file=sys.stderr)
        return 1
    print(f"\nValidation passed with {len(report.warnings)} warning(s).")
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    config = StudyConfig(year=args.year)
    catalog = load_catalog(ambient_c=args.ambient)
    report = validate(catalog, config)
    if report.errors and not args.force:
        print(report.render(), file=sys.stderr)
        print("\nRefusing to build a case from an invalid catalogue "
              "(use --force to override).", file=sys.stderr)
        return 1

    out_dir = Path(args.output or BUILD_DIR)
    network_path = export_json(catalog, out_dir / "mali_network.json")
    case_path = export_exchange(
        out_dir / "mali_case.json",
        catalog=catalog,
        config=config,
        allow_network=args.online,
    )
    print(f"network catalogue -> {network_path}")
    print(f"study cases       -> {case_path}")

    cases = json.loads(case_path.read_text())["cases"]
    print(f"\n{'case':<12} {'demand MW':>10} {'hydro':>8} {'solar':>8} "
          f"{'thermal':>8} {'import':>8} {'unserved':>9}")
    for name, case in cases.items():
        b = case["balance"]
        print(f"{name:<12} {case['total_demand_mw']:>10.1f} {b['hydro_mw']:>8.1f} "
              f"{b['solar_mw']:>8.1f} {b['thermal_mw']:>8.1f} "
              f"{b['net_import_mw']:>8.1f} {b['unserved_mw']:>9.1f}")
    return 0


def _cmd_case(args: argparse.Namespace) -> int:
    config = StudyConfig(year=args.year)
    cases = build_all_cases(config=config)
    case = cases[args.name]
    print(json.dumps(case.to_dict(), indent=2, ensure_ascii=False))
    return 0


def _cmd_inventory(args: argparse.Namespace) -> int:
    from .cache import inventory

    rows = inventory()
    if not rows:
        print("No cached payloads. Run 'mali-energy fetch' first.")
        return 0
    print(f"{'file':<45} {'sha256':<18} {'bytes':>10}  retrieved")
    for row in rows:
        print(f"{row['file']:<45} {row['sha256']:<18} {row['bytes']:>10}  {row['retrieved']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mali-energy",
        description="Canonical data layer for the Mali power-system benchmark",
    )
    parser.add_argument("--version", action="version", version=f"mali-energy {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch", help="download the external datasets into the cache")
    p_fetch.add_argument("--refresh", action="store_true", help="ignore cached copies")
    p_fetch.add_argument("--pvgis", action="store_true", help="also fetch PVGIS series per plant")
    p_fetch.add_argument("--year", type=int, default=2023, help="year for the PVGIS series")
    p_fetch.set_defaults(func=_cmd_fetch)

    p_validate = sub.add_parser("validate", help="check the network catalogue")
    p_validate.add_argument("--year", type=int, default=StudyConfig().year)
    p_validate.add_argument("--ambient", type=float, default=40.0)
    p_validate.set_defaults(func=_cmd_validate)

    p_build = sub.add_parser("build", help="write the exchange files consumed by every tool")
    p_build.add_argument("--year", type=int, default=StudyConfig().year)
    p_build.add_argument("--ambient", type=float, default=40.0)
    p_build.add_argument("--output", help="output directory (default: build/)")
    p_build.add_argument("--online", action="store_true", help="allow live PVGIS calls")
    p_build.add_argument("--force", action="store_true", help="build despite validation errors")
    p_build.set_defaults(func=_cmd_build)

    p_case = sub.add_parser("case", help="print one operating point as JSON")
    p_case.add_argument("name", choices=list(OPERATING_POINTS))
    p_case.add_argument("--year", type=int, default=StudyConfig().year)
    p_case.set_defaults(func=_cmd_case)

    p_inv = sub.add_parser("inventory", help="list cached payloads with checksums")
    p_inv.set_defaults(func=_cmd_inventory)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

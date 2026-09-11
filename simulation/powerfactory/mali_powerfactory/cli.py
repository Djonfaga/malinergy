"""Command line entry point: ``mali-powerfactory``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mali_energy.config import BUILD_DIR
from mali_energy.exchange import load_exchange

from .api import environment_report, run_script
from .dgs import DgsExport
from .verify import verify


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mali-powerfactory",
        description="Export the Malian network to PowerFactory and verify it",
    )
    parser.add_argument("--exchange", help="path to mali_case.json")
    parser.add_argument("--output", default="build", help="where to write the DGS files")
    parser.add_argument("--case", help="export a single operating point")
    parser.add_argument("--run", help="run a script inside PowerFactory, e.g. run_loadflow.py")
    parser.add_argument("--results", default="results")
    args = parser.parse_args(argv)

    exchange_path = Path(args.exchange or (BUILD_DIR / "mali_case.json"))
    if not exchange_path.exists():
        raise SystemExit(
            f"{exchange_path} not found. Run 'mali-energy build' in simulation/core first."
        )
    exchange = load_exchange(exchange_path)

    environment = environment_report()
    print(f"PowerFactory module importable: {environment['powerfactory_module']}")
    if environment.get("note"):
        print(f"  {environment['note']}")

    out = Path(args.output)
    cases = [args.case] if args.case else list(exchange["cases"])
    failures = 0

    print("\nExporting")
    for case_name in cases:
        export = DgsExport(exchange).build(case_name)
        path = export.write(out / f"mali_{case_name}.dgs")
        report = verify(export)
        status = "ok" if report.ok else f"{len(report.errors)} error(s)"
        counts = export.statistics()
        print(
            f"  {case_name:<11} -> {path}  "
            f"({counts.get('ElmTerm', 0)} busbars, {counts.get('ElmLne', 0)} lines, "
            f"{counts.get('ElmSym', 0)} machines)  verification: {status}"
        )
        for level, check, message in report.errors + report.warnings:
            print(f"      [{level}] {check}: {message}")
        if not report.ok:
            failures += 1

    (out / "environment.json").write_text(
        json.dumps(environment, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if args.run:
        print(f"\nRunning {args.run}")
        outcome = run_script(args.run, case=args.case or "dry_peak", results_dir=args.results)
        print(f"  {outcome['status']}: {outcome.get('note', '')}")
        if outcome.get("stdout"):
            print(outcome["stdout"])

    if failures:
        print(f"\n{failures} case(s) failed verification")
        return 1
    print("\nAll exported cases verified against the canonical data.")
    print("Import into PowerFactory: File, Import, DGS, select the .dgs file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

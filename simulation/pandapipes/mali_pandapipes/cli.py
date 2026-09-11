"""Command line entry point: ``mali-pandapipes``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .coupling import evaluate_storage_flexibility, water_lost_to_load_shedding
from .hydrogen import evaluate as evaluate_hydrogen
from .hydrogen import sizing_sweep
from .water.catalog import load_water_catalog
from .water.studies import pump_outage_screening, run_case


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mali-pandapipes",
        description="Fluid network studies for Mali and their coupling to the grid",
    )
    parser.add_argument("--output", default="results", help="output directory")
    parser.add_argument(
        "--studies",
        default="hydraulics,outage,coupling,hydrogen",
        help="comma separated: hydraulics, outage, coupling, hydrogen, all",
    )
    parser.add_argument("--shed-fraction", type=float, default=0.15)
    args = parser.parse_args(argv)

    requested = {s.strip() for s in args.studies.split(",")}
    if "all" in requested:
        requested = {"hydraulics", "outage", "coupling", "hydrogen"}
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    catalog = load_water_catalog()
    print(f"Bamako water network: {catalog.meta['nodes']} nodes, {catalog.meta['pipes']} pipes, "
          f"{catalog.meta['pumps']} pumping stations")
    print(f"  serving {catalog.population_served:,} people with "
          f"{catalog.total_production_m3_day:,.0f} m3 a day")

    lines: list[str] = ["# pandapipes — Bamako water supply and the hydrogen question", ""]

    if "hydraulics" in requested:
        print("\nHydraulic cases")
        rows = []
        for case in ("average", "peak", "night"):
            result = run_case(case, catalog=catalog)
            if not result.converged:
                print(f"  {case:<9} no solution")
                continue
            s = result.summary
            rows.append(s)
            print(f"  {case:<9} {s['production_m3_day']:>9,.0f} m3/d  "
                  f"{s['electrical_power_kw']:>6.0f} kW  {s['specific_energy_kwh_m3']:.3f} kWh/m3  "
                  f"deficient {s['deficient_nodes']}  isolated {s['isolated_nodes']}")
            for finding in result.findings:
                if "below the" in finding or "no hydraulic connection" in finding:
                    print(f"      - {finding}")
            result.junctions.to_csv(out / f"water_nodes_{case}.csv", index=False)
            result.pipes.to_csv(out / f"water_pipes_{case}.csv", index=False)
        frame = pd.DataFrame(rows)
        frame.to_csv(out / "water_cases.csv", index=False)
        lines += ["## Hydraulic cases", "", _table(frame), ""]

    if "outage" in requested:
        print("\nPumping station outages, average day")
        frame = pump_outage_screening(catalog)
        frame.to_csv(out / "water_pump_outages.csv", index=False)
        for _, row in frame.iterrows():
            print(f"  {row['pump']:<18} {row['status']:<13} "
                  f"{row['population_affected'] or 0:>9,} people lose service")
        lines += ["## Pumping station outages", "", _table(frame), ""]

    if "coupling" in requested:
        print("\nCoupling with the electrical network")
        flexibility = evaluate_storage_flexibility(catalog)
        for bus, mw in flexibility.bus_loads_mw.items():
            print(f"  {bus:<22} {mw:>6.3f} MW")
        print(f"  total water pumping load {flexibility.summary['total_pumping_load_mw']:.2f} MW")
        print(f"  reservoir scheduling removes "
              f"{flexibility.summary['reduction_at_system_peak_kw']:.0f} kW from the evening peak")
        flexibility.daily.to_csv(out / "water_daily_profile.csv")
        shedding = water_lost_to_load_shedding(args.shed_fraction, catalog)
        print(f"  at {args.shed_fraction:.0%} feeder shedding, "
              f"{shedding['water_not_delivered_m3_day']:,.0f} m3 a day are not delivered "
              f"({shedding['litres_per_person_per_day_lost']} litres per person)")
        (out / "water_coupling.json").write_text(
            json.dumps(
                {"flexibility": flexibility.summary, "shedding": shedding},
                indent=2, ensure_ascii=False,
            )
        )
        lines += ["## Coupling with the electrical network", "",
                  _table(pd.DataFrame([flexibility.summary])), "",
                  _table(flexibility.daily, index=True), ""]
        lines += [f"- {f}" for f in flexibility.findings] + [""]

    if "hydrogen" in requested:
        print("\nGreen hydrogen scenario")
        outcome = evaluate_hydrogen()
        print(f"  {outcome['hydrogen_t_per_year']:,.0f} t/year, "
              f"{outcome['energy_in_hydrogen_gwh_per_year']} GWh of chemical energy")
        print(f"  electrolysis efficiency {outcome['electrolysis_efficiency_pct']} %, "
              f"energy penalty {outcome['energy_penalty_gwh']} GWh/year against the existing line")
        sweep = sizing_sweep()
        sweep.to_csv(out / "hydrogen_sizing.csv", index=False)
        (out / "hydrogen_scenario.json").write_text(json.dumps(outcome, indent=2, ensure_ascii=False))
        lines += ["## Green hydrogen scenario", "",
                  _table(pd.DataFrame([{k: v for k, v in outcome.items()
                                        if not isinstance(v, dict)}])), "",
                  "### Pipeline sizing", "", _table(sweep), "",
                  outcome["conclusion"], ""]

    report = out / "report.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nreport -> {report}")
    return 0


def _table(frame: pd.DataFrame, *, index: bool = False) -> str:
    working = frame.reset_index() if index else frame
    if working.empty:
        return "_no rows_"
    headers = [str(c) for c in working.columns]
    rows = [
        [f"{v:,.3f}".rstrip("0").rstrip(".") if isinstance(v, float) else
         ("-" if pd.isna(v) else str(v)) for v in record]
        for record in working.itertuples(index=False, name=None)
    ]
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


if __name__ == "__main__":
    raise SystemExit(main())

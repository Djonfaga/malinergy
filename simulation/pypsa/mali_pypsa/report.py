"""Result tables and a Markdown report."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .costs import merit_order
from .dispatch import DispatchResult, duration_curve, monthly_balance
from .fleet import fleet_table


def table(frame: pd.DataFrame, *, index: bool = False) -> str:
    """Render a frame as Markdown without pulling in a dependency."""
    working = frame.reset_index() if index else frame
    if working.empty:
        return "_no rows_"
    headers = [str(c) for c in working.columns]
    rows = [
        [
            f"{v:,.4g}" if isinstance(v, float) else ("-" if pd.isna(v) else str(v))
            for v in record
        ]
        for record in working.itertuples(index=False, name=None)
    ]
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def write_tables(result: DispatchResult, directory: Path) -> list[Path]:
    """Write every result table as CSV, so each figure has its data beside it."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def save(frame: pd.DataFrame | pd.Series, name: str, index: bool = False) -> None:
        path = directory / name
        frame.to_csv(path, index=index)
        written.append(path)

    save(pd.DataFrame([result.summary]), "summary.csv")
    save(result.by_carrier_gwh.rename("energy_gwh"), "energy_by_carrier.csv", index=True)
    save(result.generation_gwh.rename("energy_gwh"), "energy_by_generator.csv", index=True)
    save(result.cost_usd.rename("cost_usd"), "cost_by_generator.csv", index=True)
    save(monthly_balance(result), "monthly_balance.csv", index=True)
    save(fleet_table(result.build.fleet), "fleet.csv")
    save(merit_order(), "merit_order.csv")
    save(duration_curve(result, "price").rename("price_usd_per_mwh"), "price_duration.csv", index=True)
    save(result.prices.rename("price_usd_per_mwh"), "prices_hourly.csv", index=True)
    return written


def markdown_report(result: DispatchResult, *, title: str = "Mali PyPSA v0.1") -> str:
    """Assemble a report that can be read on its own."""
    lines = [f"# {title}", ""]

    if not result.ok:
        lines += ["The dispatch did not solve.", "", f"`{result.condition}`", ""]
        return "\n".join(lines)

    s = result.summary
    lines += [
        "## Result",
        "",
        f"- Demand **{s['demand_gwh']:,.0f} GWh**, served {s['served_gwh']:,.0f} GWh",
        f"- Unserved **{s['unserved_gwh']:,.1f} GWh** ({s['unserved_pct']} %) "
        f"over {s['hours_with_unserved']:,} hours",
        f"- Operating cost **{s['operating_cost_musd']:,.1f} million USD**, "
        f"{s['average_cost_usd_per_mwh']} USD/MWh served",
        f"- Emissions **{s['co2_kt']:,.0f} kt CO2**, {s['co2_kg_per_kwh']} kg/kWh",
        f"- Resource provider: `{s['resource_provider']}` "
        f"({'measured' if s['resource_measured'] else 'modelled'})",
        "",
        "The system cost includes unserved energy priced at the value of lost load, "
        f"which accounts for {s['unserved_share_of_cost_pct']} % of it. That share "
        "is an assumption rather than a measurement, which is why the operating "
        "cost is reported separately.",
        "",
        "## Energy by carrier",
        "",
        table(result.by_carrier_gwh.rename("energy_gwh").reset_index()),
        "",
        "## Monthly balance",
        "",
        table(monthly_balance(result), index=True),
        "",
        "## Merit order",
        "",
        table(merit_order()),
        "",
        "## Fleet",
        "",
        table(fleet_table(result.build.fleet)),
        "",
    ]

    if result.notes:
        lines += ["## Modelling notes", ""]
        lines += [f"- {note}" for note in dict.fromkeys(result.notes)]
        lines.append("")
    return "\n".join(lines)

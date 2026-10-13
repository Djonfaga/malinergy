"""Figures, each one answering a question the tables answer less quickly.

Five of them, and no more. A figure here has to earn its place by showing
something a reader would otherwise have to assemble in their head:

``monthly_balance``
    The Malian year. Hydro collapses through the dry season exactly as demand
    rises into the hot months, and fuel fills the gap.
``dry_season_week``
    What the reservoir budget buys, and what it leaves undetermined. The hydro
    band is no longer pinned at the month's mean: it moves, which is the point.
    But in April and May the month's water is spent and a third of the hours
    shed load anyway, so shifting a megawatt hour from one shedding hour to
    another changes nothing and the optimiser is indifferent to where it goes.
    The band therefore looks restless. That is a degenerate optimum, not the
    river, and it is also the finding: in the dry season Mali is short of
    energy, not of power, and no amount of re-timing fixes that.
``capacity_and_energy``
    Entitled megawatts against delivered megawatt hours. Entitled, not
    nameplate: 192 MW of the OMVS cascade belongs to Senegal and Mauritania,
    and a figure arguing about what Mali has against what Mali gets would be
    wrong by that much if it plotted the plates on the machines.
``price_duration``
    How many hours of the year are set by which plant, and how many by the
    value of lost load.
``validation``
    The model's mix against the national statistics, deviations included.

Colours come from the Okabe-Ito set, which stays distinguishable under every
common form of colour blindness and in greyscale print.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # written to files, never shown
import matplotlib.pyplot as plt
import pandas as pd

from .dispatch import DispatchResult, duration_curve, monthly_balance
from .validate import against_national_statistics

#: Okabe-Ito, assigned so that fuel reads as grey and water as blue even when
#: the figure is printed in black and white.
CARRIER_COLOURS = {
    "hydro": "#0072B2",
    "solar": "#F0E442",
    "thermal": "#404040",
    "import": "#CC79A7",
    "unserved": "#D55E00",
}
CARRIER_ORDER = ("hydro", "solar", "import", "thermal", "unserved")

MONTHS = ("J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D")


def _style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 150,
            "savefig.bbox": "tight",
            "font.size": 9,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "grid.alpha": 0.25,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def _ordered(columns) -> list[str]:
    return [c for c in CARRIER_ORDER if c in columns]


def monthly_balance_figure(result: DispatchResult, path: Path) -> Path:
    monthly = monthly_balance(result)
    carriers = _ordered(monthly.columns)
    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    bottom = pd.Series(0.0, index=monthly.index)
    for carrier in carriers:
        ax.bar(
            monthly.index,
            monthly[carrier],
            bottom=bottom,
            label=carrier,
            color=CARRIER_COLOURS[carrier],
            edgecolor="white",
            linewidth=0.4,
        )
        bottom = bottom + monthly[carrier]
    ax.plot(
        monthly.index, monthly["load_gwh"], color="black", linewidth=1.4, label="load"
    )
    ax.set_xticks(list(monthly.index))
    ax.set_xticklabels(MONTHS)
    ax.set_ylabel("GWh")
    ax.set_title("Monthly energy balance")
    ax.legend(ncol=6, frameon=False, fontsize=8, loc="upper center",
              bbox_to_anchor=(0.5, -0.08))
    fig.savefig(path)
    plt.close(fig)
    return path


def dry_season_week_figure(result: DispatchResult, path: Path, *, month: int = 5) -> Path:
    n = result.n
    energy = n.generators_t.p
    window = energy[(n.snapshots.month == month) & (n.snapshots.day <= 7)]
    if window.empty:
        window = energy.iloc[: min(len(energy), 56)]
    by_carrier = window.T.groupby(n.generators.carrier).sum().T
    carriers = _ordered(by_carrier.columns)

    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    ax.stackplot(
        window.index,
        [by_carrier[c] for c in carriers],
        labels=carriers,
        colors=[CARRIER_COLOURS[c] for c in carriers],
    )
    demand = n.loads_t.p_set.loc[window.index].sum(axis=1)
    ax.plot(window.index, demand, color="black", linewidth=1.2, label="demand")
    ax.set_ylabel("MW")
    ax.set_title(f"Dispatch over the first week of month {month}, the dry-season peak")
    ax.legend(ncol=3, frameon=True, framealpha=0.9, fontsize=8, loc="upper left")
    ax.margins(x=0)
    fig.autofmt_xdate(rotation=30)
    fig.savefig(path)
    plt.close(fig)
    return path


def capacity_and_energy_figure(result: DispatchResult, path: Path) -> Path:
    n = result.n
    # Entitled capacity, not nameplate. The figure's argument is what Mali has
    # against what Mali gets, and 192 MW of the OMVS cascade is not Mali's to
    # have; plotting nameplate here would make the left bar answer a different
    # question from the right one.
    entitled = {spec.name: spec.p_nom_mw * spec.mali_share for spec in result.build.fleet}
    # An interconnection's entitlement is what is contracted on it, which is
    # already the ceiling the model gave it. Leaving imports out would drop a
    # third of Malian supply from both panels.
    carrier_of = n.generators.carrier
    for name in n.generators.index:
        if carrier_of[name] == "import":
            entitled[name] = float(n.generators.at[name, "p_nom"])
    series = pd.Series(entitled)
    installed = series.groupby(
        [carrier_of.get(name, "unknown") for name in series.index]
    ).sum()
    energy = result.by_carrier_gwh
    carriers = [c for c in CARRIER_ORDER if c in installed.index and c != "unserved"]

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.2))
    for ax, series, unit, title in (
        (axes[0], installed, "MW", "Capacity Mali is entitled to"),
        (axes[1], energy, "GWh", "Energy delivered"),
    ):
        values = [float(series.get(c, 0.0)) for c in carriers]
        ax.barh(carriers, values, color=[CARRIER_COLOURS[c] for c in carriers])
        ax.set_xlabel(unit)
        ax.set_title(title, fontsize=9)
        ax.invert_yaxis()
    axes[1].set_yticklabels([])
    fig.suptitle("What Mali is entitled to against what it gets", fontsize=10)
    fig.savefig(path)
    plt.close(fig)
    return path


def price_duration_figure(result: DispatchResult, path: Path) -> Path:
    curve = duration_curve(result, "price")
    weight = float(result.n.snapshot_weightings["objective"].iloc[0])
    hours = [i * weight for i in range(len(curve))]
    fig, ax = plt.subplots(figsize=(7.0, 3.2))
    ax.plot(hours, curve.to_numpy(), color="#0072B2", linewidth=1.4)
    ax.set_xlabel("hours of the year at or above")
    ax.set_ylabel("marginal price, USD/MWh")
    ax.set_title("Price duration curve")
    ax.set_yscale("symlog", linthresh=10)
    fig.savefig(path)
    plt.close(fig)
    return path


def validation_figure(result: DispatchResult, path: Path) -> Path:
    report = against_national_statistics(result)
    frame = report.frame()
    fig, ax = plt.subplots(figsize=(7.0, 3.2))
    positions = range(len(frame))
    width = 0.38
    ax.bar([p - width / 2 for p in positions], frame["model_gwh"], width,
           label="model", color="#0072B2")
    ax.bar([p + width / 2 for p in positions], frame["reference_gwh"], width,
           label="national statistic", color="#999999")
    for position, row in zip(positions, frame.itertuples(), strict=True):
        ax.annotate(
            f"{row.deviation_pct:+.0f} %",
            (position, max(row.model_gwh, row.reference_gwh)),
            textcoords="offset points",
            xytext=(0, 4),
            ha="center",
            fontsize=8,
        )
    ax.set_xticks(list(positions))
    ax.set_xticklabels(frame["quantity"], fontsize=8)
    ax.set_ylabel("GWh")
    ax.set_title("Dispatched mix against figures the model did not use")
    ax.legend(frameon=False, fontsize=8)
    fig.savefig(path)
    plt.close(fig)
    return path


def write_figures(result: DispatchResult, directory: Path) -> list[Path]:
    """Write every figure, and return the paths in the order of the docstring."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    _style()
    return [
        monthly_balance_figure(result, directory / "monthly_balance.png"),
        dry_season_week_figure(result, directory / "dry_season_week.png"),
        capacity_and_energy_figure(result, directory / "capacity_and_energy.png"),
        price_duration_figure(result, directory / "price_duration.png"),
        validation_figure(result, directory / "validation.png"),
    ]

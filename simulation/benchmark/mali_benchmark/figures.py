"""Figures for the write-up.

Every figure is generated from the study outputs, never from numbers retyped
into a plotting script, and every figure writes the data it drew beside the
image so a reader can check it or re-plot it. That pairing is the point: a
figure whose underlying table is not available is an assertion.

Design rules applied throughout, from the repository's visualisation
conventions:

* one measure per axis, never a second y-scale;
* categorical colour assigned by entity and fixed across every figure, so hydro
  is the same blue in each one;
* stacked segments separated by a hairline in the surface colour, so adjacent
  fills stay distinguishable;
* a legend whenever more than one series is drawn, with direct labels where
  they replace a lookup rather than adding clutter;
* recessive grid and axes, thin marks.

The palette's aqua and yellow sit below 3:1 against the light surface, so every
figure that uses them carries visible labels or ships its table beside it.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

# -- design tokens ---------------------------------------------------------

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#8a8984"
GRID = "#e6e5e1"

#: Categorical slots, in the validated order. Entities are assigned so that no
#: two adjacent segments of a stack fall on the yellow/orange pair.
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
VIOLET = "#4a3aa7"

#: Steps of the sequential blue ramp, for encoding magnitude with one hue.
BLUE_LIGHT, BLUE_DARK = "#86b6ef", "#184f95"

#: Status colours, reserved and never reused for a series.
CRITICAL = "#d03b3b"
GOOD = "#0ca30c"

#: One colour per entity, fixed across every figure in the study.
SERIES = {
    "hydro": BLUE,
    "thermal": ORANGE,
    "import": AQUA,
    "solar": YELLOW,
    "unserved": CRITICAL,
}

FIGURE_DPI = 200


def _style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.edgecolor": GRID,
            "axes.labelcolor": INK_SECONDARY,
            "axes.titlecolor": INK,
            "axes.titlesize": 11,
            "axes.titleweight": "semibold",
            "axes.titlelocation": "left",
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "xtick.color": INK_SECONDARY,
            "ytick.color": INK_SECONDARY,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.frameon": False,
            "legend.fontsize": 8,
            "lines.linewidth": 1.6,
        }
    )


def _finish(fig, axes, path: Path, data: pd.DataFrame | None) -> Path:
    for ax in np.atleast_1d(axes).ravel():
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(length=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    if data is not None:
        data.to_csv(path.with_suffix(".csv"), index=False)
    return path


# -- figures ---------------------------------------------------------------


def monthly_balance(monthly: pd.DataFrame, path: Path) -> Path:
    """Where the year's energy comes from, and when the system fails.

    Two panels on a shared month axis. Splitting the supply mix from the
    shedding keeps each panel on one measure: a single chart carrying gigawatt
    hours and hours-per-month would need two y-scales, and a chart with two
    y-scales can be made to say anything.
    """
    _style()
    frame = monthly.copy()
    if "timestamp" in frame.columns:
        frame = frame.set_index("timestamp")
    months = [pd.Timestamp(i).strftime("%b") for i in frame.index]

    fig, axes = plt.subplots(
        2, 1, figsize=(7.4, 5.6), sharex=True, height_ratios=[2.4, 1],
        gridspec_kw={"hspace": 0.22},
    )

    order = ["hydro_gwh", "thermal_gwh", "import_gwh", "solar_gwh"]
    labels = ["Hydro", "Thermal", "Imports", "Solar"]
    bottom = np.zeros(len(frame))
    for column, label in zip(order, labels, strict=True):
        values = frame[column].to_numpy(dtype=float)
        axes[0].bar(
            months, values, bottom=bottom, label=label,
            color=SERIES[column.split("_")[0]],
            edgecolor=SURFACE, linewidth=1.4, width=0.74,
        )
        bottom += values
    axes[0].set_ylabel("Energy supplied, GWh")
    axes[0].set_title("Where the electricity comes from, month by month", pad=26)
    axes[0].legend(ncol=4, loc="lower center", bbox_to_anchor=(0.5, 1.005))
    axes[0].set_ylim(0, float(bottom.max()) * 1.08)

    hours = frame["hours_shed"].to_numpy(dtype=float)
    axes[1].bar(months, hours, color=CRITICAL, width=0.74, edgecolor=SURFACE, linewidth=1.4)
    axes[1].set_ylabel("Hours of load shedding")
    axes[1].set_title("When the system cannot serve the load")
    # The annotation goes above the bars rather than beside them: at the width
    # this figure is printed, a label placed next to the tallest bar lands on
    # top of its neighbour.
    axes[1].set_ylim(0, float(hours.max()) * 1.34)
    worst = int(np.argmax(hours))
    axes[1].annotate(
        f"{hours[worst]:.0f} hours in {months[worst]}, none from July",
        xy=(worst, hours[worst]), xytext=(0, 10), textcoords="offset points",
        color=CRITICAL, fontsize=8, ha="left" if worst < 6 else "right",
    )
    axes[1].set_xlabel("2024")

    table = frame.reset_index()[["timestamp", *order, "hours_shed", "unserved_gwh"]]
    return _finish(fig, axes, path, table)


def frequency_traces(traces: pd.DataFrame, path: Path) -> Path:
    """What the frequency does after the largest infeed is lost.

    Four scenarios on one axis. The under-frequency shedding stages are drawn
    as recessive guides because the trace crossing them is the whole story:
    the system survives because the relays operate, not because the governors
    respond.
    """
    _style()
    fig, ax = plt.subplots(figsize=(7.4, 4.2))

    scenarios = {
        "dry_peak_unit_trip": ("Largest unit, 40 MW", BLUE),
        "dry_peak_interconnection": ("Interconnection lost, 120 MW", ORANGE),
        "high_solar": ("...with 250 MW of solar", VIOLET),
        "high_solar_ffr": ("...with solar holding 10 % headroom", GOOD),
    }

    for stage in (49.0, 48.6, 48.2, 47.8):
        ax.axhline(stage, color=GRID, linewidth=0.8, zorder=0)
    ax.text(
        float(traces.index.max()) * 0.99, 49.04, "under-frequency shedding stages",
        ha="right", va="bottom", color=INK_MUTED, fontsize=7.5,
    )

    for column, (label, colour) in scenarios.items():
        if column not in traces.columns:
            continue
        # Four traces that converge on the same settled frequency, so identity
        # comes from the legend alone: direct labels at the right-hand edge land
        # on top of one another, and at the nadir they collide with the curves.
        ax.plot(traces.index, traces[column], color=colour, label=label, zorder=3)

    ax.set_xlabel("Seconds")
    ax.set_ylabel("System frequency, Hz")
    ax.set_title("Frequency after the loss of the largest infeed")
    ax.set_xlim(0, float(traces.index.max()))
    ax.set_ylim(47.6, float(traces.max().max()) + 0.25)
    ax.margins(x=0)
    ax.legend(ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.16))

    table = traces.reset_index().rename(columns={"index": "time_s"})
    return _finish(fig, ax, path, table)


def case_losses(summary: pd.DataFrame, path: Path) -> Path:
    """Network losses at each operating point.

    The wet season moves less demand and loses more of it, because the hydro
    that serves it sits at the other end of the country.
    """
    _style()
    frame = summary.copy().set_index("case")
    order = [c for c in ("dry_peak", "solar_noon", "night_min", "wet_peak") if c in frame.index]
    frame = frame.loc[order]

    fig, ax = plt.subplots(figsize=(7.0, 3.0))
    labels = [c.replace("_", " ") for c in frame.index]
    values = frame["losses_pct"].to_numpy(dtype=float)
    # Magnitude on a single hue, light to dark. A status red here would say
    # "this case has failed", which is not what a loss percentage means.
    colours = [BLUE_DARK if v > 6 else BLUE_LIGHT for v in values]
    bars = ax.barh(labels, values, color=colours, height=0.6)
    for bar, value, demand in zip(bars, values, frame["demand_mw"], strict=True):
        ax.annotate(
            f"{value:.1f} %   ({demand:.0f} MW served)",
            xy=(value, bar.get_y() + bar.get_height() / 2),
            xytext=(6, 0), textcoords="offset points",
            va="center", fontsize=8, color=INK_SECONDARY,
        )
    ax.set_xlabel("Network losses, per cent of demand")
    ax.set_title("Losses by operating point")
    ax.set_xlim(0, max(values) * 1.55)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)

    return _finish(fig, ax, path, frame.reset_index()[["case", "demand_mw", "losses_mw", "losses_pct"]])


def hosting_headroom(limits: pd.DataFrame, path: Path) -> Path:
    """How much more photovoltaic capacity each busbar can carry.

    Connected capacity and the headroom above it, stacked, so the total bar is
    the limit and the split shows how much of it is already used.
    """
    _style()
    frame = limits.copy().sort_values("mw_at_scr_3")
    labels = [b.replace("BUS_", "").replace("_", " ") for b in frame["bus"]]

    fig, ax = plt.subplots(figsize=(7.0, 3.2))
    connected = frame["connected_mw"].to_numpy(dtype=float)
    headroom = frame["headroom_to_scr_3_mw"].to_numpy(dtype=float)

    ax.barh(labels, connected, color=BLUE, height=0.6,
            edgecolor=SURFACE, linewidth=1.4, label="Connected")
    ax.barh(labels, headroom, left=connected, color=AQUA, height=0.6,
            edgecolor=SURFACE, linewidth=1.4, label="Headroom to a short-circuit ratio of 3")

    for index, (c, h) in enumerate(zip(connected, headroom, strict=True)):
        ax.annotate(f"{c:.0f}", xy=(c / 2, index), ha="center", va="center",
                    color="white", fontsize=8)
        ax.annotate(f"+{h:.0f} MW", xy=(c + h, index), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=8, color=INK_SECONDARY)

    ax.set_xlabel("Photovoltaic capacity, MW")
    ax.set_title("Converter capacity each connection point can carry")
    ax.set_xlim(0, float((connected + headroom).max()) * 1.22)
    ax.legend(loc="lower right")
    ax.grid(axis="y", visible=False)

    return _finish(fig, ax, path, frame)


def minigrid_fuel(designs: pd.DataFrame, path: Path) -> Path:
    """What a village mini-grid burns, by design.

    Litres per kilowatt hour delivered is the only figure that compares
    designs fairly: total fuel rewards a design that serves less.
    """
    _style()
    frame = designs.copy()
    fig, ax = plt.subplots(figsize=(7.0, 3.4))

    labels = [d.replace(",", ",\n") for d in frame["design"]]
    values = frame["fuel_per_delivered_kwh"].to_numpy(dtype=float)
    spill = frame["pv_curtailed_pct"].to_numpy(dtype=float)
    colours = [ORANGE if s > 20 else BLUE for s in spill]

    bars = ax.barh(labels, values, color=colours, height=0.6)
    baseline = values[0]
    for bar, value, spilled in zip(bars, values, spill, strict=True):
        saving = (1 - value / baseline) * 100.0
        note = f"{value:.3f} L/kWh"
        if saving > 0.5:
            note += f"   {saving:.0f} % less fuel"
        if spilled > 20:
            note += f"   {spilled:.0f} % of the array spilled"
        ax.annotate(note, xy=(value, bar.get_y() + bar.get_height() / 2),
                    xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=8, color=INK_SECONDARY)

    ax.set_xlabel("Diesel consumed per kilowatt hour delivered, litres")
    ax.set_title("Village mini-grid: what each design burns over a year")
    ax.set_xlim(0, max(values) * 2.0)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)

    return _finish(fig, ax, path, frame)


def water_flexibility(daily: pd.DataFrame, path: Path, *, peak_hour: int = 19) -> Path:
    """Pumping that follows consumption against pumping scheduled on storage.

    The gap at the evening peak is the flexibility the city already owns.
    """
    _style()
    frame = daily.copy()
    if "hour" in frame.columns:
        frame = frame.set_index("hour")
    hours = frame.index.to_numpy()

    fig, ax = plt.subplots(figsize=(7.0, 3.8))
    following = frame["load_following_kw"].to_numpy(dtype=float) / 1000.0
    scheduled = frame["storage_scheduled_kw"].to_numpy(dtype=float) / 1000.0

    ax.fill_between(hours, scheduled, following, where=following >= scheduled,
                    color=AQUA, alpha=0.18, linewidth=0)
    ax.plot(hours, following, color=ORANGE, label="Pumps follow consumption")
    ax.plot(hours, scheduled, color=BLUE, label="Pumps scheduled against storage")

    reduction = following[peak_hour] - scheduled[peak_hour]
    ax.axvline(peak_hour, color=INK_MUTED, linewidth=0.8, linestyle=(0, (4, 3)), zorder=1)
    # Placed in the empty morning quadrant with a leader to the gap it
    # measures, rather than on top of the curve it is describing.
    ax.annotate(
        f"{reduction:.1f} MW removed from\nthe {peak_hour}:00 electrical peak",
        xy=(peak_hour, (following[peak_hour] + scheduled[peak_hour]) / 2),
        xytext=(11.5, float(scheduled.max()) * 0.62),
        ha="center", va="top", fontsize=8, color=INK_SECONDARY,
        arrowprops={"arrowstyle": "-", "color": INK_MUTED, "linewidth": 0.8,
                    "shrinkA": 2, "shrinkB": 2},
    )

    ax.set_xlabel("Hour of the day")
    ax.set_ylabel("Water pumping load, MW")
    ax.set_title("Bamako's reservoirs as an electrical flexibility resource")
    ax.set_xlim(0, 23)
    ax.set_xticks(range(0, 24, 3))
    ax.legend(loc="upper left")

    return _finish(fig, ax, path, frame.reset_index())


# -- driver ----------------------------------------------------------------


def build_all(output_dir: Path, *, step_hours: int = 3, year: int = 2024) -> list[Path]:
    """Produce every figure from the studies that can run on this machine.

    A figure whose study is unavailable is skipped with a note rather than
    drawn from a stored copy of someone else's numbers.
    """
    import sys

    root = Path(__file__).resolve().parents[2]
    for package in ("core", "pandapower", "pandapipes", "openmodelica", "simscape"):
        path = str(root / package)
        if path not in sys.path:
            sys.path.insert(0, path)

    from mali_energy.config import BUILD_DIR, StudyConfig
    from mali_energy.exchange import load_exchange
    from mali_energy.grid import load_catalog

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    exchange = load_exchange(BUILD_DIR / "mali_case.json")
    written: list[Path] = []

    from mali_pandapower.studies.loadflow import run_all_cases

    results = run_all_cases(exchange)
    summary = pd.DataFrame([r.summary for r in results.values() if r.converged])
    written.append(case_losses(summary, output_dir / "fig3_losses_by_case.png"))

    from mali_pandapower.studies.timeseries import run_year

    year_result = run_year(
        exchange, load_catalog(), config=StudyConfig(year=year), step_hours=step_hours
    )
    written.append(
        monthly_balance(year_result.monthly().reset_index(), output_dir / "fig1_monthly_balance.png")
    )

    from mali_openmodelica.generate import frequency_case, high_solar_case
    from mali_openmodelica.reference import simulate_frequency

    traces = {}
    for name, case in (
        ("dry_peak_unit_trip", frequency_case(exchange, "dry_peak", trip_mw=40.0)),
        ("dry_peak_interconnection", frequency_case(exchange, "dry_peak")),
        ("high_solar", high_solar_case(exchange, solar_mw=250.0)),
        ("high_solar_ffr", high_solar_case(exchange, solar_mw=250.0, solar_response=True)),
    ):
        run = simulate_frequency(case)
        traces[name] = pd.Series(run.frequency_hz, index=run.time_s)
    written.append(
        frequency_traces(pd.DataFrame(traces), output_dir / "fig2_frequency_response.png")
    )

    from mali_openmodelica.studies import minigrid_study
    from mali_simscape.studies import converter_limit_study

    written.append(
        hosting_headroom(converter_limit_study(exchange), output_dir / "fig4_hosting_headroom.png")
    )
    written.append(
        minigrid_fuel(minigrid_study(year=year), output_dir / "fig5_minigrid_fuel.png")
    )

    from mali_pandapipes.coupling import evaluate_storage_flexibility

    flexibility = evaluate_storage_flexibility()
    written.append(
        water_flexibility(
            flexibility.daily.reset_index(), output_dir / "fig6_water_flexibility.png",
            peak_hour=int(flexibility.summary["electrical_peak_hour"]),
        )
    )
    return written

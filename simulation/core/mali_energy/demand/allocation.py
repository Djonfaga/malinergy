"""Allocation of national demand to network buses.

The chain is deliberately short and every link is a documented number:

    national demand (measured, OWID)
      x utility share            -> energy served by the interconnected network
      / (1 - network losses)     -> energy that must be generated
      x bus weight               -> energy per load point
      x hourly shape             -> hourly demand per load point

The alternative, distributing a peak figure directly, hides the loss and
utility-share assumptions inside a single number and makes the result
impossible to audit.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import StudyConfig
from ..grid.schema import GridCatalog
from ..sources import owid
from .profiles import DemandModel

#: Weather station used for each network zone.
ZONE_STATION = {
    "Bamako": "Bamako",
    "Koulikoro": "Bamako",
    "Kayes": "Kayes",
    "Segou": "Segou",
    "Sikasso": "Sikasso",
    "Mopti": "Segou",
}


def national_to_utility(config: StudyConfig) -> dict[str, float]:
    """Energy and power the interconnected network has to serve.

    Returns
    -------
    dict with the national demand, the utility-served energy, the energy that
    must be generated once losses are covered, and the implied average and
    peak power.
    """
    balance = owid.balance(config.year)
    national_twh = float(balance.get("electricity_demand") or 0.0)
    if national_twh <= 0:
        raise ValueError(f"no demand figure for {config.year} in the OWID extract")

    served_gwh = national_twh * 1000.0 * config.utility_demand_share
    generated_gwh = served_gwh / (1.0 - config.network_loss_fraction)
    average_mw = served_gwh * 1000.0 / 8760.0
    return {
        "year": config.year,
        "national_demand_twh": national_twh,
        "utility_share": config.utility_demand_share,
        "utility_energy_gwh": served_gwh,
        "generation_required_gwh": generated_gwh,
        "average_demand_mw": average_mw,
        "peak_demand_mw": average_mw * config.peak_to_average_ratio,
        "national_generation_twh": float(balance.get("electricity_generation") or 0.0),
        "hydro_twh": float(balance.get("hydro_electricity") or 0.0),
        "solar_twh": float(balance.get("solar_electricity") or 0.0),
        "thermal_twh": float(balance.get("fossil_electricity") or 0.0),
    }


def _effective_weights(catalog: GridCatalog) -> dict[str, float]:
    """Load weights restricted to in-service buses and renormalised to 1.0."""
    weights = {
        load.id: load.weight
        for load in catalog.loads.values()
        if catalog.buses[load.bus].in_service
    }
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("no load sits on an in-service bus")
    return {k: v / total for k, v in weights.items()}


def allocate_peak(
    catalog: GridCatalog, config: StudyConfig | None = None
) -> tuple[dict[str, tuple[float, float]], dict[str, float]]:
    """Peak-hour active and reactive demand per load.

    Returns
    -------
    ``({load_id: (p_mw, q_mvar)}, summary)`` where ``summary`` is the output of
    :func:`national_to_utility` enriched with the coincident peak actually
    allocated. Bus peaks are *coincident*: every load is evaluated at the hour
    of the system peak, not at its own peak, which is what a load-flow snapshot
    requires.
    """
    config = config or StudyConfig()
    summary = national_to_utility(config)
    weights = _effective_weights(catalog)

    # Build every load's hourly series, then find the system peak hour.
    series: dict[str, pd.Series] = {}
    for load_id, weight in weights.items():
        load = catalog.loads[load_id]
        bus = catalog.buses[load.bus]
        model = DemandModel(
            year=config.year,
            customer_class=load.customer_class,
            station=ZONE_STATION.get(bus.zone, "Bamako"),
            config=config,
        )
        series[load_id] = model.series(summary["utility_energy_gwh"] * weight)

    total = pd.concat(series.values(), axis=1).sum(axis=1)
    peak_time = total.idxmax()
    summary["allocated_peak_mw"] = float(total.max())
    summary["allocated_average_mw"] = float(total.mean())
    summary["load_factor"] = float(total.mean() / total.max())
    summary["peak_timestamp"] = str(peak_time)

    allocation: dict[str, tuple[float, float]] = {}
    for load_id, values in series.items():
        load = catalog.loads[load_id]
        p_mw = float(values.loc[peak_time])
        q_mvar = p_mw * np.tan(np.arccos(load.power_factor))
        allocation[load_id] = (p_mw, q_mvar)
    return allocation, summary


def allocate_timeseries(
    catalog: GridCatalog,
    config: StudyConfig | None = None,
    *,
    freq: str | None = None,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Hourly active demand for every load, as a DataFrame in MW.

    ``freq`` optionally resamples the result (for example ``"D"`` for daily
    means) when a study does not need the full 8760 resolution.
    """
    config = config or StudyConfig()
    summary = national_to_utility(config)
    weights = _effective_weights(catalog)

    columns: dict[str, pd.Series] = {}
    for load_id, weight in weights.items():
        load = catalog.loads[load_id]
        bus = catalog.buses[load.bus]
        model = DemandModel(
            year=config.year,
            customer_class=load.customer_class,
            station=ZONE_STATION.get(bus.zone, "Bamako"),
            config=config,
        )
        columns[load_id] = model.series(summary["utility_energy_gwh"] * weight)

    frame = pd.DataFrame(columns)
    if freq:
        frame = frame.resample(freq).mean()

    total = frame.sum(axis=1)
    summary["allocated_peak_mw"] = float(total.max())
    summary["allocated_average_mw"] = float(total.mean())
    summary["load_factor"] = float(total.mean() / total.max())
    summary["peak_timestamp"] = str(total.idxmax())
    return frame, summary

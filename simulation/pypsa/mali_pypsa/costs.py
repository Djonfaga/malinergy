"""Cost assumptions, with the derivation kept visible.

A dispatch model is a sorting machine: it orders plant by marginal cost and
runs the cheapest first. Every result therefore rests on that ordering, which
makes a table of bare marginal costs the worst possible way to state the
assumptions — a reader cannot tell whether $114/MWh came from a fuel price, an
efficiency, or somebody's recollection.

So the table stores what is actually known or assumed — a delivered fuel price,
a lower heating value, an electrical efficiency, a variable operation and
maintenance cost — and the marginal cost is computed from them here. Change the
fuel price and every dependent number moves with it.

The Malian specifics worth naming:

* **The landlocked premium.** Mali has no coast. Heavy fuel oil and distillate
  arrive through the Dakar and Abidjan corridors and are then trucked up to
  1200 km. Distillate at $1000/t is not a world price; it is a world price plus
  that journey, and it is why the merit order puts the Bamako distillate sets
  last.
* **Hydro has no fuel cost but is not free.** It is limited by the river and,
  on the OMVS plants, by Mali's share of the output. Those limits live in the
  catalogue, not in this table.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

REFERENCE_DIR = Path(__file__).resolve().parent.parent / "data" / "reference"

#: Value of lost load. The optimiser needs a price for unserved energy that is
#: above every generator's marginal cost, otherwise it sheds load whenever
#: generation is merely expensive rather than absent. $600/MWh sits well above
#: the most expensive distillate set and far below the $2000-5000/MWh used for
#: industrialised systems, which would not describe a country where supply is
#: interrupted routinely. It is a modelling parameter, not a welfare estimate,
#: and the results report how much of the cost it accounts for.
VALUE_OF_LOST_LOAD_USD_PER_MWH = 600.0


@dataclass(frozen=True)
class TechnologyCost:
    technology: str
    fuel: str
    fuel_price_usd_per_t: float
    fuel_lhv_mwh_per_t: float
    electrical_efficiency: float
    vom_usd_per_mwh: float
    co2_t_per_mwh_th: float
    source: str
    confidence: str
    note: str = ""

    @property
    def fuel_cost_usd_per_mwh_th(self) -> float:
        """Delivered fuel cost per megawatt hour of heat."""
        if self.fuel_lhv_mwh_per_t <= 0:
            return 0.0
        return self.fuel_price_usd_per_t / self.fuel_lhv_mwh_per_t

    @property
    def marginal_cost_usd_per_mwh(self) -> float:
        """Short-run marginal cost: fuel through the heat rate, plus upkeep."""
        if self.electrical_efficiency <= 0:
            return self.vom_usd_per_mwh
        return self.fuel_cost_usd_per_mwh_th / self.electrical_efficiency + self.vom_usd_per_mwh

    @property
    def co2_t_per_mwh_el(self) -> float:
        if self.electrical_efficiency <= 0:
            return 0.0
        return self.co2_t_per_mwh_th / self.electrical_efficiency


#: Confidence levels a row may declare, in descending order of evidence.
CONFIDENCE_LEVELS = ("measured", "reported", "derived", "estimated")


def _provenance(row: dict, what: str) -> tuple[str, str]:
    """Read the source and confidence of a row, refusing anything missing.

    A blank cell arrives from pandas as a float nan, and ``str(nan)`` is the
    string ``"nan"``, which is perfectly truthy. A guard written as
    ``if not source`` therefore passes a row with no provenance at all, which
    is the exact failure it was written to prevent.
    """
    source = row.get("source")
    confidence = row.get("confidence")
    source = "" if source is None or pd.isna(source) else str(source).strip()
    confidence = "" if confidence is None or pd.isna(confidence) else str(confidence).strip()
    if not source:
        raise ValueError(f"{what} has no source")
    if confidence not in CONFIDENCE_LEVELS:
        raise ValueError(
            f"{what} declares confidence {confidence!r}, which is not one of "
            f"{', '.join(CONFIDENCE_LEVELS)}"
        )
    return source, confidence


def load_costs(directory: Path | None = None) -> dict[str, TechnologyCost]:
    """Read the cost table, refusing a row without provenance."""
    directory = Path(directory or REFERENCE_DIR)
    frame = pd.read_csv(directory / "costs.csv")
    costs: dict[str, TechnologyCost] = {}
    for row in frame.to_dict("records"):
        source, confidence = _provenance(row, f"cost row {row.get('technology')!r}")
        cost = TechnologyCost(
            technology=str(row["technology"]),
            fuel=str(row["fuel"]),
            fuel_price_usd_per_t=float(row["fuel_price_usd_per_t"]),
            fuel_lhv_mwh_per_t=float(row["fuel_lhv_mwh_per_t"]),
            electrical_efficiency=float(row["electrical_efficiency"]),
            vom_usd_per_mwh=float(row["vom_usd_per_mwh"]),
            co2_t_per_mwh_th=float(row["co2_t_per_mwh_th"]),
            source=source,
            confidence=confidence,
            note=str(row.get("note", "") or ""),
        )
        costs[cost.technology] = cost
    return costs


def load_interchange_costs(directory: Path | None = None) -> dict[str, float]:
    """Price of energy across each interconnection, in dollars per megawatt hour.

    Held to the same provenance rule as the cost table. A zero price here is a
    claim about how an exchange is settled, not an absence of data, so it needs
    a source as much as a dollar figure does.
    """
    directory = Path(directory or REFERENCE_DIR)
    frame = pd.read_csv(directory / "interchange_costs.csv")
    prices: dict[str, float] = {}
    for row in frame.to_dict("records"):
        _provenance(row, f"interchange row {row.get('link')!r}")
        prices[str(row["link"])] = float(row["price_usd_per_mwh"])
    return prices


def cost_key(technology: str, fuel: str) -> str:
    """Map a catalogue generator onto a row of the cost table."""
    if technology == "thermal":
        return "thermal_hfo" if fuel == "hfo" else "thermal_diesel"
    return technology


def merit_order(costs: dict[str, TechnologyCost] | None = None) -> pd.DataFrame:
    """The cost table as the optimiser will see it, cheapest first."""
    costs = costs or load_costs()
    rows = [
        {
            "technology": c.technology,
            "fuel": c.fuel,
            "fuel_usd_per_t": c.fuel_price_usd_per_t,
            "fuel_usd_per_mwh_th": round(c.fuel_cost_usd_per_mwh_th, 2),
            "efficiency": c.electrical_efficiency,
            "vom_usd_per_mwh": c.vom_usd_per_mwh,
            "marginal_cost_usd_per_mwh": round(c.marginal_cost_usd_per_mwh, 2),
            "co2_t_per_mwh_el": round(c.co2_t_per_mwh_el, 4),
            "confidence": c.confidence,
        }
        for c in costs.values()
    ]
    frame = pd.DataFrame(rows).sort_values("marginal_cost_usd_per_mwh").reset_index(drop=True)
    return frame

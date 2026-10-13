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


def load_costs(directory: Path | None = None) -> dict[str, TechnologyCost]:
    """Read the cost table, refusing a row without provenance."""
    directory = Path(directory or REFERENCE_DIR)
    frame = pd.read_csv(directory / "costs.csv")
    costs: dict[str, TechnologyCost] = {}
    for row in frame.to_dict("records"):
        cost = TechnologyCost(
            technology=str(row["technology"]),
            fuel=str(row["fuel"]),
            fuel_price_usd_per_t=float(row["fuel_price_usd_per_t"]),
            fuel_lhv_mwh_per_t=float(row["fuel_lhv_mwh_per_t"]),
            electrical_efficiency=float(row["electrical_efficiency"]),
            vom_usd_per_mwh=float(row["vom_usd_per_mwh"]),
            co2_t_per_mwh_th=float(row["co2_t_per_mwh_th"]),
            source=str(row["source"]),
            confidence=str(row["confidence"]),
            note=str(row.get("note", "") or ""),
        )
        if not (cost.source and cost.confidence):
            raise ValueError(f"cost row {cost.technology} has no provenance")
        costs[cost.technology] = cost
    return costs


def load_interchange_costs(directory: Path | None = None) -> dict[str, float]:
    """Price of energy across each interconnection, in dollars per megawatt hour."""
    directory = Path(directory or REFERENCE_DIR)
    frame = pd.read_csv(directory / "interchange_costs.csv")
    return {str(r["link"]): float(r["price_usd_per_mwh"]) for r in frame.to_dict("records")}


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

"""Validation of the dispatch against data the model did not use.

A model calibrated on a statistic cannot be validated against it. The demand
level here comes from the national electricity balance, so reproducing total
demand proves nothing. What can be checked is the *composition* the optimiser
chose, because nothing told it how much of the year should come from hydro,
thermal or solar — that fell out of the merit order, the river and the sun.

So the comparison below is against the per-technology national figures, and it
is reported as deviations with an explanation attached, not as a pass mark.
Where the model disagrees with the statistic the disagreement is the output:
either the model is wrong, or the statistic measures something else, and saying
which is the work.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from mali_energy.config import StudyConfig
from mali_energy.sources import owid

from .dispatch import DispatchResult


@dataclass
class Comparison:
    quantity: str
    model_gwh: float
    reference_gwh: float
    basis: str
    verdict: str
    explanation: str = ""

    @property
    def deviation_pct(self) -> float:
        if self.reference_gwh == 0:
            return float("nan")
        return 100.0 * (self.model_gwh - self.reference_gwh) / self.reference_gwh


@dataclass
class ValidationReport:
    comparisons: list[Comparison] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "quantity": c.quantity,
                    "model_gwh": round(c.model_gwh, 1),
                    "reference_gwh": round(c.reference_gwh, 1),
                    "deviation_pct": round(c.deviation_pct, 1),
                    "basis": c.basis,
                    "verdict": c.verdict,
                    "explanation": c.explanation,
                }
                for c in self.comparisons
            ]
        )


def against_national_statistics(
    result: DispatchResult, config: StudyConfig | None = None
) -> ValidationReport:
    """Compare the dispatched mix with the national electricity balance."""
    config = config or StudyConfig()
    balance = owid.balance(config.year)
    report = ValidationReport()

    share = config.utility_demand_share
    by_carrier = result.by_carrier_gwh

    def national(key: str) -> float:
        return float(balance.get(key) or 0.0) * 1000.0

    # --- solar -----------------------------------------------------------
    model_solar = float(by_carrier.get("solar", 0.0))
    reference_solar = national("solar_electricity")
    report.comparisons.append(
        Comparison(
            quantity="solar",
            model_gwh=model_solar,
            reference_gwh=reference_solar,
            basis="national total; essentially all Malian solar is utility scale "
                  "and on the interconnected network, so no share is applied",
            verdict="consistent" if abs(model_solar - reference_solar) < 0.15 * reference_solar
            else "deviates",
            explanation="The resource, the plant list and the capacity factors are "
                        "independent of this statistic, so agreement here is a real check.",
        )
    )

    # --- hydro -----------------------------------------------------------
    model_hydro = float(by_carrier.get("hydro", 0.0))
    reference_hydro = national("hydro_electricity")
    deviation = 100.0 * (model_hydro - reference_hydro) / max(reference_hydro, 1e-9)
    report.comparisons.append(
        Comparison(
            quantity="hydro",
            model_gwh=model_hydro,
            reference_gwh=reference_hydro,
            basis="national total",
            verdict="consistent" if abs(deviation) < 15 else "deviates",
            explanation="The model dispatches every megawatt hour the river and "
                        "Mali's OMVS share allow, because hydro is the cheapest thing "
                        "in the merit order. A model above the statistic means either "
                        "the monthly availability table is too generous or the real "
                        "plants are not run to their limit.",
        )
    )

    # --- thermal ---------------------------------------------------------
    model_thermal = float(by_carrier.get("thermal", 0.0))
    reference_thermal = national("fossil_electricity") * share
    report.comparisons.append(
        Comparison(
            quantity="thermal",
            model_gwh=model_thermal,
            reference_gwh=reference_thermal,
            basis=f"national fossil generation times the {share:.0%} utility share",
            verdict="consistent"
            if abs(model_thermal - reference_thermal) < 0.30 * reference_thermal
            else "deviates",
            explanation="The national fossil figure includes the captive diesel plant "
                        "of the gold mines, which is not on the interconnected network; "
                        "the utility share is an assumption and this comparison inherits "
                        "its uncertainty.",
        )
    )

    # --- total -----------------------------------------------------------
    model_total = float(by_carrier.drop(labels=["unserved"], errors="ignore").sum())
    reference_total = national("electricity_generation") * share
    report.comparisons.append(
        Comparison(
            quantity="total generation",
            model_gwh=model_total,
            reference_gwh=reference_total,
            basis=f"national generation times the {share:.0%} utility share",
            verdict="consistent"
            if abs(model_total - reference_total) < 0.25 * reference_total
            else "deviates",
            explanation="Imports are inside the model total and outside the national "
                        "generation figure, so the model is expected to sit above it.",
        )
    )

    for comparison in report.comparisons:
        if comparison.verdict == "deviates":
            report.findings.append(
                f"{comparison.quantity}: model {comparison.model_gwh:,.0f} GWh against "
                f"{comparison.reference_gwh:,.0f} GWh ({comparison.deviation_pct:+.0f} %). "
                f"{comparison.explanation}"
            )

    # The import variable is not comparable with the national net-import line.
    report.findings.append(
        "the national net-import statistic is not a reference for this model's import "
        "variable: Manantali stands on Malian soil and the Senegalese and Mauritanian "
        "shares of its output are counted as Malian exports, whereas the model simply "
        "never gives Mali that energy"
    )
    return report


def against_sibling_model(result: DispatchResult, *, step_hours: int = 6) -> dict:
    """Compare with the chronological run in the pandapower branch.

    Both models dispatch the same fleet against the same demand shape, by
    different means: a merit order followed by an AC load flow there, a linear
    programme here. Agreement is not guaranteed and disagreement is informative,
    so this runs the sibling study rather than quoting a remembered number.
    """
    try:
        from mali_energy.grid import load_catalog
        from mali_pandapower.studies.timeseries import run_year
    except ImportError as error:
        return {
            "status": "not run",
            "note": f"the pandapower package is not importable here ({error}). "
                    "Check out sim/pandapower or sim/benchmark and re-run.",
        }

    from mali_energy.config import BUILD_DIR
    from mali_energy.exchange import load_exchange

    path = BUILD_DIR / "mali_case.json"
    if not path.exists():
        return {"status": "not run", "note": f"{path} not found; run 'mali-energy build'"}

    sibling = run_year(
        load_exchange(path), load_catalog(), step_hours=step_hours, solve_power_flow=False
    )
    s, p = sibling.summary, result.summary
    return {
        "status": "compared",
        "step_hours": step_hours,
        "pandapower": {
            "demand_gwh": s["demand_gwh"],
            "unserved_gwh": s["unserved_gwh"],
            "hydro_gwh": s["hydro_gwh"],
            "solar_gwh": s["solar_gwh"],
            "thermal_gwh": s["thermal_gwh"],
            "import_gwh": s["import_gwh"],
        },
        "pypsa": {
            "demand_gwh": p["demand_gwh"],
            "unserved_gwh": p["unserved_gwh"],
            "hydro_gwh": round(float(result.by_carrier_gwh.get("hydro", 0.0)), 1),
            "solar_gwh": round(float(result.by_carrier_gwh.get("solar", 0.0)), 1),
            "thermal_gwh": round(float(result.by_carrier_gwh.get("thermal", 0.0)), 1),
            "import_gwh": round(float(result.by_carrier_gwh.get("import", 0.0)), 1),
        },
        "note": "the two models use different demand bases — the sibling works at "
                "network entry and computes transmission losses, this one is a copper "
                "plate and carries those losses inside demand — so totals differ by "
                "construction and the mix is the comparable part",
    }

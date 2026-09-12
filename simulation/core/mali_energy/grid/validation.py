"""Consistency checks run before any simulation.

The checks answer one question: could this network be the Malian system at all?
They catch the failure mode that matters most in a study like this one, which
is not a crashing solver but a network that converges to confident nonsense.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..config import StudyConfig
from ..sources import owid
from .schema import GridCatalog


@dataclass
class Finding:
    level: str          # error | warning | info
    check: str
    message: str

    def __str__(self) -> str:
        return f"[{self.level.upper():7s}] {self.check}: {self.message}"


@dataclass
class ValidationReport:
    findings: list[Finding] = field(default_factory=list)

    def add(self, level: str, check: str, message: str) -> None:
        self.findings.append(Finding(level, check, message))

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def render(self) -> str:
        if not self.findings:
            return "No findings."
        return "\n".join(str(f) for f in self.findings)

    def raise_if_errors(self) -> None:
        if self.errors:
            raise ValueError(
                "network validation failed:\n" + "\n".join(str(f) for f in self.errors)
            )


def _connected_component(catalog: GridCatalog) -> set[str]:
    """Buses reachable from the slack, over in-service branches only."""
    adjacency: dict[str, set[str]] = {b.id: set() for b in catalog.active_buses()}
    for line in catalog.active_lines():
        if line.from_bus in adjacency and line.to_bus in adjacency:
            adjacency[line.from_bus].add(line.to_bus)
            adjacency[line.to_bus].add(line.from_bus)
    for trafo in catalog.transformers.values():
        if not trafo.in_service:
            continue
        if trafo.hv_bus in adjacency and trafo.lv_bus in adjacency:
            adjacency[trafo.hv_bus].add(trafo.lv_bus)
            adjacency[trafo.lv_bus].add(trafo.hv_bus)

    if not adjacency:
        return set()
    start = next(iter(adjacency))
    seen, stack = {start}, [start]
    while stack:
        node = stack.pop()
        for neighbour in adjacency[node]:
            if neighbour not in seen:
                seen.add(neighbour)
                stack.append(neighbour)
    return seen


def validate(catalog: GridCatalog, config: StudyConfig | None = None) -> ValidationReport:
    """Run every check and return the findings."""
    config = config or StudyConfig()
    report = ValidationReport()

    # -- topology ----------------------------------------------------------
    active = {b.id for b in catalog.active_buses()}
    reachable = _connected_component(catalog)
    islanded = active - reachable
    if islanded:
        report.add(
            "warning",
            "connectivity",
            f"{len(islanded)} bus(es) not connected to the main island: "
            + ", ".join(sorted(islanded)),
        )

    connected_buses = set()
    for line in catalog.active_lines():
        connected_buses.update({line.from_bus, line.to_bus})
    for trafo in catalog.transformers.values():
        if trafo.in_service:
            connected_buses.update({trafo.hv_bus, trafo.lv_bus})
    for bus_id in sorted(active - connected_buses):
        report.add("warning", "orphan-bus", f"{bus_id} carries no in-service branch")

    if config.slack_bus not in catalog.buses:
        report.add("error", "slack", f"slack bus {config.slack_bus} is not in the catalogue")
    elif not catalog.buses[config.slack_bus].in_service:
        report.add("error", "slack", f"slack bus {config.slack_bus} is out of service")

    # -- generation adequacy ----------------------------------------------
    installed = catalog.installed_capacity_mw()
    installed_mali = catalog.installed_capacity_mw(mali_share=True)
    import_capacity = sum(
        x.capacity_mw for x in catalog.interconnections.values() if x.in_service
    )
    try:
        balance = owid.balance(config.year)
    except (KeyError, FileNotFoundError):
        balance = {}

    if balance:
        national_demand_twh = float(balance.get("electricity_demand") or 0.0)
        utility_demand_twh = national_demand_twh * config.utility_demand_share
        average_mw = utility_demand_twh * 1e6 / 8760.0
        peak_mw = average_mw * config.peak_to_average_ratio
        report.add(
            "info",
            "demand",
            f"{config.year}: national demand {national_demand_twh:.2f} TWh, utility share "
            f"{config.utility_demand_share:.0%} gives {average_mw:.0f} MW average and "
            f"{peak_mw:.0f} MW peak",
        )
        firm = installed_mali + import_capacity
        if firm < peak_mw:
            report.add(
                "warning",
                "adequacy",
                f"firm capacity {firm:.0f} MW is below the {peak_mw:.0f} MW peak; "
                "the base case will rely on unserved energy or imports",
            )

        # Cross-check: can the catalogue physically have produced the energy the
        # interconnected network is credited with? The national figure includes
        # captive industrial generation (chiefly the gold mines, which run their
        # own diesel plant off-grid), so it is the utility share that must be
        # compared against the catalogue.
        generation_twh = float(balance.get("electricity_generation") or 0.0)
        if installed > 0 and generation_twh > 0:
            utility_generation_twh = generation_twh * config.utility_demand_share
            implied_cf = utility_generation_twh * 1e6 / (installed * 8760.0)
            national_cf = generation_twh * 1e6 / (installed * 8760.0)
            report.add(
                "info",
                "capacity-factor",
                f"catalogue capacity {installed:.0f} MW against {utility_generation_twh:.2f} TWh "
                f"utility generation implies a {implied_cf:.0%} average capacity factor "
                f"({national_cf:.0%} if the whole national figure were carried by this fleet)",
            )
            if implied_cf > 0.85:
                report.add(
                    "error",
                    "capacity-factor",
                    f"implied capacity factor {implied_cf:.0%} is physically impossible for a "
                    "fleet with this hydro and solar share; the catalogue is missing capacity",
                )
            elif implied_cf > 0.65:
                report.add(
                    "warning",
                    "capacity-factor",
                    f"implied capacity factor {implied_cf:.0%} is high; either the catalogue "
                    "understates capacity or the utility share is set too high",
                )
            elif implied_cf < 0.20:
                report.add(
                    "warning",
                    "capacity-factor",
                    f"implied capacity factor {implied_cf:.0%} is low; the catalogue may list "
                    "capacity that is in fact unavailable",
                )
            if national_cf > 0.85:
                report.add(
                    "info",
                    "captive-generation",
                    f"the national generation figure would need a {national_cf:.0%} capacity "
                    "factor from the catalogue fleet alone, which confirms that a large share "
                    "is produced off-grid by captive industrial plant",
                )
    else:
        report.add("warning", "calibration", "OWID snapshot unavailable; adequacy not checked")

    # -- electrical plausibility ------------------------------------------
    for line in catalog.active_lines():
        if not 0.01 < line.x_ohm_per_km < 1.0:
            report.add("error", "line-reactance", f"{line.id}: X = {line.x_ohm_per_km:.3f} ohm/km")
        if line.r_ohm_per_km >= line.x_ohm_per_km and line.vn_kv >= 150:
            report.add(
                "warning",
                "line-rx-ratio",
                f"{line.id}: R exceeds X on a transmission line, check the conductor",
            )
        if line.length_km > 400:
            report.add(
                "warning",
                "line-length",
                f"{line.id}: {line.length_km:.0f} km is long enough to need a distributed model",
            )
        if not line.length_is_measured:
            report.add(
                "info",
                "line-length",
                f"{line.id}: length {line.length_km:.1f} km derived from coordinates "
                f"with a {line.route_factor:.2f} route factor",
            )

    for trafo in catalog.transformers.values():
        if trafo.vkr_percent >= trafo.vk_percent:
            report.add(
                "error",
                "transformer-impedance",
                f"{trafo.id}: resistive component exceeds the short-circuit voltage",
            )

    # -- generation data ---------------------------------------------------
    for gen in catalog.active_generators():
        if gen.sn_mva < gen.capacity_mw:
            report.add(
                "error",
                "generator-rating",
                f"{gen.id}: apparent power {gen.sn_mva:.1f} MVA below active power "
                f"{gen.capacity_mw:.1f} MW",
            )
        if gen.provides_inertia and not 1.0 <= gen.inertia_h_s <= 10.0:
            report.add(
                "warning",
                "generator-inertia",
                f"{gen.id}: inertia constant {gen.inertia_h_s:.1f} s outside the usual range",
            )
        if gen.is_inverter_based and gen.inertia_h_s > 0:
            report.add(
                "error",
                "generator-inertia",
                f"{gen.id}: inverter-based plant declared with rotating inertia",
            )

    inertia = catalog.system_inertia_mws()
    if inertia > 0:
        report.add("info", "inertia", f"system stored energy {inertia:.0f} MW.s")

    # -- reactive compensation --------------------------------------------
    compensation = catalog.installed_compensation_mvar()
    if balance:
        peak_mw = (
            float(balance.get("electricity_demand") or 0.0)
            * config.utility_demand_share
            * 1e6
            / 8760.0
            * config.peak_to_average_ratio
        )
        mean_pf = (
            sum(ld.weight * ld.power_factor for ld in catalog.loads.values())
            / max(sum(ld.weight for ld in catalog.loads.values()), 1e-9)
        )
        reactive_demand = peak_mw * math.tan(math.acos(mean_pf))
        report.add(
            "info",
            "compensation",
            f"{compensation:.0f} Mvar installed against about {reactive_demand:.0f} Mvar "
            f"of peak reactive demand at an average power factor of {mean_pf:.2f}",
        )
        if compensation < 0.3 * reactive_demand:
            report.add(
                "warning",
                "compensation",
                "shunt compensation covers less than a third of the peak reactive "
                "demand; the peak case may not hold voltage once generator "
                "reactive limits are enforced",
            )

    for shunt in catalog.shunts.values():
        bus = catalog.buses.get(shunt.bus)
        if bus is not None and bus.vn_kv > 150.0 and shunt.type == "capacitor":
            report.add(
                "info",
                "compensation",
                f"{shunt.id} is a capacitor bank on a {bus.vn_kv:.0f} kV busbar",
            )

    # -- load weights ------------------------------------------------------
    total_weight = sum(ld.weight for ld in catalog.loads.values())
    if abs(total_weight - 1.0) > 0.02:
        report.add(
            "warning",
            "load-weights",
            f"load weights sum to {total_weight:.3f} instead of 1.0; they will be normalised",
        )

    for load in catalog.loads.values():
        bus = catalog.buses.get(load.bus)
        if bus is not None and not bus.in_service and load.weight > 0:
            report.add(
                "info",
                "load-out-of-service",
                f"{load.id} sits on the out-of-service bus {bus.id}; its weight is redistributed",
            )

    return report

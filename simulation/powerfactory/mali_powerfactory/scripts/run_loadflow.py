"""Load flow on the Malian network, run inside PowerFactory.

Mirrors the pandapower study so the two can be compared row for row: the same
operating point, the same limits, the same quantities reported.

Run from a ComPython object in the project, or:

    set PYTHONPATH=%POWERFACTORY%\\Python\\3.11
    python run_loadflow.py
"""

import os

from common import activate_study_case, get_app, write_csv

OUTPUT_DIR = os.environ.get("MALI_PF_RESULTS", "results")
VOLTAGE_LIMITS = (0.95, 1.05)
LOADING_LIMIT = 100.0


def run_case(app, case_name):
    activate_study_case(app, case_name)

    ldf = app.GetFromStudyCase("ComLdf")
    # Balanced AC load flow with the controls the Malian system actually has:
    # generator voltage control on, transformer tap changers automatic,
    # capacitor banks switched by the station controller.
    ldf.iopt_net = 0          # balanced, positive sequence
    ldf.iopt_at = 1           # automatic tap adjustment
    ldf.iopt_asht = 1         # automatic shunt switching
    ldf.iopt_lim = 1          # respect reactive power limits
    ldf.iopt_plim = 1         # respect active power limits
    ldf.iPST_at = 1
    ldf.errlf = 1e-5

    failure = ldf.Execute()
    if failure:
        app.PrintError(f"{case_name}: load flow did not converge")
        return None, [], []

    buses, branches = [], []
    for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
        if not bus.HasResults():
            continue
        buses.append(
            {
                "case": case_name,
                "bus": bus.loc_name,
                "vn_kv": bus.uknom,
                "vm_pu": bus.GetAttribute("m:u"),
                "va_deg": bus.GetAttribute("m:phiu"),
                "p_mw": bus.GetAttribute("m:Pload") - bus.GetAttribute("m:Pgen"),
            }
        )

    for line in app.GetCalcRelevantObjects("*.ElmLne"):
        if not line.HasResults():
            continue
        branches.append(
            {
                "case": case_name,
                "element": "line",
                "name": line.loc_name,
                "loading_percent": line.GetAttribute("c:loading"),
                "p_from_mw": line.GetAttribute("m:P:bus1"),
                "q_from_mvar": line.GetAttribute("m:Q:bus1"),
                "losses_mw": line.GetAttribute("c:Losses") / 1000.0,
            }
        )
    for trafo in app.GetCalcRelevantObjects("*.ElmTr2"):
        if not trafo.HasResults():
            continue
        branches.append(
            {
                "case": case_name,
                "element": "transformer",
                "name": trafo.loc_name,
                "loading_percent": trafo.GetAttribute("c:loading"),
                "p_from_mw": trafo.GetAttribute("m:P:bushv"),
                "q_from_mvar": trafo.GetAttribute("m:Q:bushv"),
                "losses_mw": trafo.GetAttribute("c:Losses") / 1000.0,
            }
        )

    low, high = VOLTAGE_LIMITS
    violations = [
        {"case": case_name, "element": "bus", "name": b["bus"],
         "quantity": "voltage", "value": round(b["vm_pu"], 4),
         "limit": low if b["vm_pu"] < low else high}
        for b in buses if b["vm_pu"] < low or b["vm_pu"] > high
    ]
    violations += [
        {"case": case_name, "element": b["element"], "name": b["name"],
         "quantity": "loading", "value": round(b["loading_percent"], 1),
         "limit": LOADING_LIMIT}
        for b in branches if b["loading_percent"] > LOADING_LIMIT
    ]

    total_losses = sum(b["losses_mw"] for b in branches)
    demand = sum(max(b["p_mw"], 0.0) for b in buses)
    summary = {
        "case": case_name,
        "demand_mw": round(demand, 2),
        "losses_mw": round(total_losses, 3),
        "losses_pct": round(100.0 * total_losses / demand, 2) if demand else 0.0,
        "vm_min_pu": round(min(b["vm_pu"] for b in buses), 4),
        "vm_max_pu": round(max(b["vm_pu"] for b in buses), 4),
        "max_loading_pct": round(max(b["loading_percent"] for b in branches), 1),
        "violations": len(violations),
    }
    return summary, buses, branches, violations


def main():
    app = get_app()
    app.ClearOutputWindow()
    summaries, all_buses, all_branches, all_violations = [], [], [], []

    for case_name in ("dry_peak", "wet_peak", "solar_noon", "night_min"):
        try:
            result = run_case(app, case_name)
        except RuntimeError as error:
            app.PrintWarn(str(error))
            continue
        if result[0] is None:
            continue
        summary, buses, branches, violations = result
        summaries.append(summary)
        all_buses.extend(buses)
        all_branches.extend(branches)
        all_violations.extend(violations)
        app.PrintInfo(
            f"{case_name}: {summary['demand_mw']:.1f} MW, "
            f"losses {summary['losses_mw']:.2f} MW ({summary['losses_pct']:.2f} %), "
            f"Vmin {summary['vm_min_pu']:.3f}, {summary['violations']} violation(s)"
        )

    write_csv(os.path.join(OUTPUT_DIR, "pf_loadflow_summary.csv"), summaries,
              ["case", "demand_mw", "losses_mw", "losses_pct", "vm_min_pu",
               "vm_max_pu", "max_loading_pct", "violations"])
    write_csv(os.path.join(OUTPUT_DIR, "pf_voltages.csv"), all_buses,
              ["case", "bus", "vn_kv", "vm_pu", "va_deg", "p_mw"])
    write_csv(os.path.join(OUTPUT_DIR, "pf_flows.csv"), all_branches,
              ["case", "element", "name", "loading_percent", "p_from_mw",
               "q_from_mvar", "losses_mw"])
    write_csv(os.path.join(OUTPUT_DIR, "pf_violations.csv"), all_violations,
              ["case", "element", "name", "quantity", "value", "limit"])
    app.PrintInfo(f"results written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

"""Short-circuit currents to IEC 60909, run inside PowerFactory.

Maximum and minimum, three-phase and single-phase, at every busbar. The same
four quantities the pandapower branch reports, so the comparison in
sim/benchmark is like for like.
"""

import os

from common import activate_study_case, get_app, write_csv

OUTPUT_DIR = os.environ.get("MALI_PF_RESULTS", "results")


def run_fault(app, fault_type, case):
    shc = app.GetFromStudyCase("ComShc")
    shc.iopt_mde = 1            # IEC 60909
    shc.iopt_shc = fault_type   # "3psc" or "spgf"
    shc.iopt_allbus = 1         # every busbar
    shc.iopt_cur = case         # 0 maximum, 1 minimum
    shc.cfac = 1.1 if case == 0 else 1.0
    shc.iopt_asc = 0
    failure = shc.Execute()
    if failure:
        app.PrintError(f"short circuit {fault_type}/{case} failed")
        return {}
    values = {}
    for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
        if not bus.HasResults():
            continue
        values[bus.loc_name] = {
            "ikss_ka": bus.GetAttribute("m:Ikss"),
            "ip_ka": bus.GetAttribute("m:ip") if case == 0 else None,
            "skss_mva": bus.GetAttribute("m:Skss"),
            "vn_kv": bus.uknom,
        }
    return values


def main():
    app = get_app()
    app.ClearOutputWindow()
    case_name = os.environ.get("MALI_PF_CASE", "dry_peak")
    activate_study_case(app, case_name)

    three_max = run_fault(app, "3psc", 0)
    three_min = run_fault(app, "3psc", 1)
    single_max = run_fault(app, "spgf", 0)
    single_min = run_fault(app, "spgf", 1)

    rows = []
    for bus, values in sorted(three_max.items(), key=lambda kv: -kv[1]["skss_mva"]):
        rows.append(
            {
                "case": case_name,
                "bus": bus,
                "vn_kv": values["vn_kv"],
                "ikss_3ph_max_ka": round(values["ikss_ka"], 4),
                "ip_3ph_ka": round(values["ip_ka"], 4) if values["ip_ka"] else None,
                "sk_max_mva": round(values["skss_mva"], 1),
                "ikss_3ph_min_ka": round(three_min.get(bus, {}).get("ikss_ka", 0.0), 4),
                "ikss_1ph_max_ka": round(single_max.get(bus, {}).get("ikss_ka", 0.0), 4),
                "ikss_1ph_min_ka": round(single_min.get(bus, {}).get("ikss_ka", 0.0), 4),
            }
        )

    # The two findings the pandapower branch reports, repeated here so the
    # comparison covers the interpretation and not only the numbers.
    for row in rows:
        if row["ikss_1ph_max_ka"] < 0.05:
            app.PrintWarn(
                f"{row['bus']}: no zero-sequence source. No earth-fault protection "
                "can be set from this model until an earthing transformer is added."
            )
        elif row["ikss_1ph_max_ka"] > row["ikss_3ph_max_ka"]:
            app.PrintInfo(
                f"{row['bus']}: earth fault exceeds three-phase fault, which is "
                "what sizes the switchgear at a solidly earthed neutral."
            )

    write_csv(
        os.path.join(OUTPUT_DIR, f"pf_shortcircuit_{case_name}.csv"), rows,
        ["case", "bus", "vn_kv", "ikss_3ph_max_ka", "ip_3ph_ka", "sk_max_mva",
         "ikss_3ph_min_ka", "ikss_1ph_max_ka", "ikss_1ph_min_ka"],
    )
    app.PrintInfo(f"{len(rows)} busbars written")


if __name__ == "__main__":
    main()

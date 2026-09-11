"""N-1 contingency analysis, run inside PowerFactory.

Uses the built-in contingency analysis rather than a scripted loop, because
that is the point of the comparison: PowerFactory does in one object what the
pandapower branch had to write out, including the post-fault actions and the
accounting of demand isolated by an outage.
"""

import os

from common import activate_study_case, get_app, safe, write_csv

OUTPUT_DIR = os.environ.get("MALI_PF_RESULTS", "results")


def build_contingency_set(app, folder):
    """One contingency per in-service branch, as the screening requires."""
    existing = folder.GetContents("*.IntEvt")
    for item in existing:
        item.Delete()

    created = 0
    for element in app.GetCalcRelevantObjects("*.ElmLne") + app.GetCalcRelevantObjects("*.ElmTr2"):
        if element.outserv:
            continue
        case = folder.CreateObject("ComOutage", element.loc_name)
        event = case.CreateObject("EvtOutage", f"trip_{element.loc_name}")
        event.p_target = element
        event.time = 0.0
        created += 1
    return created


def main():
    app = get_app()
    app.ClearOutputWindow()
    case_name = os.environ.get("MALI_PF_CASE", "dry_peak")
    activate_study_case(app, case_name)

    study_case = app.GetActiveStudyCase()
    folder = study_case.CreateObject("IntFolder", "Contingencies")
    count = build_contingency_set(app, folder)
    app.PrintInfo(f"{count} contingencies defined")

    contingency = app.GetFromStudyCase("ComSimoutage")
    contingency.iopt_method = 0        # AC load flow for each case
    contingency.p_cases = folder
    contingency.iopt_lim = 1
    failure = contingency.Execute()
    if failure:
        app.PrintError("contingency analysis failed")
        return

    rows = []
    results = app.GetFromStudyCase("ComRes")
    for case in folder.GetContents("*.ComOutage"):
        rows.append(
            {
                "case": case_name,
                "outage": case.loc_name,
                "converged": safe(case, "iConverged", 1),
                "max_loading_pct": safe(case, "cmaxload", None),
                "vm_min_pu": safe(case, "cminvolt", None),
                "vm_max_pu": safe(case, "cmaxvolt", None),
                "violations": safe(case, "cviol", None),
            }
        )

    write_csv(
        os.path.join(OUTPUT_DIR, f"pf_contingency_{case_name}.csv"), rows,
        ["case", "outage", "converged", "max_loading_pct", "vm_min_pu",
         "vm_max_pu", "violations"],
    )
    app.PrintInfo(f"{len(rows)} contingencies written")


if __name__ == "__main__":
    main()

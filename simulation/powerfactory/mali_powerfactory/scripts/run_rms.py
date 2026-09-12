"""RMS dynamic simulation of a generation trip, run inside PowerFactory.

The same event the Modelica branch simulates: the loss of the largest infeed at
the dry-season peak. Comparing the frequency trace against the Modelica one is
the most demanding check in the whole repository, because it exercises the
machine models, the governors and the load model at once.
"""

import os

from common import activate_study_case, get_app, write_csv

OUTPUT_DIR = os.environ.get("MALI_PF_RESULTS", "results")
TRIP_TIME_S = 5.0
STOP_TIME_S = 60.0


def main():
    app = get_app()
    app.ClearOutputWindow()
    case_name = os.environ.get("MALI_PF_CASE", "dry_peak")
    target_name = os.environ.get("MALI_PF_TRIP", "XC_CIV")
    activate_study_case(app, case_name)

    targets = [
        obj
        for obj in app.GetCalcRelevantObjects("*.ElmXnet") + app.GetCalcRelevantObjects("*.ElmSym")
        if obj.loc_name == target_name
    ]
    if not targets:
        app.PrintError(f"nothing called {target_name} to trip")
        return
    target = targets[0]

    events = app.GetFromStudyCase("IntEvt")
    for event in events.GetContents():
        event.Delete()
    trip = events.CreateObject("EvtOutage", f"trip_{target_name}")
    trip.p_target = target
    trip.time = TRIP_TIME_S

    # Record the frequency of every machine and the total demand.
    monitor = app.GetFromStudyCase("ElmRes")
    for machine in app.GetCalcRelevantObjects("*.ElmSym"):
        monitor.AddVariable(machine, "s:xspeed")
        monitor.AddVariable(machine, "s:P1")
    for load in app.GetCalcRelevantObjects("*.ElmLod"):
        monitor.AddVariable(load, "m:P:bus1")

    initial = app.GetFromStudyCase("ComInc")
    initial.iopt_sim = "rms"       # balanced RMS, not EMT
    initial.iopt_net = "sym"
    initial.iopt_show = 1
    initial.dtgrd = 0.01
    initial.tstart = 0.0
    if initial.Execute():
        app.PrintError("initial conditions failed; the load flow underneath must solve first")
        return

    simulate = app.GetFromStudyCase("ComSim")
    simulate.tstop = STOP_TIME_S
    if simulate.Execute():
        app.PrintError("RMS simulation failed")
        return

    export = app.GetFromStudyCase("ComRes")
    export.pResult = monitor
    export.iopt_exp = 6            # comma separated
    export.f_name = os.path.join(OUTPUT_DIR, f"pf_rms_{case_name}_{target_name}.csv")
    export.iopt_sep = 1
    export.iopt_honly = 0
    export.Execute()

    app.PrintInfo(
        f"RMS run written to {export.f_name}. Compare the frequency trace with "
        "the Modelica result in sim/openmodelica and with the SciPy reference."
    )


if __name__ == "__main__":
    main()

"""Capability matrix across the five environments.

Every row is a claim about what a tool did or did not do during this study, and
every claim carries the evidence for it: the module that had to be written by
hand, the test that locks the behaviour in, or the note recording that the tool
could not be run here at all.

The matrix is not a feature list copied from a brochure. A feature a tool has
but that cost a day to find and configure is not the same as one that works out
of the box, and a tool that cannot be run without a licence is not comparable
to one that installs with pip. Those distinctions are recorded here because
they are the ones that decide what a Malian engineering office can actually
use.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

TOOLS = ["pandapower", "pandapipes", "PowerFactory", "OpenModelica", "Simscape Electrical"]

#: How a capability is provided.
NATIVE = "built in"
SCRIPTED = "written by hand"
ABSENT = "not available"
PARTIAL = "partly"
NOT_APPLICABLE = "n/a"


@dataclass
class Capability:
    area: str
    capability: str
    support: dict[str, str]
    evidence: str = ""
    note: str = ""
    weight: int = 1


#: Filled from what actually happened while building this repository.
CAPABILITIES: list[Capability] = [
    Capability(
        area="Steady state",
        capability="Balanced AC load flow",
        support={
            "pandapower": NATIVE, "pandapipes": NOT_APPLICABLE, "PowerFactory": NATIVE,
            "OpenModelica": SCRIPTED, "Simscape Electrical": PARTIAL,
        },
        evidence="mali_pandapower/studies/loadflow.py",
        note="Simscape can do it through a load-flow tool on a Specialized Power "
             "Systems model, but the workflow is an initialisation step rather "
             "than a study.",
    ),
    Capability(
        area="Steady state",
        capability="Unbalanced and zero-sequence data",
        support={
            "pandapower": NATIVE, "pandapipes": NOT_APPLICABLE, "PowerFactory": NATIVE,
            "OpenModelica": ABSENT, "Simscape Electrical": NATIVE,
        },
        evidence="grid/electrical.py carries Carson-Clem zero-sequence values "
                 "through to both exports",
    ),
    Capability(
        area="Steady state",
        capability="Automatic tap changing and shunt switching",
        support={
            "pandapower": SCRIPTED, "pandapipes": NOT_APPLICABLE, "PowerFactory": NATIVE,
            "OpenModelica": ABSENT, "Simscape Electrical": ABSENT,
        },
        evidence="mali_pandapower/operations.py::switch_shunts, 90 lines "
                 "including oscillation detection",
        note="Capacitor banks sized for the evening peak drive the network to "
             "1.32 pu at four in the morning. This had to be written out for "
             "pandapower; PowerFactory has a station controller.",
        weight=2,
    ),
    Capability(
        area="Steady state",
        capability="Loss-consistent dispatch (balancing across machines)",
        support={
            "pandapower": SCRIPTED, "pandapipes": NOT_APPLICABLE, "PowerFactory": NATIVE,
            "OpenModelica": NOT_APPLICABLE, "Simscape Electrical": NOT_APPLICABLE,
        },
        evidence="mali_pandapower/operations.py::rebalance_dispatch",
        note="Losses vary from 3.6 % to 7.3 % across the four cases; the "
             "difference lands on the slack machine unless it is corrected.",
        weight=2,
    ),
    Capability(
        area="Steady state",
        capability="Reporting a reactive shortfall instead of failing to converge",
        support={
            "pandapower": SCRIPTED, "pandapipes": NOT_APPLICABLE, "PowerFactory": PARTIAL,
            "OpenModelica": NOT_APPLICABLE, "Simscape Electrical": NOT_APPLICABLE,
        },
        evidence="mali_pandapower/operations.py::reactive_shortfall",
        note="Both tools stop at non-convergence by default. Turning that into "
             "'Bamako is 71 Mvar short' was work in either.",
    ),
    Capability(
        area="Fault analysis",
        capability="IEC 60909 short circuit",
        support={
            "pandapower": NATIVE, "pandapipes": NOT_APPLICABLE, "PowerFactory": NATIVE,
            "OpenModelica": ABSENT, "Simscape Electrical": PARTIAL,
        },
        evidence="studies/shortcircuit.py and scripts/run_shortcircuit.py",
    ),
    Capability(
        area="Fault analysis",
        capability="Contingency analysis with isolated-demand accounting",
        support={
            "pandapower": SCRIPTED, "pandapipes": SCRIPTED, "PowerFactory": NATIVE,
            "OpenModelica": ABSENT, "Simscape Electrical": ABSENT,
        },
        evidence="studies/contingency.py, including a topology search for buses "
                 "left without a source",
        weight=2,
    ),
    Capability(
        area="Dynamics",
        capability="RMS frequency dynamics with governors",
        support={
            "pandapower": ABSENT, "pandapipes": NOT_APPLICABLE, "PowerFactory": NATIVE,
            "OpenModelica": NATIVE, "Simscape Electrical": NATIVE,
        },
        evidence="MaliEnergy.Systems.InterconnectedFrequency",
        weight=2,
    ),
    Capability(
        area="Dynamics",
        capability="EMT and converter control design",
        support={
            "pandapower": ABSENT, "pandapipes": NOT_APPLICABLE, "PowerFactory": NATIVE,
            "OpenModelica": PARTIAL, "Simscape Electrical": NATIVE,
        },
        evidence="matlab/+mali/addControlSubsystem.m and mali_simscape/reference.py",
    ),
    Capability(
        area="Dynamics",
        capability="Standard machine, governor and exciter model library",
        support={
            "pandapower": ABSENT, "pandapipes": NOT_APPLICABLE, "PowerFactory": NATIVE,
            "OpenModelica": PARTIAL, "Simscape Electrical": NATIVE,
        },
        note="OpenModelica has the Modelica libraries, but assembling a "
             "governor from them took as long as writing one.",
    ),
    Capability(
        area="Fluids",
        capability="Water, gas and heat networks",
        support={
            "pandapower": NOT_APPLICABLE, "pandapipes": NATIVE, "PowerFactory": ABSENT,
            "OpenModelica": PARTIAL, "Simscape Electrical": PARTIAL,
        },
        evidence="mali_pandapipes/water",
        note="Simscape has a fluids product and Modelica has thermal libraries; "
             "neither is a network analysis tool.",
    ),
    Capability(
        area="Fluids",
        capability="Coupling a fluid network to an electrical one",
        support={
            "pandapower": SCRIPTED, "pandapipes": SCRIPTED, "PowerFactory": ABSENT,
            "OpenModelica": NATIVE, "Simscape Electrical": NATIVE,
        },
        evidence="mali_pandapipes/coupling.py",
        note="The multi-physics tools do this by construction. The network "
             "tools needed a bridge, which is 150 lines and a shared busbar "
             "name.",
    ),
    Capability(
        area="Workflow",
        capability="Scriptable without a graphical session",
        support={
            "pandapower": NATIVE, "pandapipes": NATIVE, "PowerFactory": PARTIAL,
            "OpenModelica": NATIVE, "Simscape Electrical": PARTIAL,
        },
        note="PowerFactory and MATLAB both script well, but both need an "
             "installed licence to do anything at all.",
        weight=2,
    ),
    Capability(
        area="Workflow",
        capability="Runs in this repository's automated checks",
        support={
            "pandapower": NATIVE, "pandapipes": NATIVE, "PowerFactory": ABSENT,
            "OpenModelica": ABSENT, "Simscape Electrical": ABSENT,
        },
        evidence="20 and 18 tests respectively, executed on every change",
        note="This is the sharpest division in the table. Two of the five were "
             "verified by running them; three were verified by writing a second "
             "implementation and checking the export.",
        weight=3,
    ),
    Capability(
        area="Workflow",
        capability="Installs without a licence",
        support={
            "pandapower": NATIVE, "pandapipes": NATIVE, "PowerFactory": ABSENT,
            "OpenModelica": NATIVE, "Simscape Electrical": ABSENT,
        },
        evidence="pip install; OpenModelica is a package install",
        weight=3,
    ),
    Capability(
        area="Workflow",
        capability="Model readable and reviewable as text",
        support={
            "pandapower": NATIVE, "pandapipes": NATIVE, "PowerFactory": PARTIAL,
            "OpenModelica": NATIVE, "Simscape Electrical": SCRIPTED,
        },
        evidence="matlab/+mali/buildSimscapeModel.m builds the model by script "
                 "so it is not a binary .slx",
        note="PowerFactory projects are a database; DGS makes them reviewable "
             "on the way in and out but not in place.",
        weight=2,
    ),
    Capability(
        area="Workflow",
        capability="Interchange with the other tools",
        support={
            "pandapower": NATIVE, "pandapipes": NATIVE, "PowerFactory": NATIVE,
            "OpenModelica": PARTIAL, "Simscape Electrical": PARTIAL,
        },
        evidence="mali_powerfactory/dgs.py, 470 lines to write DGS correctly",
        note="Every tool reads something. Getting the same network into all "
             "five was the largest single piece of work in this repository.",
    ),
]

#: Numeric weights used for the summary score.
SCORE = {NATIVE: 1.0, PARTIAL: 0.5, SCRIPTED: 0.25, ABSENT: 0.0}


def matrix() -> pd.DataFrame:
    """The capability matrix as a table."""
    rows = []
    for capability in CAPABILITIES:
        row = {"area": capability.area, "capability": capability.capability}
        row.update({tool: capability.support.get(tool, ABSENT) for tool in TOOLS})
        row["evidence"] = capability.evidence
        rows.append(row)
    return pd.DataFrame(rows)


def scores() -> pd.DataFrame:
    """A weighted score per tool, with the capabilities that do not apply excluded.

    The score is a summary, not a verdict. A tool that scores low because it is
    a fluid solver being asked about short-circuit currents has not failed at
    anything.
    """
    rows = []
    for tool in TOOLS:
        applicable = [c for c in CAPABILITIES if c.support.get(tool) != NOT_APPLICABLE]
        total_weight = sum(c.weight for c in applicable)
        earned = sum(SCORE.get(c.support.get(tool, ABSENT), 0.0) * c.weight for c in applicable)
        rows.append(
            {
                "tool": tool,
                "applicable_capabilities": len(applicable),
                "built_in": sum(1 for c in applicable if c.support[tool] == NATIVE),
                "partly": sum(1 for c in applicable if c.support[tool] == PARTIAL),
                "written_by_hand": sum(1 for c in applicable if c.support[tool] == SCRIPTED),
                "not_available": sum(1 for c in applicable if c.support[tool] == ABSENT),
                "weighted_score": round(earned / total_weight, 3) if total_weight else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values("weighted_score", ascending=False).reset_index(drop=True)


def hand_written_work() -> pd.DataFrame:
    """What each tool made us write that another provides.

    This is the column an engineering office should read: it is the difference
    between a licence fee and an engineer's month.
    """
    rows = []
    for capability in CAPABILITIES:
        scripted = [tool for tool, level in capability.support.items() if level == SCRIPTED]
        native = [tool for tool, level in capability.support.items() if level == NATIVE]
        if scripted and native:
            rows.append(
                {
                    "capability": capability.capability,
                    "written_by_hand_for": ", ".join(scripted),
                    "built_into": ", ".join(native),
                    "evidence": capability.evidence,
                    "why_it_matters": capability.note,
                }
            )
    return pd.DataFrame(rows)

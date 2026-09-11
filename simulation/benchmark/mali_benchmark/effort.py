"""What each branch cost, measured rather than asserted.

Lines of code are a poor measure of anything on their own. They are used here
for one narrow purpose: to show how much had to be written to obtain a
capability that another tool provides, which is the trade an engineering office
is actually making when it chooses between a licence and an open library.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]

BRANCHES = {
    "core (shared data layer)": ["core/mali_energy"],
    "pandapower": ["pandapower/mali_pandapower"],
    "pandapipes": ["pandapipes/mali_pandapipes"],
    "OpenModelica": ["openmodelica/mali_openmodelica", "openmodelica/modelica"],
    "Simscape Electrical": ["simscape/mali_simscape", "simscape/matlab"],
    "PowerFactory": ["powerfactory/mali_powerfactory"],
    "benchmark": ["benchmark/mali_benchmark"],
}

TEST_DIRS = {
    "core (shared data layer)": "core/tests",
    "pandapower": "pandapower/tests",
    "pandapipes": "pandapipes/tests",
    "OpenModelica": "openmodelica/tests",
    "Simscape Electrical": "simscape/tests",
    "PowerFactory": "powerfactory/tests",
    "benchmark": "benchmark/tests",
}

CODE_SUFFIXES = {".py", ".mo", ".m"}


def _count(path: Path) -> tuple[int, int, int]:
    """Return (files, code lines, comment or docstring lines)."""
    files = code = commentary = 0
    if not path.exists():
        return 0, 0, 0
    for item in sorted(path.rglob("*")):
        if item.suffix not in CODE_SUFFIXES or not item.is_file():
            continue
        files += 1
        in_docstring = False
        for raw in item.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line:
                continue
            if item.suffix == ".py":
                if line.startswith(('"""', "'''")) and line.count('"""') == 1:
                    in_docstring = not in_docstring
                    commentary += 1
                    continue
                if in_docstring or line.startswith("#"):
                    commentary += 1
                    continue
            elif line.startswith(("//", "%", "*")):
                commentary += 1
                continue
            code += 1
    return files, code, commentary


def effort_table() -> pd.DataFrame:
    rows = []
    for branch, directories in BRANCHES.items():
        files = code = commentary = 0
        for directory in directories:
            f, c, d = _count(REPO_ROOT / directory)
            files += f
            code += c
            commentary += d
        test_files, test_code, _ = _count(REPO_ROOT / TEST_DIRS[branch])
        rows.append(
            {
                "branch": branch,
                "files": files,
                "code_lines": code,
                "commentary_lines": commentary,
                "commentary_ratio": round(commentary / code, 2) if code else 0.0,
                "test_files": test_files,
                "test_lines": test_code,
            }
        )
    frame = pd.DataFrame(rows)
    total = {
        "branch": "total",
        "files": frame["files"].sum(),
        "code_lines": frame["code_lines"].sum(),
        "commentary_lines": frame["commentary_lines"].sum(),
        "commentary_ratio": round(
            frame["commentary_lines"].sum() / max(frame["code_lines"].sum(), 1), 2
        ),
        "test_files": frame["test_files"].sum(),
        "test_lines": frame["test_lines"].sum(),
    }
    return pd.concat([frame, pd.DataFrame([total])], ignore_index=True)


def access_table() -> pd.DataFrame:
    """What it takes to run each tool at all.

    The column that decides whether a result can be reproduced by a reader, a
    reviewer or a Malian engineering office.
    """
    return pd.DataFrame(
        [
            {
                "tool": "pandapower",
                "licence": "BSD-3, free",
                "installation": "pip install pandapower",
                "runs_in_ci": True,
                "reproducible_by_a_reader": True,
            },
            {
                "tool": "pandapipes",
                "licence": "BSD-3, free",
                "installation": "pip install pandapipes",
                "runs_in_ci": True,
                "reproducible_by_a_reader": True,
            },
            {
                "tool": "OpenModelica",
                "licence": "OSMC-PL, free",
                "installation": "package install, about 1 GB",
                "runs_in_ci": False,
                "reproducible_by_a_reader": True,
            },
            {
                "tool": "PowerFactory",
                "licence": "commercial, per seat",
                "installation": "licensed installer and a dongle or licence server",
                "runs_in_ci": False,
                "reproducible_by_a_reader": False,
            },
            {
                "tool": "Simscape Electrical",
                "licence": "commercial, MATLAB plus two toolboxes",
                "installation": "MathWorks installer and a licence",
                "runs_in_ci": False,
                "reproducible_by_a_reader": False,
            },
        ]
    )

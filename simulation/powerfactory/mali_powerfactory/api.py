"""External access to PowerFactory, where a licence and an installation exist."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent / "scripts"


def powerfactory_available() -> bool:
    """True when the ``powerfactory`` module can be imported.

    It ships with the application and is only importable when the installation
    directory for the running Python version is on the path.
    """
    try:
        import powerfactory  # noqa: F401, PLC0415
    except Exception:  # noqa: BLE001
        return False
    return True


def powerfactory_executable() -> str | None:
    for name in ("PowerFactory", "powerfactory", "digpf"):
        found = shutil.which(name)
        if found:
            return found
    return None


def environment_report() -> dict:
    """What is present on this machine, stated plainly."""
    return {
        "python": sys.version.split()[0],
        "powerfactory_module": powerfactory_available(),
        "powerfactory_executable": powerfactory_executable(),
        "pythonpath_hint": os.environ.get("PYTHONPATH", ""),
        "note": (
            "PowerFactory is licensed software and is not installed here. The "
            "DGS export and its verification run anywhere; the scripts in "
            "mali_powerfactory/scripts run inside PowerFactory itself."
        )
        if not powerfactory_available()
        else "",
    }


def run_script(name: str, *, case: str = "dry_peak", results_dir: str = "results") -> dict:
    """Run one of the scripts through the external PowerFactory engine."""
    script = SCRIPTS / name
    if not script.exists():
        raise FileNotFoundError(f"no script called {name} in {SCRIPTS}")
    if not powerfactory_available():
        return {
            "status": "not run",
            "script": name,
            "note": (
                "the powerfactory module is not importable. Put the "
                "PowerFactory Python directory for this interpreter version on "
                "PYTHONPATH, or run the script from a ComPython object inside "
                "the project."
            ),
        }

    environment = dict(os.environ)
    environment["MALI_PF_CASE"] = case
    environment["MALI_PF_RESULTS"] = results_dir
    outcome = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(SCRIPTS),
        env=environment,
        capture_output=True,
        text=True,
        timeout=7200,
    )
    return {
        "status": "ran" if outcome.returncode == 0 else "failed",
        "script": name,
        "returncode": outcome.returncode,
        "stdout": outcome.stdout[-4000:],
        "stderr": outcome.stderr[-2000:],
    }

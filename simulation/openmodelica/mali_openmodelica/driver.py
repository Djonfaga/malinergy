"""OpenModelica driver.

Compiles and simulates the Modelica library through OMPython. This requires an
OpenModelica installation (the ``omc`` compiler) on the machine running it;
where that is absent, :mod:`mali_openmodelica.reference` integrates the same
equations with SciPy and the studies fall back to it, saying so in the result.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

MODELICA_ROOT = Path(__file__).resolve().parents[1] / "modelica"
LIBRARY = MODELICA_ROOT / "MaliEnergy" / "package.mo"


def openmodelica_available() -> bool:
    """True when an ``omc`` compiler is on the path."""
    return shutil.which("omc") is not None


def openmodelica_version() -> str | None:
    if not openmodelica_available():
        return None
    try:
        out = subprocess.run(["omc", "--version"], capture_output=True, text=True, timeout=30)
        return out.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


@dataclass
class SimulationResult:
    model: str
    ok: bool
    frame: pd.DataFrame | None = None
    message: str = ""
    result_file: Path | None = None


def simulate(
    model: str,
    *,
    start_time: float = 0.0,
    stop_time: float = 60.0,
    intervals: int = 6000,
    tolerance: float = 1e-8,
    overrides: dict[str, float | bool] | None = None,
    work_dir: Path | None = None,
) -> SimulationResult:
    """Compile and run one model, returning its trajectories.

    Parameters
    ----------
    model:
        Fully qualified Modelica class, e.g.
        ``MaliEnergy.Studies.UnitTripDrySeason``.
    overrides:
        Parameter values applied at simulation time, so a parameter study does
        not require recompiling.
    """
    if not openmodelica_available():
        return SimulationResult(
            model=model,
            ok=False,
            message=(
                "no OpenModelica compiler found. Install OpenModelica and put "
                "'omc' on the path, then re-run; until then the studies use the "
                "SciPy reference implementation of the same equations."
            ),
        )

    from OMPython import OMCSessionZMQ

    work_dir = Path(work_dir or (MODELICA_ROOT.parent / "build" / "modelica"))
    work_dir.mkdir(parents=True, exist_ok=True)

    session = OMCSessionZMQ()
    try:
        session.sendExpression(f'cd("{work_dir.as_posix()}")')
        session.sendExpression("loadModel(Modelica)")
        loaded = session.sendExpression(f'loadFile("{LIBRARY.as_posix()}")')
        if loaded is not True:
            return SimulationResult(
                model=model, ok=False,
                message=f"could not load the library: {session.sendExpression('getErrorString()')}",
            )

        flags = ""
        if overrides:
            pairs = ",".join(
                f"{k}={'true' if v is True else 'false' if v is False else v}"
                for k, v in overrides.items()
            )
            flags = f', simflags="-override {pairs}"'

        command = (
            f"simulate({model}, startTime={start_time}, stopTime={stop_time}, "
            f"numberOfIntervals={intervals}, tolerance={tolerance}{flags})"
        )
        outcome = session.sendExpression(command)
        errors = session.sendExpression("getErrorString()")

        result_file = None
        if isinstance(outcome, dict):
            result_file = outcome.get("resultFile") or None
        if not result_file:
            return SimulationResult(model=model, ok=False, message=errors or "no result file")

        path = Path(result_file)
        frame = read_result(path)
        return SimulationResult(model=model, ok=True, frame=frame, result_file=path, message=errors)
    finally:
        try:
            session.sendExpression("quit()")
        except Exception:  # noqa: BLE001
            pass


def read_result(path: Path) -> pd.DataFrame:
    """Read an OpenModelica ``.mat`` result file into a DataFrame."""
    from scipy.io import loadmat

    raw = loadmat(str(path))
    names = ["".join(chr(c) for c in row if c).strip() for row in raw["name"].T]
    data_2 = raw.get("data_2")
    data_1 = raw.get("data_1")
    info = raw["dataInfo"].T

    columns: dict[str, list] = {}
    length = data_2.shape[1] if data_2 is not None else 1
    for index, name in enumerate(names):
        block, row = int(info[index][0]), int(info[index][1])
        sign = -1.0 if row < 0 else 1.0
        row = abs(row) - 1
        if block == 1 and data_1 is not None:
            columns[name] = [sign * float(data_1[row][0])] * length
        elif block == 2 and data_2 is not None:
            columns[name] = (sign * data_2[row]).tolist()
    frame = pd.DataFrame(columns)
    if "time" in frame:
        frame = frame.set_index("time")
    return frame

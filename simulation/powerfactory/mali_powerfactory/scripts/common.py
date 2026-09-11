"""Helpers shared by the scripts that run inside PowerFactory.

These modules are executed by PowerFactory's own Python engine, where the
``powerfactory`` module is provided by the application. They are therefore not
importable from the outside and are not exercised by this repository's tests;
what is tested is the DGS export they operate on.
"""

import csv
import os


def get_app():
    """Return the PowerFactory application object, or raise with a clear message."""
    try:
        import powerfactory  # noqa: PLC0415 - provided by the host application
    except ImportError as exc:  # pragma: no cover - only outside PowerFactory
        raise RuntimeError(
            "this script runs inside PowerFactory. Either execute it from a "
            "ComPython object in the project, or start Python with the "
            "PowerFactory installation directory on PYTHONPATH so that "
            "'import powerfactory' resolves."
        ) from exc
    app = powerfactory.GetApplication()
    if app is None:  # pragma: no cover
        raise RuntimeError("PowerFactory returned no application object")
    return app


def activate_study_case(app, name):
    """Activate a study case by name, listing what exists if it is absent."""
    folder = app.GetProjectFolder("study")
    cases = folder.GetContents("*.IntCase")
    for case in cases:
        if case.loc_name == name:
            case.Activate()
            return case
    available = ", ".join(c.loc_name for c in cases)
    raise RuntimeError(f"study case {name!r} not found. Available: {available}")


def write_csv(path, rows, columns):
    """Write results next to the project so they can be compared with the others."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def safe(obj, attribute, default=None):
    """Read an attribute that may not exist on every object class."""
    try:
        value = getattr(obj, attribute)
    except AttributeError:
        return default
    return default if value is None else value

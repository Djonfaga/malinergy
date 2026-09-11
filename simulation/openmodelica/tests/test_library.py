"""Structural checks on the Modelica library itself.

These cannot replace compiling it, but they catch the errors that survive
review: a model that is not in its package order, a component referenced from a
system that does not exist, a missing 'within' clause.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "modelica" / "MaliEnergy"


def models() -> list[Path]:
    return [p for p in ROOT.rglob("*.mo") if p.name != "package.mo"]


def test_library_exists():
    assert (ROOT / "package.mo").exists()
    assert len(models()) >= 8


@pytest.mark.parametrize("path", models(), ids=lambda p: p.stem)
def test_each_model_declares_its_package(path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("within MaliEnergy"), f"{path} has no within clause"


@pytest.mark.parametrize("path", models(), ids=lambda p: p.stem)
def test_each_model_is_closed_and_named_after_its_file(path):
    text = path.read_text(encoding="utf-8")
    match = re.search(r"^\s*(model|package)\s+(\w+)", text, re.MULTILINE)
    assert match, f"{path} declares no model"
    name = match.group(2)
    assert name == path.stem, f"{path} declares {name}"
    assert re.search(rf"end\s+{name}\s*;", text), f"{path} is not closed"


@pytest.mark.parametrize("path", models(), ids=lambda p: p.stem)
def test_each_model_is_listed_in_its_package_order(path):
    order = path.parent / "package.order"
    if not order.exists():
        pytest.skip("no package.order in this folder")
    assert path.stem in order.read_text().split()


def test_components_referenced_by_systems_exist():
    available = {p.stem for p in (ROOT / "Components").glob("*.mo")}
    for path in (ROOT / "Systems").glob("*.mo"):
        if path.name == "package.mo":
            continue
        text = path.read_text(encoding="utf-8")
        for referenced in re.findall(r"Components\.(\w+)", text):
            assert referenced in available, f"{path.stem} uses missing {referenced}"


def test_studies_extend_a_system_that_exists():
    systems = {p.stem for p in (ROOT / "Systems").glob("*.mo")}
    for path in (ROOT / "Studies").glob("*.mo"):
        if path.name == "package.mo":
            continue
        text = path.read_text(encoding="utf-8")
        for referenced in re.findall(r"MaliEnergy\.Systems\.(\w+)", text):
            assert referenced in systems, f"{path.stem} extends missing {referenced}"


def test_every_parameter_carries_a_description():
    """An undocumented parameter is a parameter nobody can check.

    Declarations are split on the semicolon rather than the newline, because a
    Modelica parameter routinely carries its description on the following line.
    """
    for path in models():
        text = path.read_text(encoding="utf-8")
        for statement in text.split(";"):
            statement = statement.strip()
            if not statement.startswith("parameter "):
                continue
            assert '"' in statement, f"{path.stem}: {statement.splitlines()[0]}"

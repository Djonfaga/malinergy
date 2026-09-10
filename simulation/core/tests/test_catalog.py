"""The catalogue must load, validate and refuse malformed input."""

import pytest

from mali_energy.config import StudyConfig
from mali_energy.grid import load_catalog
from mali_energy.grid.validation import validate


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def test_catalog_loads_expected_scale(catalog):
    assert len(catalog.buses) > 25
    assert len(catalog.lines) > 20
    assert len(catalog.generators) > 10
    assert len(catalog.loads) > 10


def test_every_record_carries_provenance(catalog):
    groups = [
        catalog.buses.values(),
        catalog.lines.values(),
        catalog.transformers.values(),
        catalog.generators.values(),
        catalog.loads.values(),
    ]
    for group in groups:
        for item in group:
            assert item.source, f"{item.id} has no source"
            assert item.confidence in {"measured", "reported", "derived", "estimated"}


def test_line_lengths_are_plausible(catalog):
    for line in catalog.lines.values():
        assert 1.0 < line.length_km < 400.0, f"{line.id}: {line.length_km} km"


def test_omvs_plants_carry_a_partial_malian_share(catalog):
    for plant_id in ("GEN_MANANTALI", "GEN_GOUINA", "GEN_FELOU"):
        assert catalog.generators[plant_id].mali_share < 1.0
    assert catalog.generators["GEN_SELINGUE"].mali_share == 1.0


def test_inverter_plants_declare_no_inertia(catalog):
    for generator in catalog.generators.values():
        if generator.is_inverter_based:
            assert generator.inertia_h_s == 0.0
            assert not generator.provides_inertia


def test_validation_reports_no_errors(catalog):
    report = validate(catalog, StudyConfig())
    assert report.ok, report.render()


def test_unknown_bus_reference_is_rejected(tmp_path):
    import shutil

    from mali_energy.config import REFERENCE_DIR
    from mali_energy.grid.catalog import CatalogError

    shutil.copytree(REFERENCE_DIR, tmp_path / "reference")
    lines = tmp_path / "reference" / "lines.csv"
    text = lines.read_text().replace("BUS_KITA_225", "BUS_DOES_NOT_EXIST", 1)
    lines.write_text(text)

    with pytest.raises(CatalogError, match="unknown bus"):
        load_catalog(tmp_path / "reference")

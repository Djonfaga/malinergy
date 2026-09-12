"""The DGS export is the only thing that crosses into PowerFactory, so it is
checked more carefully than anything else in this branch."""

import pytest

from mali_energy.config import BUILD_DIR
from mali_energy.exchange import load_exchange
from mali_powerfactory.dgs import DgsExport
from mali_powerfactory.verify import parse, verify


@pytest.fixture(scope="module")
def exchange():
    path = BUILD_DIR / "mali_case.json"
    if not path.exists():
        pytest.skip("run 'mali-energy build' in simulation/core first")
    return load_exchange(path)


@pytest.fixture(scope="module")
def export(exchange):
    return DgsExport(exchange).build("dry_peak")


def test_every_case_exports_and_verifies(exchange):
    for case_name in exchange["cases"]:
        report = verify(DgsExport(exchange).build(case_name))
        assert report.ok, f"{case_name}:\n{report.render()}"


def test_file_starts_with_a_version_header(export):
    lines = export.render().splitlines()
    assert any("DGS Version" in line for line in lines[:5])
    assert any(line.startswith("$$General") for line in lines)


def test_identifiers_are_unique(export):
    tables = parse(export.render())
    identifiers = [row["ID"] for rows in tables.values() for row in rows]
    assert len(identifiers) == len(set(identifiers))


def test_every_row_matches_its_header_width(export):
    tables = parse(export.render())
    for name, rows in tables.items():
        for row in rows:
            assert row["_fields"] == row["_expected"], f"{name} has a ragged row"


def test_dispatch_is_per_machine_not_per_station(exchange, export):
    """PowerFactory multiplies pgini by ngnum. Exporting the station total
    against a machine count of five gives a load flow with five times the
    generation, which converges and is nonsense."""
    tables = parse(export.render())
    case = exchange["cases"]["dry_peak"]
    generators = {g["id"]: g for g in exchange["network"]["generators"]}
    for row in tables["ElmSym"]:
        if row["outserv"] != "0":
            continue
        record = generators[row["loc_name"]]
        setpoint = case["generators"][row["loc_name"]]
        units = max(record["units"], 1)
        assert float(row["ngnum"]) == units
        assert float(row["pgini"]) == pytest.approx(setpoint["p_mw"] / units, rel=1e-4)


def test_exactly_one_slack_node(export):
    tables = parse(export.render())
    slacks = [row for row in tables["ElmXnet"] if row["bustp"] == "SL"]
    assert len(slacks) == 1


def test_neighbours_are_voltage_controlled_not_swing(export):
    """An infinite bus at Ferkessedougou would let Cote d'Ivoire absorb the
    Malian deficit, and the study would describe a system that never sheds."""
    tables = parse(export.render())
    neighbours = [row for row in tables["ElmXnet"] if not row["loc_name"].startswith("SLACK_")]
    assert neighbours
    assert all(row["bustp"] == "PV" for row in neighbours)


def test_solar_plants_export_as_static_generators(exchange, export):
    """Only the plants in the dispatch. A scenario asset that is out of
    service, such as the Safo project, is not part of an operating point and
    must not appear in its export."""
    tables = parse(export.render())
    static = {row["loc_name"] for row in tables.get("ElmGenstat", [])}
    synchronous = {row["loc_name"] for row in tables.get("ElmSym", [])}
    case = exchange["cases"]["dry_peak"]
    records = {g["id"]: g for g in exchange["network"]["generators"]}
    dispatched_solar = {
        gen_id for gen_id in case["generators"] if records[gen_id]["technology"] == "solar"
    }
    assert dispatched_solar
    for gen_id in dispatched_solar:
        assert gen_id in static
        assert gen_id not in synchronous

    out_of_service = {
        g["id"] for g in exchange["network"]["generators"]
        if g["technology"] == "solar" and not g["in_service"]
    }
    assert not (out_of_service & static)


def test_line_types_are_shared_between_identical_corridors(exchange, export):
    """A project with one type per line is a project nobody can maintain."""
    tables = parse(export.render())
    assert len(tables["TypLne"]) < len(tables["ElmLne"])


def test_impedances_survive_the_export(exchange, export):
    tables = parse(export.render())
    types = {row["loc_name"]: row for row in tables["TypLne"]}
    for line in exchange["network"]["lines"]:
        key = f"{line['conductor']}_{line['tower']}_{line['vn_kv']:.0f}".replace(" ", "_")
        record = types[key]
        assert float(record["rline"]) == pytest.approx(line["r_ohm_per_km"], abs=1e-4)
        assert float(record["xline"]) == pytest.approx(line["x_ohm_per_km"], abs=1e-4)
        assert float(record["cline"]) == pytest.approx(line["c_nf_per_km"], abs=1e-4)


def test_zero_sequence_data_is_carried(export):
    tables = parse(export.render())
    for row in tables["TypLne"]:
        assert float(row["xline0"]) > float(row["xline"])


def test_verification_catches_a_corrupted_export(exchange):
    """The verifier has to fail on something, or it proves nothing."""
    export = DgsExport(exchange).build("dry_peak")
    export.tables["ElmTerm"].rows = export.tables["ElmTerm"].rows[:-3]
    report = verify(export)
    assert not report.ok
    assert any(check == "buses" for _, check, _ in report.errors)


def test_verification_catches_a_broken_reference(exchange):
    export = DgsExport(exchange).build("dry_peak")
    export.tables["ElmLne"].rows[0][3] = 999999
    report = verify(export)
    assert not report.ok
    assert any(check == "references" for _, check, _ in report.errors)

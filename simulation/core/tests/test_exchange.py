"""The exchange file is the contract between the five tools."""

import json

import pytest

from mali_energy.config import StudyConfig
from mali_energy.exchange import OPERATING_POINTS, build_all_cases, export_exchange, load_exchange
from mali_energy.grid import load_catalog


@pytest.fixture(scope="module")
def cases():
    return build_all_cases(catalog=load_catalog(), config=StudyConfig())


def test_all_operating_points_are_built(cases):
    assert set(cases) == set(OPERATING_POINTS)


def test_dry_season_hydro_is_below_wet_season(cases):
    assert cases["dry_peak"].balance["hydro_mw"] < cases["wet_peak"].balance["hydro_mw"]


def test_dry_season_peak_is_the_stressed_case(cases):
    dry = cases["dry_peak"].balance
    wet = cases["wet_peak"].balance
    assert dry["unserved_mw"] >= wet["unserved_mw"]


def test_solar_only_appears_during_the_day(cases):
    assert cases["solar_noon"].balance["solar_mw"] > 0
    assert cases["night_min"].balance["solar_mw"] == 0
    assert cases["dry_peak"].balance["solar_mw"] == 0


def test_night_demand_is_the_lowest(cases):
    demands = {name: case.total_demand_mw for name, case in cases.items()}
    assert min(demands, key=demands.get) == "night_min"


def test_generation_covers_demand_and_losses(cases):
    for name, case in cases.items():
        b = case.balance
        supplied = b["hydro_mw"] + b["solar_mw"] + b["thermal_mw"] + b["storage_mw"] + b["net_import_mw"]
        assert supplied + b["unserved_mw"] == pytest.approx(
            b["generation_required_mw"] + b["surplus_mw"], abs=1.0
        ), name


def test_hydro_never_exceeds_the_malian_share(cases):
    catalog = load_catalog()
    for case in cases.values():
        for gid, setpoint in case.generators.items():
            generator = catalog.generators[gid]
            if generator.technology == "hydro":
                assert setpoint.p_mw <= generator.capacity_mw * generator.mali_share + 1e-6


def test_exchange_roundtrip(tmp_path):
    path = export_exchange(tmp_path / "case.json")
    payload = load_exchange(path)
    assert payload["format"].startswith("mali-energy-exchange/")
    assert payload["network"]["buses"]
    assert set(payload["cases"]) == set(OPERATING_POINTS)
    assert payload["data_card"]["records"] > 50


def test_exchange_rejects_a_foreign_file(tmp_path):
    path = tmp_path / "other.json"
    path.write_text(json.dumps({"format": "something-else"}))
    with pytest.raises(ValueError, match="not a Mali energy exchange file"):
        load_exchange(path)

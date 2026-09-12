"""The translation into pandapower must preserve the exchange file exactly."""

import pytest

from mali_energy.config import BUILD_DIR
from mali_energy.exchange import load_exchange
from mali_pandapower.builder import VOLTAGE_CONTROL_MIN_MVA, build


@pytest.fixture(scope="module")
def exchange():
    path = BUILD_DIR / "mali_case.json"
    if not path.exists():
        pytest.skip("run 'mali-energy build' in simulation/core first")
    return load_exchange(path)


def test_every_in_service_bus_is_translated(exchange):
    result = build(exchange, "dry_peak")
    expected = sum(1 for b in exchange["network"]["buses"] if b["in_service"])
    assert len(result.net.bus) == expected


def test_line_impedances_are_copied_not_recomputed(exchange):
    result = build(exchange, "dry_peak")
    for line in exchange["network"]["lines"]:
        if line["id"] not in result.line_index:
            continue
        index = result.line_index[line["id"]]
        assert result.net.line.at[index, "r_ohm_per_km"] == pytest.approx(line["r_ohm_per_km"])
        assert result.net.line.at[index, "x_ohm_per_km"] == pytest.approx(line["x_ohm_per_km"])
        assert result.net.line.at[index, "length_km"] == pytest.approx(line["length_km"])
        assert result.net.line.at[index, "parallel"] == line["circuits"]


def test_demand_matches_the_case(exchange):
    result = build(exchange, "dry_peak")
    case = exchange["cases"]["dry_peak"]
    case_total = sum(load["p_mw"] for load in case["loads"].values())
    assert float(result.net.load.p_mw.sum()) == pytest.approx(case_total, rel=1e-9)


def test_small_machines_do_not_regulate_voltage(exchange):
    result = build(exchange, "dry_peak")
    generators = {g["id"]: g for g in exchange["network"]["generators"]}
    for gen_id in result.gen_index:
        if gen_id in generators:
            assert generators[gen_id]["sn_mva"] >= VOLTAGE_CONTROL_MIN_MVA


def test_solar_plants_are_static_generators(exchange):
    result = build(exchange, "solar_noon")
    for gen in exchange["network"]["generators"]:
        if gen["technology"] == "solar" and gen["in_service"]:
            assert gen["id"] in result.sgen_index
            assert gen["id"] not in result.gen_index


def test_capacitor_banks_are_negative_reactive_loads(exchange):
    result = build(exchange, "dry_peak")
    assert len(result.net.shunt) > 0
    assert (result.net.shunt.q_mvar < 0).all()
    for shunt in exchange["network"]["shunts"]:
        if shunt["id"] in result.shunt_index:
            index = result.shunt_index[shunt["id"]]
            assert result.net.shunt.at[index, "q_mvar"] == pytest.approx(
                -shunt["q_mvar_per_step"]
            )
            assert result.net.shunt.at[index, "max_step"] == shunt["steps"]


def test_exactly_one_slack(exchange):
    result = build(exchange, "dry_peak")
    assert len(result.net.ext_grid) == 1


def test_transformer_vector_groups_keep_their_neutral(exchange):
    result = build(exchange, "dry_peak")
    groups = set(result.net.trafo.vector_group.unique())
    assert groups <= {"YNd", "YNyn", "Dyn", "Yd", "Yy"}
    assert any("N" in g for g in groups)

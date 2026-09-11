"""Checks on the Bamako water model."""

import pytest

from mali_pandapipes.coupling import evaluate_storage_flexibility, pumping_load_by_bus
from mali_pandapipes.water.catalog import WaterCatalogError, load_water_catalog
from mali_pandapipes.water.studies import pump_outage_screening, run_case


@pytest.fixture(scope="module")
def catalog():
    return load_water_catalog()


def test_catalog_scale_matches_bamako(catalog):
    assert 2_000_000 < catalog.population_served < 3_500_000
    # SOMAGEP production for Bamako is of the order of a quarter of a million
    # cubic metres a day once Kabala phase one is counted.
    assert 180_000 < catalog.total_production_m3_day < 400_000


def test_every_record_carries_provenance(catalog):
    for group in (catalog.nodes, catalog.pipes, catalog.pumps, catalog.demands):
        for item in group.values():
            assert item.source and item.confidence


def test_average_case_serves_every_district(catalog):
    result = run_case("average", catalog=catalog)
    assert result.converged
    assert result.summary["deficient_nodes"] == 0
    assert result.summary["isolated_nodes"] == 0


def test_specific_energy_is_plausible(catalog):
    result = run_case("average", catalog=catalog)
    # Surface water with 125 m of lift to Point G: 0.3 to 0.7 kWh per cubic metre.
    assert 0.30 < result.summary["specific_energy_kwh_m3"] < 0.70


def test_service_pressures_are_within_design_range(catalog):
    result = run_case("average", catalog=catalog)
    served = result.junctions[result.junctions["type"] == "demand"]
    assert served["head_m"].min() > 15.0
    # Above about 80 m a distribution network needs pressure reduction, which
    # is exactly why the model has a reducing station below Point G.
    assert served["head_m"].max() < 90.0


def test_mains_are_not_overloaded(catalog):
    result = run_case("average", catalog=catalog)
    assert result.summary["max_velocity_m_s"] < 2.5


def test_direct_pumped_left_bank_fails_at_peak(catalog):
    """Magnambougou and Sotuba have no service reservoir, so the peak hour has
    to come straight from the pumps. This is the finding, not a defect."""
    result = run_case("peak", catalog=catalog)
    assert result.converged
    failing = {
        row["node"]
        for _, row in result.junctions.iterrows()
        if row["type"] == "demand" and row["p_bar"] < 2.0
    }
    assert "WN_SOTUBA_DEM" in failing or "WN_MAGNAM_DEM" in failing


def test_outage_of_the_main_plant_is_the_worst(catalog):
    frame = pump_outage_screening(catalog)
    worst = frame.iloc[0]
    assert worst["pump"] in {"PU_KABALA_HL", "PU_CENTRE_POINTG"}
    assert worst["population_affected"] > 1_000_000


def test_isolated_nodes_are_not_counted_as_served(catalog):
    """A node cut off from every source returns NaN pressure. Comparing NaN
    against a threshold is false, so without explicit handling the nodes with
    no water at all would be reported as secure."""
    result = run_case("average", catalog=catalog, pumps_out_of_service=("PU_CENTRE_POINTG",))
    assert result.summary["isolated_nodes"] > 0


def test_pumping_load_lands_on_named_electrical_buses(catalog):
    loads = pumping_load_by_bus(catalog)
    assert loads
    assert all(bus.startswith("BUS_") for bus in loads)
    assert 2.0 < sum(loads.values()) < 12.0


def test_storage_removes_load_from_the_evening_peak(catalog):
    result = evaluate_storage_flexibility(catalog)
    assert result.summary["reduction_at_system_peak_kw"] > 0
    assert (
        result.summary["storage_scheduled_peak_kw"]
        < result.summary["load_following_peak_kw"]
    )


def test_parallel_active_element_is_rejected(tmp_path, catalog):
    import shutil

    from mali_pandapipes.water.catalog import REFERENCE_DIR

    shutil.copytree(REFERENCE_DIR, tmp_path / "reference")
    pipes = tmp_path / "reference" / "water_pipes.csv"
    text = pipes.read_text().replace("WN_POINTG_PUMP,WN_POINTG_RES", "WN_CENTRE_JCT,WN_POINTG_PUMP")
    pipes.write_text(text)
    with pytest.raises(WaterCatalogError, match="parallel with a pipe"):
        load_water_catalog(tmp_path / "reference")

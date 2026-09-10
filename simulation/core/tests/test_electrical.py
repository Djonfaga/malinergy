"""Line parameter derivation is checked against textbook values.

If these break, every load flow in every tool is wrong in the same way, so
they are the first tests to run.
"""

import math

import pytest

from mali_energy.grid import electrical


def test_225kv_line_matches_textbook_values():
    p = electrical.line_parameters("ASTER 570", "225kV-single-flat", ambient_c=40.0)
    # A 225 kV single-circuit line with a large AAAC conductor sits close to
    # 0.4 ohm/km of reactance and 9 nF/km of capacitance.
    assert 0.38 < p.x_ohm_km < 0.45
    assert 8.0 < p.c_nf_km < 10.0
    assert 2.5 < p.b_us_km < 3.2
    assert 0.06 < p.r_ohm_km < 0.09


def test_surge_impedance_and_natural_load_are_plausible():
    p = electrical.line_parameters("ASTER 570", "225kV-single-flat")
    assert 330 < p.surge_impedance_ohm < 420
    # Surge impedance loading of a 225 kV line is of the order of 130 MW.
    assert 110 < p.natural_load_mw(225.0) < 160


def test_zero_sequence_exceeds_positive_sequence():
    p = electrical.line_parameters("ASTER 570", "225kV-single-flat")
    assert p.x0_ohm_km > 2.0 * p.x_ohm_km
    assert p.r0_ohm_km > p.r_ohm_km


def test_resistance_rises_with_temperature():
    conductor = electrical.CONDUCTORS["ASTER 570"]
    cold = conductor.resistance_ohm_km(20.0)
    hot = conductor.resistance_ohm_km(75.0)
    assert hot > cold
    # 0.36 %/K over 55 K is close to a 20 % increase.
    assert 1.15 < hot / cold < 1.25


def test_sahel_ambient_reduces_ampacity():
    conductor = electrical.CONDUCTORS["ASTER 570"]
    mild = electrical.ampacity_derating(conductor, 25.0)
    hot = electrical.ampacity_derating(conductor, 45.0)
    assert hot < mild
    # Losing 10-25 % of the rating between a mild and a Malian hot afternoon.
    assert 0.75 < hot / mild < 0.95


def test_bundling_reduces_reactance():
    single = electrical.TOWERS["225kV-single-flat"]
    bundled = electrical.TowerGeometry(
        "test-bundle", 225.0, single.phase_positions, bundle=2, bundle_spacing_m=0.4
    )
    electrical.TOWERS["test-bundle"] = bundled
    try:
        a = electrical.line_parameters("ASTER 570", "225kV-single-flat")
        b = electrical.line_parameters("ASTER 570", "test-bundle")
        assert b.x_ohm_km < a.x_ohm_km
        assert b.r_ohm_km == pytest.approx(a.r_ohm_km / 2.0)
    finally:
        del electrical.TOWERS["test-bundle"]


def test_transformer_impedance_split():
    z = electrical.transformer_impedance(63.0, 225.0, 33.0, vk_percent=13.0, vkr_percent=0.4)
    assert z["x_ohm"] < z["z_ohm"]
    assert math.isclose(
        math.hypot(z["r_ohm"], z["x_ohm"]), z["z_ohm"], rel_tol=1e-9
    )
    assert z["ratio"] == pytest.approx(225.0 / 33.0)

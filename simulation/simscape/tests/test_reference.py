"""The averaged converter model is checked against known converter behaviour."""

import math

import pytest

from mali_simscape.reference import InverterDesign, simulate_inverter


def _design(scr: float, *, voltage_kv: float = 33.0, rating_mva: float = 52.6, **kwargs):
    z = voltage_kv**2 / (scr * rating_mva)
    x_over_r = 6.0
    r = z / math.hypot(1.0, x_over_r)
    inductance = (r * x_over_r) / (2 * math.pi * 50.0)
    return InverterDesign(
        name=f"scr_{scr}", rating_mva=rating_mva, voltage_kv=voltage_kv,
        grid_l_h=inductance, grid_r_ohm=r, **kwargs
    )


def test_short_circuit_ratio_is_consistent_with_the_impedance():
    design = _design(5.0)
    assert design.short_circuit_ratio == pytest.approx(5.0, rel=0.02)


def test_a_strong_grid_is_stable_and_settles_quickly():
    result = simulate_inverter(_design(10.0), duration_s=1.0, p_step_pu=0.1, p_step_time_s=0.4)
    assert result.metrics["stable"]
    assert result.metrics["settling_time_ms"] < 20.0


def test_angle_error_grows_as_the_grid_weakens():
    """The converter has to push harder against a weaker network to deliver the
    same power, and the angle across the impedance is the measure of it."""
    strong = simulate_inverter(_design(10.0), duration_s=0.8).metrics
    weak = simulate_inverter(_design(2.0), duration_s=0.8).metrics
    assert weak["max_angle_error_deg"] > strong["max_angle_error_deg"]


def test_synchronism_is_lost_below_a_short_circuit_ratio_of_about_one():
    """The model has to reproduce the known limit before any Malian conclusion
    is drawn from it."""
    assert simulate_inverter(_design(1.5), duration_s=1.0).metrics["stable"]
    assert simulate_inverter(_design(1.0), duration_s=1.0).metrics["diverged"]


def test_power_transfer_limit_appears_on_a_very_weak_grid():
    """Below roughly a ratio of two the plant can no longer deliver its
    setpoint, whatever the controller does."""
    result = simulate_inverter(_design(1.5), duration_s=1.0)
    assert result.metrics["final_p_pu"] < 0.95 * result.design.p_setpoint_pu / 0.9


def test_current_limit_holds_during_a_voltage_dip():
    result = simulate_inverter(
        _design(5.0), duration_s=1.2, grid_voltage_step_pu=-0.4, grid_step_time_s=0.5
    )
    assert result.metrics["max_current_pu"] <= 1.25
    assert result.metrics["stable"]


def test_controller_decouples_with_the_filter_not_the_network():
    """Decoupling with the total inductance cancels the network impedance
    exactly and makes every connection look strong. If that regression ever
    returns, a very weak grid stops diverging and this test fails."""
    assert simulate_inverter(_design(1.0), duration_s=1.0).metrics["diverged"]


def test_control_delay_is_represented():
    design = _design(5.0)
    assert design.control_delay_s > 0

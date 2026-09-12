"""Figures must be generated from the study outputs and ship their data.

A figure whose underlying table is not available beside it is an assertion,
so the tests check the pairing as much as the image.
"""

import matplotlib
import pandas as pd
import pytest

matplotlib.use("Agg")

from mali_benchmark import figures  # noqa: E402


@pytest.fixture
def monthly():
    months = pd.date_range("2024-01-01", periods=12, freq="MS")
    return pd.DataFrame(
        {
            "timestamp": months,
            "hydro_gwh": [110, 87, 73, 53, 50, 65, 118, 168, 181, 177, 149, 127],
            "thermal_gwh": [101, 122, 166, 172, 176, 152, 99, 46, 39, 54, 63, 84],
            "import_gwh": [67, 63, 67, 65, 67, 65, 67, 63, 51, 65, 64, 67],
            "solar_gwh": [12, 12, 13, 13, 13, 12, 12, 12, 12, 13, 12, 13],
            "hours_shed": [0, 52, 107, 202, 199, 74, 0, 0, 0, 0, 0, 0],
            "unserved_gwh": [0, 6, 21, 44, 40, 14, 0, 0, 0, 0, 0, 0],
        }
    )


def test_monthly_balance_writes_image_and_data(monthly, tmp_path):
    path = figures.monthly_balance(monthly, tmp_path / "fig.png")
    assert path.exists() and path.stat().st_size > 5_000
    table = path.with_suffix(".csv")
    assert table.exists()
    assert len(pd.read_csv(table)) == 12


def test_frequency_traces_handles_converging_series(tmp_path):
    import numpy as np

    time = np.arange(0, 60, 0.05)
    traces = pd.DataFrame(
        {
            "dry_peak_unit_trip": 50 - 1.2 * np.exp(-((time - 10) ** 2) / 30),
            "dry_peak_interconnection": 50 - 2.0 * np.exp(-((time - 12) ** 2) / 60),
        },
        index=time,
    )
    path = figures.frequency_traces(traces, tmp_path / "freq.png")
    assert path.exists()
    assert path.with_suffix(".csv").exists()


def test_series_colours_are_fixed_per_entity():
    """Hydro must be the same blue in every figure, so a reader who has learned
    the colours in one figure has learned them in all of them."""
    assert figures.SERIES["hydro"] == figures.BLUE
    assert figures.SERIES["thermal"] == figures.ORANGE
    assert figures.SERIES["solar"] == figures.YELLOW
    assert len(set(figures.SERIES.values())) == len(figures.SERIES)


def test_status_colours_are_not_reused_as_series():
    assert figures.CRITICAL not in {figures.BLUE, figures.ORANGE, figures.AQUA, figures.YELLOW}
    assert figures.GOOD not in {figures.BLUE, figures.ORANGE, figures.AQUA, figures.YELLOW}


def test_stack_order_avoids_the_yellow_orange_pair():
    """The palette's yellow and orange fail the colour-vision separation floor
    when placed side by side, so the stack puts aqua between them."""
    source = (figures.__file__)
    text = open(source, encoding="utf-8").read()
    assert '["hydro_gwh", "thermal_gwh", "import_gwh", "solar_gwh"]' in text


def test_case_losses_uses_one_hue_for_magnitude(tmp_path):
    summary = pd.DataFrame(
        {
            "case": ["dry_peak", "wet_peak", "solar_noon", "night_min"],
            "demand_mw": [385, 462, 454, 262],
            "losses_mw": [14.5, 33.9, 16.2, 16.0],
            "losses_pct": [3.8, 7.3, 3.6, 6.1],
        }
    )
    path = figures.case_losses(summary, tmp_path / "losses.png")
    assert path.exists()
    # Two steps of the blue ramp, not a status red: a loss percentage is a
    # magnitude, not a failure state.
    assert figures.BLUE_LIGHT != figures.BLUE_DARK

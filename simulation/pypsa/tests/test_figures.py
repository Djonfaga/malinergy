"""Figures: that they are produced, and that they are readable in greyscale.

A plot is the easiest place in a study to mislead by accident, so what is
tested is the part a reader cannot check: that the colours stay distinguishable
when the article is printed in black and white, and that every figure actually
gets written rather than silently skipped.
"""

from itertools import pairwise

import pytest

matplotlib = pytest.importorskip("matplotlib")

from mali_pypsa.figures import (  # noqa: E402
    CARRIER_COLOURS,
    CARRIER_ORDER,
    write_figures,
)


def test_every_figure_is_written(result, tmp_path):
    paths = write_figures(result, tmp_path)
    assert len(paths) == 5
    for path in paths:
        assert path.exists()
        assert path.stat().st_size > 5_000, f"{path.name} looks empty"


def test_every_carrier_in_the_result_has_a_colour(result):
    for carrier in result.by_carrier_gwh.index:
        assert carrier in CARRIER_COLOURS


def test_the_stacking_order_covers_every_colour():
    assert set(CARRIER_ORDER) == set(CARRIER_COLOURS)


def test_the_colours_survive_greyscale_printing():
    """Luminance has to separate, or the stack is a single grey block."""
    from matplotlib.colors import to_rgb

    def luminance(hex_colour: str) -> float:
        r, g, b = to_rgb(hex_colour)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    values = sorted(luminance(c) for c in CARRIER_COLOURS.values())
    gaps = [b - a for a, b in pairwise(values)]
    assert min(gaps) > 0.06, "two carriers are the same shade of grey"


def test_water_is_blue_and_fuel_is_grey():
    """Not decoration: a reader should not have to consult the legend twice."""
    assert CARRIER_COLOURS["hydro"] == "#0072B2"
    assert CARRIER_COLOURS["thermal"] == "#404040"

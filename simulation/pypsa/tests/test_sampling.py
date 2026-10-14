"""Interval averaging, and the invariance it buys.

The claim these tests stand behind is simple and checkable: an annual total
from this model does not depend on how finely the year was sampled. Without
it, solar energy at twelve-hourly sampling came out four fifths too high.
"""

import numpy as np
import pandas as pd
import pytest
from mali_pypsa.sampling import downsample, resolves_day, step_hours

INDEX = pd.date_range("2024-01-01", "2024-12-31 23:00", freq="h", tz="UTC")


def test_step_hours_reads_the_interval_off_the_index():
    assert step_hours(INDEX) == 1.0
    assert step_hours(INDEX[::6]) == 6.0
    assert step_hours(INDEX[:1]) == 1.0


def test_an_hourly_series_is_unchanged_by_an_hourly_index():
    series = pd.Series(np.arange(len(INDEX), dtype=float), index=INDEX)
    assert downsample(series, INDEX).equals(series)


def test_a_square_wave_averages_to_its_duty_cycle():
    """The solar case in miniature: twelve hours on, twelve off."""
    series = pd.Series((INDEX.hour >= 6) & (INDEX.hour < 18), index=INDEX).astype(float)
    daily = downsample(series, INDEX[::24])
    assert daily.min() == pytest.approx(0.5)
    assert daily.max() == pytest.approx(0.5)


def test_reading_the_instant_would_have_given_zero_or_one():
    """Stated as a test so the defect cannot come back unnoticed."""
    series = pd.Series((INDEX.hour >= 6) & (INDEX.hour < 18), index=INDEX).astype(float)
    sampled = series.reindex(INDEX[::24])
    assert set(sampled.unique()) == {0.0}
    assert downsample(series, INDEX[::24]).mean() == pytest.approx(0.5)


@pytest.mark.parametrize("step", [1, 2, 3, 4, 6, 8, 12, 24])
def test_the_mean_survives_every_sampling_interval(step):
    rng = np.random.default_rng(7)
    diurnal = 0.5 + 0.5 * np.sin(2 * np.pi * (INDEX.hour - 6) / 24)
    series = pd.Series(diurnal * rng.uniform(0.8, 1.2, len(INDEX)), index=INDEX)
    coarse = downsample(series, INDEX[::step])
    assert float(coarse.mean()) == pytest.approx(float(series.mean()), rel=0.01)


def test_the_result_has_no_holes():
    series = pd.Series(1.0, index=INDEX[: len(INDEX) // 2])
    coarse = downsample(series, INDEX[::6])
    assert coarse.index.equals(INDEX[::6])
    assert not coarse.isna().any()


def test_a_naive_target_index_is_accepted():
    """PyPSA snapshots are naive, the source series is not."""
    series = pd.Series(1.0, index=INDEX)
    naive = INDEX.tz_localize(None)[::6]
    coarse = downsample(series, naive)
    assert coarse.index.tz is None
    assert coarse.notna().all()


def test_three_hours_resolves_the_day_and_twelve_does_not():
    assert resolves_day(INDEX)
    assert resolves_day(INDEX[::3])
    assert not resolves_day(INDEX[::12])


def test_a_target_after_the_source_raises():
    """The first version of this guard only looked one way."""
    series = pd.Series(1.0, index=INDEX)
    later = pd.date_range("2025-01-01", "2025-12-31 23:00", freq="h", tz="UTC")[::6]
    with pytest.raises(ValueError, match="do not overlap"):
        downsample(series, later)


def test_a_target_before_the_source_raises_too():
    """Everything after the last snapshot lands *in* it, so it looked like a hit.

    A 2023 index against a 2024 series does not return nothing; it returns one
    flat value for the whole year, which a model will happily solve.
    """
    series = pd.Series(1.0, index=INDEX)
    earlier = pd.date_range("2023-01-01", "2023-12-31 23:00", freq="h", tz="UTC")[::6]
    with pytest.raises(ValueError, match="do not overlap"):
        downsample(series, earlier)


def test_the_ordinary_end_of_year_overhang_is_not_an_error():
    """An hourly year ends at 23:00 and its last daily snapshot covers the day."""
    series = pd.Series(1.0, index=INDEX)
    daily = INDEX[::24]
    assert downsample(series, daily).notna().all()

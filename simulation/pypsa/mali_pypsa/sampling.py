"""Putting an hourly series onto a coarser snapshot index.

A sampled year is the ordinary way to keep an optimisation tractable, and the
ordinary way to get it wrong is to *read* the series at each snapshot instead
of *averaging* it over the hours that snapshot stands for.

For demand the error is modest, because demand is smooth. For solar it is
ruinous. A twelve-hourly index sampled at midnight and noon sees a capacity
factor of zero and of nearly eighty per cent, averaging to 0.39 — against a
true annual mean near 0.22. The model would then solve cleanly and report
roughly eighty per cent more solar energy than Mali's plants can produce,
displacing fuel that in reality is burnt.

Averaging over the interval removes that bias, and makes every annual total
invariant to the sampling interval. That invariance is worth having on its own:
it is a property a reader can check, and it is tested.
"""

from __future__ import annotations

import pandas as pd

#: Coarsest sampling interval at which a snapshot still falls clearly inside
#: the day or inside the night. Beyond this the averaging above is still
#: correct for energy, but a single snapshot straddles sunrise, so a check like
#: "solar must not generate at night" has nothing to test and must say so
#: rather than fail.
DAY_RESOLVING_STEP_HOURS = 3


def resolves_day(index: pd.DatetimeIndex) -> bool:
    """Whether the index is fine enough for the diurnal checks to mean anything."""
    return step_hours(index) <= DAY_RESOLVING_STEP_HOURS


def step_hours(index: pd.DatetimeIndex) -> float:
    """Hours each snapshot stands for, read off a regular index."""
    if len(index) < 2:
        return 1.0
    return float((index[1] - index[0]).total_seconds() / 3600.0)


def downsample(series: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    """Average an hourly series over the interval each snapshot represents.

    The series is assumed to be at least as fine as the target index. Where it
    is coarser the values are interpolated onto the target, which spreads the
    series rather than conserving its mean exactly, so that direction is for
    filling a gap and not for an energy total. Where a snapshot falls outside
    the source the nearest available value is carried in, so the result has no
    holes: a hole in a capacity factor becomes an unexplained megawatt hour.

    Source timestamps before the first snapshot belong to no interval and are
    dropped. That is right when the two indices cover the same period and wrong
    when they do not, so a target that shares nothing with the source raises
    rather than returning a year of silent zeros.
    """
    if not len(index):
        return pd.Series(dtype=float, index=index)

    aligned = series.copy()
    if aligned.index.tz is not None and index.tz is None:
        aligned.index = aligned.index.tz_localize(None)
    elif aligned.index.tz is None and index.tz is not None:
        aligned.index = aligned.index.tz_localize(index.tz)

    step = step_hours(index)
    if step <= step_hours(aligned.index):
        return aligned.reindex(index).interpolate(limit_direction="both")

    # Label each hour of the source with the snapshot that covers it, then take
    # the mean per snapshot. searchsorted is used rather than resample so that
    # the windows follow the snapshot index itself and not a calendar grid.
    position = index.searchsorted(aligned.index, side="right") - 1
    inside = position >= 0
    if not inside.any():
        raise ValueError(
            "the series and the snapshot index do not overlap: the series runs "
            f"{aligned.index[0]} to {aligned.index[-1]} and the snapshots run "
            f"{index[0]} to {index[-1]}. Interpolating across that gap would "
            "invent a year of data."
        )
    dropped = int((~inside).sum())
    if dropped > 0.01 * len(aligned):
        raise ValueError(
            f"{dropped} of {len(aligned)} values fall before the first snapshot and "
            "would be dropped. The snapshot index does not start where the series "
            "does, so an energy total taken from the result would be wrong."
        )
    grouped = aligned[inside].groupby(index[position[inside]]).mean()
    return grouped.reindex(index).interpolate(limit_direction="both")

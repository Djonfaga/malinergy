"""Hourly demand model for the Malian interconnected network.

There is no published hourly load curve for Mali, so the profile is *built*
rather than downloaded, from three ingredients that are documented and can be
challenged one by one:

1. **A daily shape per customer class.** Four anchor points (night trough,
   morning shoulder, midday, evening peak) are interpolated with a periodic
   cubic spline, which reproduces the sharply evening-peaked shape of a
   West African urban feeder without inventing structure between the anchors.
2. **A weekly modulation.** Fridays and Sundays differ from working days;
   industrial feeders drop much further at the weekend than residential ones.
3. **A thermal term.** Air conditioning and fans dominate the seasonal swing:
   demand is scaled with cooling degree hours above a comfort threshold, using
   the monthly temperature normals of the load centre.

The resulting shape is then scaled so that the annual energy matches the
utility share of the national demand reported by Our World in Data. Only the
*shape* is modelled; the *level* comes from measured data.
"""

from __future__ import annotations

import calendar
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..config import REFERENCE_DIR, TIMEZONE, StudyConfig

#: Hours at which the four anchor values of a daily shape are placed.
ANCHOR_HOURS = (3.0, 9.0, 14.0, 20.0)

#: Comfort threshold above which cooling demand appears, in degrees Celsius.
COOLING_BASE_C = 26.0

#: Time constant of the building stock, in hours. Cooling load does not follow
#: the air temperature instantaneously: masonry and concrete buildings keep
#: releasing heat into the evening, which is why the Malian system peak sits
#: at 20:00 and not at 15:00 when the air is hottest. Ignoring this lag moves
#: the modelled peak to midday and quietly changes every conclusion that
#: depends on when the system is stressed.
BUILDING_TIME_CONSTANT_H = 4.0


def _load_class_table() -> pd.DataFrame:
    return pd.read_csv(REFERENCE_DIR / "load_classes.csv").set_index("customer_class")


def _load_climate_table() -> pd.DataFrame:
    return pd.read_csv(REFERENCE_DIR / "climate_normals.csv")


def class_day_shape(customer_class: str, *, resolution: int = 24) -> np.ndarray:
    """Normalised daily shape (mean 1.0) for a customer class.

    A periodic interpolation through the four anchors keeps the curve smooth
    across midnight, which a piecewise-linear shape does not.
    """
    table = _load_class_table()
    if customer_class not in table.index:
        raise KeyError(f"unknown customer class {customer_class!r}")
    row = table.loc[customer_class]
    anchors = np.array(
        [row["base_night"], row["morning_peak"], row["midday"], row["evening_peak"]],
        dtype=float,
    )

    hours = np.arange(resolution) * (24.0 / resolution)
    # Periodic interpolation: replicate the anchors either side of the day.
    anchor_hours = np.array(ANCHOR_HOURS)
    extended_hours = np.concatenate([anchor_hours - 24.0, anchor_hours, anchor_hours + 24.0])
    extended_values = np.concatenate([anchors, anchors, anchors])

    shape = np.interp(hours, extended_hours, extended_values)
    # A light circular smoothing removes the kinks the linear interpolation
    # leaves at the anchors, without displacing the peak.
    kernel = np.array([0.25, 0.5, 0.25])
    padded = np.concatenate([shape[-1:], shape, shape[:1]])
    shape = np.convolve(padded, kernel, mode="valid")
    return shape / shape.mean()


def _weekday_factor(weekday: int, weekend_factor: float) -> float:
    """Mali works a Monday-to-Friday week with a half day on Friday afternoon."""
    if weekday == 4:                       # Friday
        return 1.0 - (1.0 - weekend_factor) * 0.35
    if weekday == 5:                       # Saturday
        return 1.0 - (1.0 - weekend_factor) * 0.65
    if weekday == 6:                       # Sunday
        return weekend_factor
    return 1.0


@dataclass
class DemandModel:
    """Builds hourly demand for one load centre or for the whole system."""

    year: int
    customer_class: str = "urban_mixed"
    station: str = "Bamako"
    config: StudyConfig | None = None

    def __post_init__(self) -> None:
        self.config = self.config or StudyConfig(year=self.year)
        classes = _load_class_table()
        if self.customer_class not in classes.index:
            raise KeyError(f"unknown customer class {self.customer_class!r}")
        self._class_row = classes.loc[self.customer_class]
        climate = _load_climate_table()
        station_rows = climate[climate["station"] == self.station]
        if station_rows.empty:
            station_rows = climate[climate["station"] == "Bamako"]
        self._climate = station_rows.set_index("month")

    # -- components --------------------------------------------------------
    def index(self) -> pd.DatetimeIndex:
        """Hourly index over the whole year, in Malian local time (UTC+0)."""
        return pd.date_range(
            f"{self.year}-01-01 00:00",
            f"{self.year}-12-31 23:00",
            freq="h",
            tz=TIMEZONE,
        )

    def temperature(self, index: pd.DatetimeIndex | None = None) -> pd.Series:
        """Hourly air temperature from monthly mean and maximum normals.

        The diurnal cycle is a sine peaking at 15:00 local time, which matches
        the observed lag of the Sahelian daily maximum.
        """
        index = self.index() if index is None else index
        months = index.month
        mean = self._climate.loc[months, "temp_mean_c"].to_numpy()
        maximum = self._climate.loc[months, "temp_max_c"].to_numpy()
        amplitude = (maximum - mean)
        phase = 2 * math.pi * (index.hour.to_numpy() - 15.0) / 24.0
        return pd.Series(mean + amplitude * np.cos(phase), index=index, name="temp_air_c")

    def effective_temperature(self, index: pd.DatetimeIndex | None = None) -> pd.Series:
        """Air temperature filtered through the thermal mass of the buildings.

        An exponentially weighted mean with a four hour time constant, applied
        forward in time so that the response lags the forcing.
        """
        index = self.index() if index is None else index
        temperature = self.temperature(index)
        alpha = 1.0 - math.exp(-1.0 / BUILDING_TIME_CONSTANT_H)
        return temperature.ewm(alpha=alpha, adjust=False).mean().rename("temp_effective_c")

    def cooling_factor(self, index: pd.DatetimeIndex | None = None) -> pd.Series:
        """Multiplier capturing air conditioning and fan load.

        Split deliberately into two terms so each can be argued with
        separately: a seasonal term driven by the daily mean effective
        temperature, which is what makes April the critical month, and a
        smaller intraday term driven by the departure from that daily mean.
        """
        index = self.index() if index is None else index
        effective = self.effective_temperature(index)
        sensitivity = float(self._class_row["cooling_sensitivity"])

        daily_mean = effective.groupby(effective.index.date).transform("mean")
        seasonal_degrees = (daily_mean - COOLING_BASE_C).clip(lower=0.0)
        intraday_degrees = (effective - daily_mean).clip(lower=0.0)

        raw = (
            1.0
            + sensitivity * seasonal_degrees / 10.0
            + 0.35 * sensitivity * intraday_degrees / 10.0
        )
        # Normalise so the annual mean multiplier is 1.0: the shape is
        # modelled, the annual level stays with the measured energy.
        return raw / raw.mean()

    def shape(self, index: pd.DatetimeIndex | None = None) -> pd.Series:
        """Normalised hourly demand shape with a mean of 1.0."""
        index = self.index() if index is None else index
        day_shape = class_day_shape(self.customer_class)
        hourly = day_shape[index.hour.to_numpy()]
        weekend = float(self._class_row["weekend_factor"])
        weekly = np.array([_weekday_factor(int(d), weekend) for d in index.dayofweek])
        cooling = self.cooling_factor(index).to_numpy()
        combined = hourly * weekly * cooling
        return pd.Series(combined / combined.mean(), index=index, name="shape")

    def series(self, annual_energy_gwh: float) -> pd.Series:
        """Hourly demand in MW whose annual energy equals ``annual_energy_gwh``."""
        index = self.index()
        shape = self.shape(index)
        hours = len(index)
        average_mw = annual_energy_gwh * 1000.0 / hours
        return (shape * average_mw).rename("p_mw")

    # -- diagnostics -------------------------------------------------------
    def statistics(self, annual_energy_gwh: float) -> dict[str, float]:
        series = self.series(annual_energy_gwh)
        peak = float(series.max())
        average = float(series.mean())
        return {
            "peak_mw": peak,
            "average_mw": average,
            "minimum_mw": float(series.min()),
            "load_factor": average / peak if peak else 0.0,
            "peak_hour": int(series.idxmax().hour),
            "peak_month": int(series.idxmax().month),
            "annual_energy_gwh": float(series.sum() / 1000.0),
        }


def leap_hours(year: int) -> int:
    return 8784 if calendar.isleap(year) else 8760

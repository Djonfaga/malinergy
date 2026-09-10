"""Photovoltaic plant production model.

The plant model is deliberately explicit about the two effects that dominate
PV yield in the Sahel and are often left out of desk studies:

* **Cell temperature.** Ambient air at 40 degC with 1000 W/m2 puts a
  free-standing module near 65-70 degC, which costs roughly 15 % of the
  nameplate power at -0.35 %/K. Ignoring it overstates the midday output.
* **Soiling.** Harmattan dust between November and March produces losses that
  reach 10-20 % between cleanings. A monthly soiling profile is applied and
  reported separately so its weight in the result is visible.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import pvlib

from .resource import IrradianceResult, irradiance

#: Monthly soiling loss fraction, driven by the harmattan dust season.
SOILING_MONTHLY = {
    1: 0.11, 2: 0.13, 3: 0.14, 4: 0.10, 5: 0.06, 6: 0.03,
    7: 0.02, 8: 0.02, 9: 0.02, 10: 0.04, 11: 0.07, 12: 0.09,
}


@dataclass
class PlantDesign:
    """Design parameters of a utility-scale plant."""

    name: str
    dc_capacity_mw: float
    ac_capacity_mw: float
    latitude: float
    longitude: float
    tilt_deg: float | None = None            # None -> latitude tilt
    azimuth_deg: float = 180.0               # 180 = due south
    tracking: bool = False
    temperature_coefficient_per_k: float = -0.0035
    noct_c: float = 45.0
    dc_losses: float = 0.06                  # wiring, mismatch, diodes
    inverter_efficiency: float = 0.98
    availability: float = 0.98
    apply_soiling: bool = True
    station: str = "Bamako"

    @property
    def dc_ac_ratio(self) -> float:
        return self.dc_capacity_mw / self.ac_capacity_mw if self.ac_capacity_mw else 1.0

    @property
    def effective_tilt(self) -> float:
        return self.tilt_deg if self.tilt_deg is not None else abs(self.latitude)


@dataclass
class PlantResult:
    design: PlantDesign
    ac_mw: pd.Series
    resource: IrradianceResult
    diagnostics: dict = field(default_factory=dict)

    @property
    def annual_energy_gwh(self) -> float:
        return float(self.ac_mw.sum() / 1000.0)

    @property
    def capacity_factor(self) -> float:
        hours = len(self.ac_mw)
        rated = self.design.ac_capacity_mw * hours
        return float(self.ac_mw.sum() / rated) if rated else 0.0

    @property
    def specific_yield_kwh_kwp(self) -> float:
        dc_kw = self.design.dc_capacity_mw * 1000.0
        return float(self.ac_mw.sum() * 1000.0 / dc_kw) if dc_kw else 0.0


def plane_of_array(design: PlantDesign, resource: IrradianceResult) -> pd.Series:
    """Irradiance in the plane of the array, W/m2."""
    data = resource.data
    if resource.provider == "pvgis" and "poa_global" in data:
        return data["poa_global"]

    location = pvlib.location.Location(design.latitude, design.longitude, tz=str(data.index.tz))
    solar_position = location.get_solarposition(data.index)

    if design.tracking:
        tracker = pvlib.tracking.singleaxis(
            apparent_zenith=solar_position["apparent_zenith"],
            apparent_azimuth=solar_position["azimuth"],
            axis_tilt=0.0,
            axis_azimuth=180.0,
            max_angle=55.0,
            backtrack=True,
            gcr=0.35,
        )
        surface_tilt = tracker["surface_tilt"].fillna(0.0)
        surface_azimuth = tracker["surface_azimuth"].fillna(180.0)
    else:
        surface_tilt = design.effective_tilt
        surface_azimuth = design.azimuth_deg

    dni_extra = pvlib.irradiance.get_extra_radiation(data.index)
    total = pvlib.irradiance.get_total_irradiance(
        surface_tilt=surface_tilt,
        surface_azimuth=surface_azimuth,
        solar_zenith=solar_position["apparent_zenith"],
        solar_azimuth=solar_position["azimuth"],
        dni=data["dni"].fillna(0.0),
        ghi=data["ghi"].fillna(0.0),
        dhi=data["dhi"].fillna(0.0),
        dni_extra=dni_extra,
        model="haydavies",
        albedo=0.25,                     # bare Sahelian soil
    )
    return total["poa_global"].fillna(0.0)


def plant_output(
    design: PlantDesign,
    year: int,
    *,
    resource: IrradianceResult | None = None,
    allow_network: bool = False,
) -> PlantResult:
    """Hourly AC output of one plant, in MW."""
    resource = resource or irradiance(
        design.latitude,
        design.longitude,
        year,
        station=design.station,
        allow_network=allow_network,
    )
    poa = plane_of_array(design, resource)
    temp_air = resource.data["temp_air"]
    wind = resource.data.get("wind_speed", pd.Series(2.5, index=poa.index))

    # Cell temperature: Faiman model, parameters for open-rack glass-glass
    # modules, which is what utility plants in Mali use.
    cell_temp = pvlib.temperature.faiman(poa, temp_air, wind, u0=25.0, u1=6.84)

    dc_ratio = poa / 1000.0
    thermal = 1.0 + design.temperature_coefficient_per_k * (cell_temp - 25.0)
    dc_mw = design.dc_capacity_mw * dc_ratio * thermal * (1.0 - design.dc_losses)

    if design.apply_soiling:
        soiling = pd.Series(
            [SOILING_MONTHLY[m] for m in poa.index.month], index=poa.index
        )
        dc_before_soiling = dc_mw.copy()
        dc_mw = dc_mw * (1.0 - soiling)
    else:
        dc_before_soiling = dc_mw

    ac_mw = (dc_mw * design.inverter_efficiency * design.availability).clip(
        lower=0.0, upper=design.ac_capacity_mw
    )

    clipped_mwh = float((dc_mw * design.inverter_efficiency - ac_mw).clip(lower=0.0).sum())
    soiling_mwh = float(
        ((dc_before_soiling - dc_mw) * design.inverter_efficiency).clip(lower=0.0).sum()
    )
    diagnostics = {
        "resource": resource.summary(),
        "poa_annual_kwh_m2": round(float(poa.sum() / 1000.0), 1),
        "mean_cell_temp_c": round(float(cell_temp[poa > 50].mean()), 1),
        "thermal_loss_pct": round(
            float((1 - thermal[poa > 50]).mean() * 100.0), 2
        ),
        "soiling_loss_gwh": round(soiling_mwh / 1000.0, 3),
        "inverter_clipping_gwh": round(clipped_mwh / 1000.0, 3),
        "dc_ac_ratio": round(design.dc_ac_ratio, 3),
    }
    return PlantResult(design=design, ac_mw=ac_mw.rename(design.name), resource=resource, diagnostics=diagnostics)


def portfolio_output(
    designs: list[PlantDesign], year: int, *, allow_network: bool = False
) -> tuple[pd.DataFrame, dict]:
    """Hourly output of several plants plus a portfolio diagnostic.

    The smoothing statistic matters for the article: geographic spread between
    Kita, Bamako, Segou and Sikasso reduces the aggregate ramp rate that the
    thermal fleet has to follow, and this quantifies by how much.
    """
    results = {d.name: plant_output(d, year, allow_network=allow_network) for d in designs}
    frame = pd.DataFrame({name: r.ac_mw for name, r in results.items()})
    total = frame.sum(axis=1)

    total_capacity = sum(d.ac_capacity_mw for d in designs)
    individual_ramp = sum(
        float(r.ac_mw.diff().abs().max()) / r.design.ac_capacity_mw for r in results.values()
    ) / max(len(results), 1)
    portfolio_ramp = float(total.diff().abs().max()) / total_capacity if total_capacity else 0.0

    diagnostics = {
        "plants": {name: r.diagnostics for name, r in results.items()},
        "annual_energy_gwh": round(float(total.sum() / 1000.0), 2),
        "capacity_factor": round(
            float(total.sum() / (total_capacity * len(total))) if total_capacity else 0.0, 4
        ),
        "max_ramp_mw_per_hour": round(float(total.diff().abs().max()), 1),
        "mean_single_plant_ramp_pu": round(individual_ramp, 3),
        "portfolio_ramp_pu": round(portfolio_ramp, 3),
        "smoothing_benefit_pct": round(
            (1 - portfolio_ramp / individual_ramp) * 100.0 if individual_ramp else 0.0, 1
        ),
        "measured_resource": all(r.resource.is_measured for r in results.values()),
    }
    return frame, diagnostics


def design_from_generator(generator, *, station: str = "Bamako", dc_ac_ratio: float = 1.25) -> PlantDesign:
    """Build a :class:`PlantDesign` from a catalogue generator record."""
    return PlantDesign(
        name=generator.id,
        dc_capacity_mw=generator.capacity_mw * dc_ac_ratio,
        ac_capacity_mw=generator.capacity_mw,
        latitude=generator.latitude,
        longitude=generator.longitude,
        station=station,
    )

"""Derivation of line electrical parameters from conductor and tower geometry.

Line impedances in this project are *computed*, not copied: for every corridor
the catalogue records the conductor type, the number of circuits and the tower
family, and this module turns that into R, X and B. The point is auditability —
a reviewer can recompute any impedance from published conductor tables.

Two Sahelian specifics are handled explicitly:

* **Conductor temperature.** Resistance is corrected from the 20 degC table
  value to the operating temperature actually reached in Mali.
* **Ampacity derating.** Thermal ratings quoted by manufacturers assume 25-35
  degC ambient. Bamako and Kayes routinely exceed 40 degC, which removes a
  significant part of the rating. Ignoring this overstates transfer capability,
  so a simplified IEEE 738 steady-state heat balance is applied.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

MU0 = 4e-7 * math.pi
EPS0 = 8.8541878128e-12


@dataclass(frozen=True)
class Conductor:
    """One entry of the overhead-conductor library.

    Attributes
    ----------
    r20_ohm_km:
        DC resistance at 20 degC from the standard table.
    diameter_mm:
        Overall stranded diameter.
    gmr_factor:
        Geometric-mean-radius as a fraction of the physical radius. 0.768 is
        the usual value for a 61-strand all-aluminium-alloy conductor; 0.809
        suits 37-strand constructions.
    rated_current_a:
        Manufacturer ampacity at the reference ambient below.
    """

    name: str
    material: str
    section_mm2: float
    r20_ohm_km: float
    diameter_mm: float
    rated_current_a: float
    gmr_factor: float = 0.768
    alpha_per_k: float = 0.0036       # AAAC/ALMELEC temperature coefficient
    reference_ambient_c: float = 35.0
    max_operating_c: float = 75.0
    emissivity: float = 0.5
    absorptivity: float = 0.5
    source: str = "cigre"

    @property
    def radius_m(self) -> float:
        return self.diameter_mm / 2000.0

    @property
    def gmr_m(self) -> float:
        return self.radius_m * self.gmr_factor

    def resistance_ohm_km(self, temperature_c: float = 75.0) -> float:
        """AC resistance at ``temperature_c``.

        A 2 % skin-effect uplift is applied at 50 Hz, which matches measured
        values for the large sections used on 225 kV lines.
        """
        r_dc = self.r20_ohm_km * (1.0 + self.alpha_per_k * (temperature_c - 20.0))
        skin = 1.02 if self.section_mm2 > 300 else 1.01
        return r_dc * skin


#: Conductor library. Sections follow NF C34-125 (ALMELEC / AAAC "Aster"),
#: the family used on the OMVS and WAPP 225 kV corridors and on most Malian
#: sub-transmission, plus two ACSR entries for older lines.
CONDUCTORS: dict[str, Conductor] = {
    c.name: c
    for c in [
        Conductor("ASTER 851", "AAAC", 851.0, 0.0388, 38.0, 1380.0, 0.768),
        Conductor("ASTER 570", "AAAC", 570.0, 0.0579, 31.05, 1050.0, 0.768),
        Conductor("ASTER 366", "AAAC", 366.0, 0.0902, 24.9, 795.0, 0.768),
        Conductor("ASTER 288", "AAAC", 288.0, 0.1146, 22.1, 675.0, 0.768),
        Conductor("ASTER 228", "AAAC", 228.0, 0.1447, 19.6, 585.0, 0.768),
        Conductor("ASTER 147", "AAAC", 147.1, 0.2242, 15.75, 445.0, 0.809),
        Conductor("ASTER 116", "AAAC", 116.2, 0.2836, 14.0, 385.0, 0.809),
        Conductor("ASTER 75", "AAAC", 75.5, 0.4366, 11.25, 285.0, 0.809),
        Conductor("ASTER 54", "AAAC", 54.6, 0.6042, 9.6, 230.0, 0.809),
        Conductor("ASTER 34", "AAAC", 34.4, 0.9583, 7.56, 170.0, 0.809),
        Conductor("ACSR 228/38", "ACSR", 265.6, 0.1195, 21.0, 645.0, 0.726),
        Conductor("ACSR 147/25", "ACSR", 172.0, 0.1939, 17.1, 490.0, 0.726),
    ]
}


@dataclass(frozen=True)
class TowerGeometry:
    """Phase-conductor arrangement, used to obtain the geometric mean distance."""

    name: str
    voltage_kv: float
    #: Horizontal and vertical offsets of the three phases, in metres.
    phase_positions: tuple[tuple[float, float], ...]
    bundle: int = 1
    bundle_spacing_m: float = 0.4
    earth_wire: bool = True

    @property
    def gmd_m(self) -> float:
        """Geometric mean distance between the three phases."""
        (x1, y1), (x2, y2), (x3, y3) = self.phase_positions
        d12 = math.dist((x1, y1), (x2, y2))
        d23 = math.dist((x2, y2), (x3, y3))
        d13 = math.dist((x1, y1), (x3, y3))
        return (d12 * d23 * d13) ** (1.0 / 3.0)


#: Tower families in service on the Malian network. Dimensions follow the
#: standard designs used by the OMVS and WAPP corridors (double-circuit
#: vertical for 225 kV, flat single circuit for 150 kV, pin-type for 33 kV).
TOWERS: dict[str, TowerGeometry] = {
    "225kV-single-flat": TowerGeometry("225kV-single-flat", 225.0, ((-7.0, 22.0), (0.0, 22.0), (7.0, 22.0))),
    "225kV-double-vertical": TowerGeometry(
        "225kV-double-vertical", 225.0, ((-5.5, 30.0), (-6.5, 24.0), (-5.5, 18.0))
    ),
    "150kV-single-flat": TowerGeometry("150kV-single-flat", 150.0, ((-5.0, 18.0), (0.0, 18.0), (5.0, 18.0))),
    "66kV-single-triangle": TowerGeometry("66kV-single-triangle", 66.0, ((-2.5, 13.0), (0.0, 15.5), (2.5, 13.0))),
    "33kV-pin": TowerGeometry("33kV-pin", 33.0, ((-1.2, 10.0), (0.0, 10.6), (1.2, 10.0))),
    "15kV-pin": TowerGeometry("15kV-pin", 15.0, ((-0.9, 9.0), (0.0, 9.5), (0.9, 9.0))),
}


@dataclass(frozen=True)
class LineParameters:
    """Positive- and zero-sequence parameters of one circuit, per kilometre."""

    r_ohm_km: float
    x_ohm_km: float
    b_us_km: float
    c_nf_km: float
    r0_ohm_km: float
    x0_ohm_km: float
    c0_nf_km: float
    rated_current_a: float
    conductor: str
    tower: str
    operating_temp_c: float
    ambient_temp_c: float
    derating_factor: float

    @property
    def surge_impedance_ohm(self) -> float:
        return math.sqrt(self.x_ohm_km / (self.b_us_km * 1e-6))

    def natural_load_mw(self, voltage_kv: float) -> float:
        """Surge impedance loading — the natural transfer level of the line."""
        return voltage_kv**2 / self.surge_impedance_ohm


def bundle_gmr(conductor: Conductor, bundle: int, spacing_m: float) -> float:
    """Equivalent GMR of a bundled phase."""
    if bundle <= 1:
        return conductor.gmr_m
    if bundle == 2:
        return math.sqrt(conductor.gmr_m * spacing_m)
    if bundle == 3:
        return (conductor.gmr_m * spacing_m**2) ** (1 / 3)
    if bundle == 4:
        return 1.09 * (conductor.gmr_m * spacing_m**3) ** (1 / 4)
    raise ValueError(f"unsupported bundle size {bundle}")


def bundle_radius(conductor: Conductor, bundle: int, spacing_m: float) -> float:
    """Equivalent radius of a bundled phase, for the capacitance calculation."""
    if bundle <= 1:
        return conductor.radius_m
    if bundle == 2:
        return math.sqrt(conductor.radius_m * spacing_m)
    if bundle == 3:
        return (conductor.radius_m * spacing_m**2) ** (1 / 3)
    if bundle == 4:
        return 1.09 * (conductor.radius_m * spacing_m**3) ** (1 / 4)
    raise ValueError(f"unsupported bundle size {bundle}")


def ampacity_derating(
    conductor: Conductor,
    ambient_c: float,
    *,
    wind_speed_ms: float = 0.6,
    solar_radiation_wm2: float = 1000.0,
) -> float:
    """Ratio of the achievable current to the table ampacity in Sahelian air.

    Simplified steady-state IEEE 738 balance: convection and radiation must
    remove joule heating plus absorbed solar gain. Both the reference case (at
    the conductor's reference ambient) and the study case are solved, and the
    ratio of the two currents is returned. A hot, still, sunny Malian afternoon
    typically yields 0.80-0.90.
    """

    def losses(ambient: float) -> float:
        t_c = conductor.max_operating_c
        d = conductor.diameter_mm / 1000.0
        delta = t_c - ambient
        film = (t_c + ambient) / 2.0 + 273.15

        # Forced convection, low-wind branch of IEEE 738.
        k_air = 2.424e-2 + 7.477e-5 * (film - 273.15)
        rho_air = 1.293 * 273.15 / film
        mu_air = 1.458e-6 * film**1.5 / (film + 110.4)
        reynolds = max(rho_air * wind_speed_ms * d / mu_air, 1e-6)
        nusselt_forced = 1.01 + 1.35 * reynolds**0.52
        q_forced = k_air * delta * nusselt_forced * math.pi

        # Natural convection, which dominates when the wind drops.
        q_natural = 3.645 * math.sqrt(rho_air) * d**0.75 * max(delta, 0.0) ** 1.25

        q_conv = max(q_forced, q_natural)
        q_rad = (
            17.8
            * conductor.emissivity
            * d
            * (((t_c + 273.15) / 100.0) ** 4 - ((ambient + 273.15) / 100.0) ** 4)
        )
        q_sun = conductor.absorptivity * solar_radiation_wm2 * d
        return max(q_conv + q_rad - q_sun, 1e-6)

    reference = losses(conductor.reference_ambient_c)
    study = losses(ambient_c)
    return math.sqrt(study / reference)


def line_parameters(
    conductor_name: str,
    tower_name: str,
    *,
    ambient_c: float = 40.0,
    operating_temp_c: float = 75.0,
    wind_speed_ms: float = 0.6,
    earth_resistivity_ohm_m: float = 200.0,
    frequency_hz: float = 50.0,
) -> LineParameters:
    """Positive and zero sequence parameters for one circuit.

    The zero-sequence quantities use the Carson-Clem earth-return
    approximation, which is what protection studies in the region assume;
    ``earth_resistivity_ohm_m`` defaults to a value representative of the
    lateritic soils of southern Mali.
    """
    conductor = CONDUCTORS[conductor_name]
    tower = TOWERS[tower_name]
    omega = 2 * math.pi * frequency_hz

    gmr = bundle_gmr(conductor, tower.bundle, tower.bundle_spacing_m)
    radius = bundle_radius(conductor, tower.bundle, tower.bundle_spacing_m)
    gmd = tower.gmd_m

    r_pos = conductor.resistance_ohm_km(operating_temp_c) / tower.bundle
    x_pos = omega * 2e-7 * math.log(gmd / gmr) * 1000.0
    c_pos = 2 * math.pi * EPS0 / math.log(gmd / radius) * 1e12  # F/m -> nF/km
    b_pos = omega * c_pos * 1e-9 * 1e6                          # microsiemens/km

    # Carson-Clem: earth return adds resistance and a large reactance term.
    de = 658.87 * math.sqrt(earth_resistivity_ohm_m / frequency_hz)
    r_earth = 9.869e-4 * frequency_hz
    r_zero = r_pos + 3.0 * r_earth
    gmr_three_phase = (gmr * gmd**2) ** (1.0 / 3.0)
    x_zero = omega * 2e-7 * 3.0 * math.log(de / gmr_three_phase) * 1000.0
    c_zero = c_pos / 2.4   # usual ratio for single-circuit lines with earth wire

    derating = ampacity_derating(conductor, ambient_c, wind_speed_ms=wind_speed_ms)
    rated = conductor.rated_current_a * derating * tower.bundle

    return LineParameters(
        r_ohm_km=r_pos,
        x_ohm_km=x_pos,
        b_us_km=b_pos,
        c_nf_km=c_pos,
        r0_ohm_km=r_zero,
        x0_ohm_km=x_zero,
        c0_nf_km=c_zero,
        rated_current_a=rated,
        conductor=conductor_name,
        tower=tower_name,
        operating_temp_c=operating_temp_c,
        ambient_temp_c=ambient_c,
        derating_factor=derating,
    )


def transformer_impedance(
    sn_mva: float, hv_kv: float, lv_kv: float, *, vk_percent: float, vkr_percent: float
) -> dict[str, float]:
    """Short-circuit impedance of a two-winding transformer, referred to HV."""
    z_base = hv_kv**2 / sn_mva
    z_k = vk_percent / 100.0 * z_base
    r_k = vkr_percent / 100.0 * z_base
    x_k = math.sqrt(max(z_k**2 - r_k**2, 0.0))
    return {
        "z_ohm": z_k,
        "r_ohm": r_k,
        "x_ohm": x_k,
        "z_base_ohm": z_base,
        "ratio": hv_kv / lv_kv,
    }

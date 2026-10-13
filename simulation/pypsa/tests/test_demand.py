"""Demand: the level, the shape, and the snapshot index.

The level is the one decision in this module that can be wrong without looking
wrong. A copper plate has no network and therefore computes no losses, so if
demand is set to what customers consume the model generates roughly a fifth
less energy than the system really does, and every fuel bill and emission
figure is understated by that fifth while the model still solves cleanly.
"""

import pytest
from mali_pypsa.demand import (
    build_demand,
    check_energy_balance,
    diurnal_profile,
    monthly_profile,
    resample,
    snapshot_weightings,
    snapshots,
)


@pytest.fixture(scope="module")
def profile(catalog):
    return build_demand(catalog)


def test_the_default_basis_includes_the_losses_the_model_cannot_compute(catalog):
    served = build_demand(catalog, basis="utility_served")
    entry = build_demand(catalog, basis="network_entry")
    required = build_demand(catalog, basis="generation_required")
    assert served.annual_energy_gwh < entry.annual_energy_gwh < required.annual_energy_gwh
    assert build_demand(catalog).basis == "generation_required"


def test_an_unknown_basis_is_refused(catalog):
    with pytest.raises(ValueError, match="basis must be one of"):
        build_demand(catalog, basis="whatever")


def test_each_basis_carries_its_own_target_and_not_another(catalog):
    """Comparing a profile with the target stored beside it cannot fail.

    build_demand scales the series to that target by construction, so the
    obvious assertion is arithmetic rather than evidence. What can fail, and
    is the error worth catching, is a basis picking up the wrong figure.
    """
    keys = {
        "utility_served": "utility_energy_gwh",
        "network_entry": "network_entry_energy_gwh",
        "generation_required": "generation_required_gwh",
    }
    for basis, key in keys.items():
        built = build_demand(catalog, basis=basis)
        assert built.annual_energy_gwh == pytest.approx(
            built.calibration[key], rel=0.01
        )
        others = [v for k, v in keys.items() if k != basis]
        for other in others:
            assert built.annual_energy_gwh != pytest.approx(
                built.calibration[other], rel=0.01
            )


def test_the_peak_is_in_the_evening(profile):
    """Thermal mass, not air temperature, places the Malian peak."""
    assert 17 <= profile.series_mw.idxmax().hour <= 22


def test_the_diurnal_minimum_is_at_night(profile):
    diurnal = diurnal_profile(profile)
    assert 1 <= int(diurnal.idxmin()) <= 6


def test_the_hottest_hour_is_not_the_peak_hour(profile):
    """A model that peaks at 15:00 has forgotten the building stock."""
    diurnal = diurnal_profile(profile)
    assert diurnal.loc[19] > diurnal.loc[15]


def test_the_load_factor_is_credible(profile):
    assert 0.5 < profile.load_factor < 0.85


def test_the_profile_passes_its_own_checks(profile):
    assert check_energy_balance(profile) == []


def test_the_checks_catch_a_profile_that_lost_its_energy(profile):
    from dataclasses import replace

    halved = replace(profile, series_mw=profile.series_mw * 0.5)
    assert any("target of" in p for p in check_energy_balance(halved))


def test_the_checks_catch_a_profile_built_on_the_wrong_basis(catalog):
    """The failure the old assertion could not see: right arithmetic, wrong level."""
    from dataclasses import replace

    served = build_demand(catalog, basis="utility_served")
    mislabelled = replace(served, basis="generation_required")
    assert any("target of" in p for p in check_energy_balance(mislabelled))


def test_the_checks_refuse_a_basis_they_do_not_know(profile):
    from dataclasses import replace

    assert check_energy_balance(replace(profile, basis="vibes")) == [
        "unknown demand basis 'vibes'"
    ]


def test_monthly_sums_are_not_the_evidence_the_level_is(profile):
    """Stated plainly: the sum of the parts equalling the whole proves nothing.

    What this pins instead is that the monthly table disaggregates rather than
    rescales -- no month carries the annual mean.
    """
    monthly = monthly_profile(profile)
    mean = profile.annual_energy_gwh / 12
    assert (monthly["energy_gwh"] - mean).abs().max() > 0.05 * mean


def test_monthly_energy_sums_to_the_year(profile):
    monthly = monthly_profile(profile)
    assert len(monthly) == 12
    assert monthly["energy_gwh"].sum() == pytest.approx(profile.annual_energy_gwh, rel=0.01)


def test_the_hot_season_carries_more_energy_than_the_cool_season(profile):
    monthly = monthly_profile(profile)
    assert monthly.loc[4, "energy_gwh"] > monthly.loc[1, "energy_gwh"]


def test_snapshots_cover_a_whole_year_in_malian_time(profile):
    index = snapshots(2024)
    assert len(index) == 8784  # 2024 is a leap year
    assert str(index.tz) in {"UTC", "Africa/Bamako"}
    assert index[0].hour == 0
    assert index[-1].hour == 23


def test_sampling_thins_the_index_without_shortening_the_year():
    hourly = snapshots(2024)
    six = snapshots(2024, step_hours=6)
    assert len(six) == len(hourly) // 6
    assert six[0] == hourly[0]
    assert (six[-1] - six[0]).days == 365


def test_weightings_restore_the_hours_sampling_removed():
    index = snapshots(2024, step_hours=6)
    weights = snapshot_weightings(index, step_hours=6)
    assert weights.sum() == pytest.approx(8784)


def test_resampling_preserves_the_mean_demand(profile):
    index = snapshots(2024, step_hours=6)
    sampled = resample(profile, index)
    assert sampled.mean() == pytest.approx(profile.series_mw.mean(), rel=0.02)


def test_the_calibration_records_where_the_level_came_from(profile):
    for key in ("basis", "target_gwh", "generation_required_gwh"):
        assert key in profile.calibration

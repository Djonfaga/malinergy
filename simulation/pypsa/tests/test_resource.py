"""The solar resource, and the honesty of its provenance.

Two things matter here. The profiles must behave like sunlight — no generation
at midnight, a capacity factor in the range a Malian plant actually delivers.
And the model must always be able to say where the resource came from, because
a clear-sky model and a reanalysis are not the same evidence and a result that
quietly swapped one for the other would be unciteable.
"""

import pandas as pd
import pytest
from mali_pypsa.resource import (
    MALI_BOUNDS,
    PANEL,
    ResourceResult,
    capacity_factors,
    check_profiles,
    core_capacity_factors,
    cutout_path,
)
from mali_pypsa.sampling import downsample

YEAR = 2024


@pytest.fixture(scope="module")
def resource(catalog, index):
    return capacity_factors(catalog, YEAR, index, prefer_atlite=False)


@pytest.fixture(scope="module")
def hourly_index():
    return pd.date_range(f"{YEAR}-01-01", f"{YEAR}-12-31 23:00", freq="h", tz="UTC")


@pytest.fixture(scope="module")
def hourly_profiles(catalog, hourly_index):
    """The clear-sky model over a full hourly year, computed once.

    Several checks here are only meaningful at hourly resolution -- a twelve
    hourly index can step straight over sunrise -- and the geometry is slow
    enough that recomputing it per test is the difference between a suite that
    gets run and one that does not.
    """
    profiles, _ = core_capacity_factors(catalog, YEAR, hourly_index)
    return profiles


def test_every_solar_plant_gets_a_profile(catalog, resource):
    expected = {
        g.id for g in catalog.generators.values() if g.technology == "solar" and g.in_service
    }
    assert expected <= set(resource.profiles)


def test_profiles_are_aligned_on_the_snapshots(index, resource):
    for series in resource.profiles.values():
        assert series.index.equals(index)


def test_capacity_factors_stay_within_zero_and_one(resource):
    """Both producers clip, so this only pins that the clipping stays in place."""
    for series in resource.profiles.values():
        assert series.min() >= 0.0
        assert series.max() <= 1.0


def test_a_plant_reaches_a_plausible_peak_rather_than_a_clipped_one(resource):
    """A profile pinned at 1.0 would pass the bounds check and be nonsense."""
    for name, series in resource.profiles.items():
        peak = float(series.max())
        assert 0.6 < peak < 1.0, f"{name} peaks at {peak:.2f}"
        assert float((series >= 0.999).mean()) < 0.001, f"{name} is clipped flat"


def test_nothing_generates_at_midnight(hourly_profiles):
    """Checked on an hourly index, because a twelve-hourly one can miss it."""
    for series in hourly_profiles.values():
        assert float(series[series.index.hour == 0].max()) == 0.0


def test_the_annual_mean_is_what_a_malian_plant_delivers(resource):
    """And the sampled year must agree with the hourly one, not with its noons."""
    for series in resource.profiles.values():
        assert 0.15 < float(series.mean()) < 0.30


def test_sampling_does_not_change_the_annual_sunshine(catalog, hourly_index):
    """The defect this guards against inflated solar by four fifths."""
    reference = None
    for step in (1, 4, 12):
        result = capacity_factors(
            catalog, YEAR, hourly_index[::step], prefer_atlite=False
        )
        mean = sum(float(s.mean()) for s in result.profiles.values()) / len(result.profiles)
        if reference is None:
            reference = mean
        assert mean == pytest.approx(reference, rel=0.02)


def test_output_peaks_around_solar_noon(hourly_profiles):
    series = next(iter(hourly_profiles.values()))
    june = series[series.index.month == 6]
    by_hour = june.groupby(june.index.hour).mean()
    assert 11 <= int(by_hour.idxmax()) <= 14


def test_the_dry_season_outshines_the_rains(hourly_profiles):
    """Harmattan dust against monsoon cloud: the dry season still wins."""
    series = next(iter(hourly_profiles.values()))
    monthly = series.groupby(series.index.month).mean()
    assert monthly.loc[3] > monthly.loc[8]


def test_the_provider_is_always_recorded(resource):
    assert resource.provider
    assert resource.summary()["provider"] == resource.provider


def test_a_modelled_resource_does_not_claim_to_be_measured(resource):
    """Offline the core falls back to geometry, and the label must say so."""
    assert resource.provider.startswith("core/clear-sky")
    assert resource.is_measured is False
    assert any("not measured" in w for w in resource.warnings)


def test_the_provider_is_read_from_what_the_core_found(catalog, index, monkeypatch):
    """Labelling by the function called rather than by what it returned would
    turn provenance into a guess that reads as fact."""
    import mali_energy.solar.pv as pv

    original = pv.plant_output

    def pretend_satellite(design, year, **kwargs):
        output = original(design, year, **kwargs)
        object.__setattr__(output.resource, "provider", "pvgis")
        return output

    monkeypatch.setattr(pv, "plant_output", pretend_satellite)
    result = capacity_factors(catalog, YEAR, index, prefer_atlite=False)
    assert result.provider == "core/pvgis"
    assert result.is_measured is True


def test_a_missing_cutout_is_reported_rather_than_ignored(catalog, index):
    """Falling back in silence is the failure worth preventing."""
    result = capacity_factors(
        catalog, YEAR, index, prefer_atlite=True, cutout=cutout_path(1999)
    )
    assert result.provider.startswith("core/")
    assert result.warnings


def test_full_load_hours_do_not_depend_on_the_sampling_interval(
    hourly_index, hourly_profiles
):
    totals = []
    for step in (1, 6):
        sampled = {
            name: downsample(series, hourly_index[::step])
            for name, series in hourly_profiles.items()
        }
        result = ResourceResult(profiles=sampled, provider="test")
        totals.append(sum(result.summary()["annual_full_load_hours"].values()))
    assert totals[0] == pytest.approx(totals[1], rel=0.02)


def test_the_checks_catch_a_profile_that_runs_at_night(index):
    broken = ResourceResult(
        profiles={"GEN_FAKE": pd.Series(0.2, index=index)}, provider="test"
    )
    assert any("at night" in p for p in check_profiles(broken))


def test_the_checks_catch_an_implausible_capacity_factor(index):
    day = pd.Series((index.hour >= 7) & (index.hour <= 17), index=index).astype(float)
    broken = ResourceResult(profiles={"GEN_FAKE": day}, provider="test")
    assert any("outside the 15-30" in p for p in check_profiles(broken))


def test_a_real_resource_passes_its_own_checks(resource):
    assert check_profiles(resource) == []


def test_the_bounding_box_contains_mali(catalog):
    """Malian buses only: the catalogue also holds the far ends of the links."""
    inside = 0
    for bus in catalog.buses.values():
        if bus.zone == "External" or bus.longitude is None or bus.latitude is None:
            continue
        assert MALI_BOUNDS["x"].start <= bus.longitude <= MALI_BOUNDS["x"].stop
        assert MALI_BOUNDS["y"].start <= bus.latitude <= MALI_BOUNDS["y"].stop
        inside += 1
    assert inside > 10


def test_the_panel_is_the_one_installed_in_mali():
    assert PANEL == "CSi"

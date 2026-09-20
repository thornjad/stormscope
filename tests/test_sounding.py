"""Tests for sounding index calculations."""

import math

import pytest

from stormscope.sounding import clean_profile, compute_indices, find_inversions

_PRESSURES = [1000, 950, 900, 850, 800, 750, 700, 650, 600, 550, 500, 450, 400, 350, 300, 250, 200]


def _std_height(p_mb: float) -> float:
    """standard-atmosphere height (m) for a pressure, troposphere only."""
    return 44330.77 * (1 - (p_mb / 1013.25) ** 0.190263)


def _profile(lapse_c_km=6.5, sfc_t=15.0, spread=10.0, wind=None) -> list[dict]:
    """synthetic profile with linear temperature decrease and a constant dewpoint spread.

    wind: optional callable(height_m) -> (direction_deg, speed_kt).
    """
    levels = []
    for p in _PRESSURES:
        z = _std_height(p)
        t = sfc_t - lapse_c_km * z / 1000.0
        d, spd = wind(z) if wind else (None, None)
        levels.append({
            "pressure": float(p), "height": z, "temp": t, "dewpoint": t - spread,
            "wind_dir": d, "wind_speed": spd,
        })
    return levels


def _westerly_shear(z):
    return 270.0, 5.0 * z / 1000.0  # 5 kt per km


class TestCleanProfile:
    def test_drops_null_thermo_and_nonmonotonic_levels(self):
        levels = [
            {"pressure": 1000.0, "height": 90.0, "temp": None, "dewpoint": None},
            {"pressure": 970.0, "height": 350.0, "temp": 25.0, "dewpoint": 17.0},
            {"pressure": 970.0, "height": 351.0, "temp": 25.0, "dewpoint": 17.0},
            {"pressure": 925.0, "height": 780.0, "temp": 24.0, "dewpoint": None},
            {"pressure": 850.0, "height": 1500.0, "temp": 20.0, "dewpoint": 14.0},
        ]
        out = clean_profile(levels)
        assert [lv["pressure"] for lv in out] == [970.0, 850.0]


class TestComputeIndices:
    def test_too_short_profile_is_all_none(self):
        result = compute_indices(_profile()[:2])
        assert all(v is None for v in result.values())

    def test_lapse_rate_matches_input(self):
        result = compute_indices(_profile(lapse_c_km=6.5))
        assert result["lapse_rate_700_500_c_km"] == pytest.approx(6.5, abs=0.1)
        assert result["lapse_rate_850_500_c_km"] == pytest.approx(6.5, abs=0.1)

    def test_freezing_level(self):
        result = compute_indices(_profile(lapse_c_km=6.5, sfc_t=15.0))
        # 15C / 6.5 C/km is 2308 m MSL; the 1000 mb "surface" already sits ~111 m up
        expected = 15.0 / 6.5 * 1000 - _std_height(1000)
        assert result["freezing_level_agl_m"] == pytest.approx(expected, abs=60)

    def test_freezing_level_zero_when_surface_is_freezing(self):
        result = compute_indices(_profile(sfc_t=-5.0))
        assert result["freezing_level_agl_m"] == 0

    def test_stable_profile_has_no_cape(self):
        # dry, slowly cooling column: parcel never becomes buoyant
        result = compute_indices(_profile(lapse_c_km=4.0, spread=25.0))
        assert result["cape_jkg"] == 0
        assert result["lfc_agl_m"] is None
        assert result["el_agl_m"] is None

    def test_unstable_profile_has_cape_and_ordered_levels(self):
        result = compute_indices(_profile(lapse_c_km=8.5, sfc_t=30.0, spread=3.0))
        assert result["cape_jkg"] > 500
        assert 0 <= result["lcl_agl_m"] <= result["lfc_agl_m"]

    def test_pwat_is_reasonable(self):
        result = compute_indices(_profile(sfc_t=25.0, spread=5.0))
        assert 20 < result["pwat_mm"] < 80

    def test_bulk_shear_from_linear_wind_profile(self):
        result = compute_indices(_profile(wind=_westerly_shear))
        assert result["shear_0_1km_kt"] == pytest.approx(5.0, abs=0.5)
        assert result["shear_0_6km_kt"] == pytest.approx(30.0, abs=1.0)

    def test_srh_computed_with_wind(self):
        result = compute_indices(_profile(wind=_westerly_shear))
        assert result["srh_0_1km"] is not None
        assert result["srh_0_3km"] is not None

    def test_veering_wind_gives_positive_srh(self):
        def veering(z):
            return 150.0 + 40.0 * z / 1000.0, 10.0 + 6.0 * z / 1000.0

        result = compute_indices(_profile(wind=veering))
        assert result["srh_0_3km"] > 50

    def test_missing_wind_leaves_thermo_intact(self):
        result = compute_indices(_profile())
        assert result["shear_0_6km_kt"] is None
        assert result["srh_0_3km"] is None
        assert result["cape_jkg"] is not None

    def test_shallow_wind_profile_skips_deep_layers(self):
        levels = _profile(wind=_westerly_shear)
        # keep wind only through ~850 mb (about 1.5 km)
        for lv in levels:
            if lv["pressure"] < 850:
                lv["wind_dir"] = lv["wind_speed"] = None
        result = compute_indices(levels)
        assert result["shear_0_6km_kt"] is None
        assert result["srh_0_3km"] is None

    def test_no_nan_leaks(self):
        result = compute_indices(_profile(wind=_westerly_shear))
        assert not any(isinstance(v, float) and math.isnan(v) for v in result.values())


def _lv(p, z, t):
    return {"pressure": float(p), "height": float(z), "temp": float(t), "dewpoint": float(t) - 5.0}


class TestFindInversions:
    def test_standard_atmosphere_has_none(self):
        assert find_inversions(_profile()) == []

    def test_surface_based_inversion(self):
        levels = [_lv(1000, 100, 5), _lv(975, 300, 8), _lv(950, 500, 6), _lv(900, 900, 3)]
        inv = find_inversions(levels)
        assert len(inv) == 1
        assert inv[0]["surface_based"] is True
        assert inv[0]["base_agl_m"] == 0
        assert inv[0]["top_agl_m"] == 200
        assert inv[0]["base_pressure_mb"] == 1000.0
        assert inv[0]["top_pressure_mb"] == 975.0
        assert inv[0]["delta_c"] == 3.0

    def test_elevated_inversion_heights_are_agl(self):
        levels = [_lv(1000, 100, 15), _lv(925, 800, 9), _lv(900, 1000, 11), _lv(850, 1500, 8)]
        inv = find_inversions(levels)
        assert len(inv) == 1
        layer = inv[0]
        assert layer["surface_based"] is False
        assert layer["base_agl_m"] == 700
        assert layer["top_agl_m"] == 900
        assert layer["delta_c"] == 2.0

    def test_adjacent_warming_steps_merge_through_isothermal_level(self):
        levels = [
            _lv(1000, 100, 15), _lv(925, 800, 10), _lv(913, 900, 10.6),
            _lv(900, 1000, 10.6), _lv(880, 1200, 11.4), _lv(850, 1500, 9),
        ]
        inv = find_inversions(levels)
        assert len(inv) == 1
        assert inv[0]["delta_c"] == 1.4
        assert inv[0]["top_agl_m"] == 1100

    def test_trailing_isothermal_levels_do_not_extend_top(self):
        levels = [_lv(1000, 100, 15), _lv(925, 800, 10), _lv(900, 1000, 12), _lv(850, 1500, 12), _lv(800, 2000, 8)]
        inv = find_inversions(levels)
        assert inv[0]["top_agl_m"] == 900

    def test_weak_layers_ignored(self):
        levels = [_lv(1000, 100, 15), _lv(925, 800, 10), _lv(900, 1000, 10.3), _lv(850, 1500, 7)]
        assert find_inversions(levels) == []

    def test_min_delta_adjustable(self):
        levels = [_lv(1000, 100, 15), _lv(925, 800, 10), _lv(900, 1000, 10.3), _lv(850, 1500, 7)]
        assert len(find_inversions(levels, min_delta_c=0.2)) == 1

    def test_layers_based_above_cutoff_ignored(self):
        levels = [_lv(1000, 100, 15), _lv(500, 5800, -15), _lv(450, 6500, -12), _lv(400, 7100, -18)]
        assert find_inversions(levels) == []
        assert len(find_inversions(levels, max_base_agl_m=8000)) == 1

    def test_multiple_layers_ordered_bottom_up(self):
        levels = [
            _lv(1000, 100, 10), _lv(975, 300, 13), _lv(950, 500, 9),
            _lv(850, 1500, 3), _lv(800, 2000, 6), _lv(700, 3000, -2),
        ]
        inv = find_inversions(levels)
        assert [layer["surface_based"] for layer in inv] == [True, False]
        assert inv[0]["base_agl_m"] < inv[1]["base_agl_m"]

    def test_null_levels_skipped_and_short_profile_empty(self):
        below_ground = {"pressure": 1000.0, "height": 93.0, "temp": None, "dewpoint": None}
        levels = [below_ground, _lv(970, 350, 10), _lv(925, 780, 12), _lv(850, 1500, 8)]
        inv = find_inversions(levels)
        # heights measured from the first level with data, not the below-ground row
        assert inv[0]["surface_based"] is True
        assert inv[0]["base_agl_m"] == 0
        assert find_inversions([_lv(1000, 100, 10)]) == []

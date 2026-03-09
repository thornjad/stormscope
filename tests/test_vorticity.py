"""Tests for vorticity computation — pure math, no mocking."""

import math

from stormscope.vorticity import (
    coriolis_parameter,
    compute_vorticity,
    grid_spacing,
    wind_components,
)


class TestWindComponents:
    def test_south_wind(self):
        # wind FROM the south (180 deg) should give v > 0 (northward? no)
        # meteorological: 180 = from south, so wind blows north
        # u = -speed*sin(180) = 0, v = -speed*cos(180) = speed
        u, v = wind_components(10.0, 180.0)
        assert abs(u) < 1e-10
        assert abs(v - 10.0) < 1e-10

    def test_west_wind(self):
        # wind FROM the west (270 deg) blows east
        # u = -speed*sin(270) = speed, v = -speed*cos(270) = 0
        u, v = wind_components(10.0, 270.0)
        assert abs(u - 10.0) < 1e-10
        assert abs(v) < 1e-10

    def test_calm(self):
        u, v = wind_components(0.0, 0.0)
        assert u == 0.0
        assert v == 0.0


class TestGridSpacing:
    def test_equator(self):
        dx, dy = grid_spacing(0.0)
        # at equator dx == dy
        assert abs(dx - dy) < 1.0  # within 1 meter

    def test_high_latitude(self):
        dx, dy = grid_spacing(60.0)
        # dx should be about half of dy at 60 degrees
        assert abs(dx / dy - 0.5) < 0.01


class TestCoriolisParameter:
    def test_midlatitude(self):
        f = coriolis_parameter(45.0)
        expected = 2.0 * 7.2921e-5 * math.sin(math.radians(45.0))
        assert abs(f - expected) < 1e-12

    def test_equator(self):
        f = coriolis_parameter(0.0)
        assert abs(f) < 1e-15


class TestComputeVorticity:
    def test_uniform_wind_zero_relative(self):
        # uniform westerly wind everywhere -> no shear -> zero relative vorticity
        wind = (10.0, 270.0)
        rel, abso = compute_vorticity(45.0, wind, wind, wind, wind, wind)
        assert abs(rel) < 1e-10
        # absolute should equal coriolis
        f = coriolis_parameter(45.0)
        assert abs(abso - f) < 1e-10

    def test_cyclonic_shear_positive(self):
        # set up cyclonic (counterclockwise) shear in NH
        # south wind on east side, north wind on west side
        center = (10.0, 270.0)
        north = (10.0, 270.0)
        south = (10.0, 270.0)
        east = (10.0, 180.0)   # from south (northward v component)
        west = (10.0, 0.0)     # from north (southward v component)

        rel, abso = compute_vorticity(45.0, center, north, south, east, west)
        assert rel > 0  # cyclonic in NH
        assert abso > rel  # absolute adds positive coriolis

    def test_southern_hemisphere_coriolis_negative(self):
        # same cyclonic shear pattern, but in SH coriolis is negative
        center = (10.0, 270.0)
        north = (10.0, 270.0)
        south = (10.0, 270.0)
        east = (10.0, 180.0)
        west = (10.0, 0.0)

        rel, abso = compute_vorticity(-45.0, center, north, south, east, west)
        assert rel > 0  # shear-driven vorticity is positive regardless of hemisphere
        assert abso < rel  # negative coriolis reduces absolute vorticity

    def test_polar_latitude_returns_none(self):
        wind = (10.0, 270.0)
        rel, abso = compute_vorticity(90.0, wind, wind, wind, wind, wind)
        assert rel is None
        assert abso is None

    def test_near_polar_returns_none(self):
        wind = (10.0, 270.0)
        rel, abso = compute_vorticity(86.0, wind, wind, wind, wind, wind)
        assert rel is None
        assert abso is None

"""Tests for geographic utilities."""

from shapely.geometry import Polygon

from stormscope.geo import polygon_to_region


def test_oklahoma_polygon():
    poly = Polygon([(-97.8, 35.2), (-97.2, 35.2), (-97.2, 35.8), (-97.8, 35.8)])
    region = polygon_to_region(poly)
    assert "Oklahoma" in region


def test_minnesota_polygon():
    poly = Polygon([(-93.5, 44.8), (-93.0, 44.8), (-93.0, 45.2), (-93.5, 45.2)])
    region = polygon_to_region(poly)
    assert "Minnesota" in region


def test_fallback_for_ocean():
    poly = Polygon([(-60.0, 30.0), (-59.0, 30.0), (-59.0, 31.0), (-60.0, 31.0)])
    region = polygon_to_region(poly)
    assert "near" in region

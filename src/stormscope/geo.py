"""geographic utilities for polygon-to-region descriptions."""

import json
from pathlib import Path

from shapely.geometry import Point, shape

_states: list[dict] | None = None
_DATA_PATH = Path(__file__).resolve().parent / "data" / "us_states.json"


def load_states() -> list[dict]:
    """load us_states.json, cached in module-level variable."""
    global _states
    if _states is not None:
        return _states
    with open(_DATA_PATH) as f:
        data = json.load(f)
    _states = data["features"]
    return _states


def _cardinal_position(centroid: Point, bounds: tuple[float, float, float, float]) -> str:
    """determine rough cardinal position within a bounding box."""
    minx, miny, maxx, maxy = bounds
    lat_range = maxy - miny
    lon_range = maxx - minx

    rel_lat = (centroid.y - miny) / lat_range if lat_range > 0 else 0.5
    rel_lon = (centroid.x - minx) / lon_range if lon_range > 0 else 0.5

    ns = ""
    if rel_lat < 0.33:
        ns = "southern"
    elif rel_lat > 0.67:
        ns = "northern"

    ew = ""
    if rel_lon < 0.33:
        ew = "western"
    elif rel_lon > 0.67:
        ew = "eastern"

    if ns and ew:
        return f"{ns} {ew}"
    if ns:
        return ns
    if ew:
        return ew
    return "central"


def polygon_to_region(polygon) -> str:
    """convert a shapely geometry to a human-readable region description."""
    centroid = polygon.centroid
    states = load_states()

    for feat in states:
        state_geom = shape(feat["geometry"])
        if state_geom.contains(centroid):
            name = feat["properties"]["NAME"]
            pos = _cardinal_position(centroid, state_geom.bounds)
            return f"{pos} {name}"

    best_dist = float("inf")
    best_name = None
    for feat in states:
        state_geom = shape(feat["geometry"])
        d = state_geom.distance(centroid)
        if d < best_dist:
            best_dist = d
            best_name = feat["properties"]["NAME"]

    if best_name and best_dist < 2.0:
        return f"near {best_name}"

    return f"near {centroid.y:.1f}N {abs(centroid.x):.1f}W"

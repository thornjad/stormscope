"""geographic utilities for polygon-to-region descriptions and IP geolocation."""

import json
import logging
from pathlib import Path

import httpx
from shapely.geometry import Point, shape

logger = logging.getLogger(__name__)

_states: list[tuple[str, object]] | None = None
_DATA_PATH = Path(__file__).resolve().parent / "data" / "us_states.json"


def load_states() -> list[tuple[str, object]]:
    """load us_states.json with pre-computed shapely geometries."""
    global _states
    if _states is not None:
        return _states
    with open(_DATA_PATH) as f:
        data = json.load(f)
    _states = [
        (feat["properties"]["NAME"], shape(feat["geometry"]))
        for feat in data["features"]
    ]
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

    for name, state_geom in states:
        if state_geom.contains(centroid):
            pos = _cardinal_position(centroid, state_geom.bounds)
            return f"{pos} {name}"

    best_dist = float("inf")
    best_name = None
    for name, state_geom in states:
        d = state_geom.distance(centroid)
        if d < best_dist:
            best_dist = d
            best_name = name

    if best_name and best_dist < 2.0:
        return f"near {best_name}"

    lat_dir = "N" if centroid.y >= 0 else "S"
    lon_dir = "W" if centroid.x < 0 else "E"
    return f"near {abs(centroid.y):.1f}{lat_dir} {abs(centroid.x):.1f}{lon_dir}"


_ip_location: tuple[float, float] | None = None
_ip_location_fetched = False


async def geolocate_ip() -> tuple[float, float] | None:
    """approximate location via IP geolocation, cached for server lifetime."""
    global _ip_location, _ip_location_fetched
    if _ip_location_fetched:
        return _ip_location

    _ip_location_fetched = True
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://ipinfo.io/json", timeout=5.0)
            resp.raise_for_status()
            loc = resp.json()["loc"]
            lat_s, lon_s = loc.split(",")
            _ip_location = (float(lat_s), float(lon_s))
            logger.info("IP geolocation: %s, %s", lat_s, lon_s)
    except Exception:
        logger.debug("IP geolocation failed", exc_info=True)
        _ip_location = None

    return _ip_location

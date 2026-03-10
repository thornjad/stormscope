"""geographic utilities for polygon-to-region descriptions and geolocation."""

import asyncio
import json
import logging
import os
import subprocess
import sys
import tempfile
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


_LOCATION_SWIFT_SRC = """\
import CoreLocation
import Foundation

class Delegate: NSObject, CLLocationManagerDelegate {
    let manager = CLLocationManager()

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
    }

    func start() {
        switch manager.authorizationStatus {
        case .authorizedAlways:
            manager.requestLocation()
        case .notDetermined:
            manager.requestAlwaysAuthorization()
        default:
            exit(1)
        }
    }

    func locationManagerDidChangeAuthorization(_ m: CLLocationManager) {
        if m.authorizationStatus == .authorizedAlways {
            m.requestLocation()
        } else if m.authorizationStatus != .notDetermined {
            exit(1)
        }
    }

    func locationManager(_ m: CLLocationManager, didUpdateLocations locs: [CLLocation]) {
        guard let loc = locs.last else { return }
        print("\\(loc.coordinate.latitude),\\(loc.coordinate.longitude)")
        fflush(stdout)
        exit(0)
    }

    func locationManager(_ m: CLLocationManager, didFailWithError error: Error) {
        fputs("location error: \\(error.localizedDescription)\\n", stderr)
        exit(1)
    }
}

let d = Delegate()
d.start()
RunLoop.main.run(until: Date(timeIntervalSinceNow: 10))
exit(1)
"""

_LOCATION_INFO_PLIST = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" \
"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key>
    <string>com.thornjad.stormscope.location</string>
    <key>CFBundleExecutable</key>
    <string>StormscopeLocation</string>
    <key>CFBundleName</key>
    <string>StormscopeLocation</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSLocationUsageDescription</key>
    <string>StormScope uses your location for local weather data.</string>
    <key>NSLocationWhenInUseUsageDescription</key>
    <string>StormScope uses your location for local weather data.</string>
</dict>
</plist>
"""


def _ensure_location_helper() -> Path | None:
    """build the CoreLocation helper .app bundle if needed, return app path."""
    if sys.platform != "darwin":
        return None

    support = Path.home() / "Library" / "Application Support" / "stormscope"
    app_dir = support / "StormscopeLocation.app"
    contents = app_dir / "Contents"
    macos = contents / "MacOS"
    binary = macos / "StormscopeLocation"

    if binary.exists():
        return app_dir

    try:
        macos.mkdir(parents=True, exist_ok=True)
        (contents / "Info.plist").write_text(_LOCATION_INFO_PLIST)
        swift_src = contents / "main.swift"
        swift_src.write_text(_LOCATION_SWIFT_SRC)
        subprocess.run(
            ["swiftc", str(swift_src), "-o", str(binary)],
            check=True,
            capture_output=True,
        )
        swift_src.unlink(missing_ok=True)
        logger.info("compiled CoreLocation helper at %s", app_dir)
        return app_dir
    except Exception:
        logger.debug("failed to build CoreLocation helper", exc_info=True)
        return None


_cl_location: tuple[float, float] | None = None
_cl_location_fetched = False


async def geolocate_corelocation() -> tuple[float, float] | None:
    """locate via compiled macOS CoreLocation helper, cached for server lifetime."""
    global _cl_location, _cl_location_fetched
    if _cl_location_fetched:
        return _cl_location

    _cl_location_fetched = True
    app_path = await asyncio.to_thread(_ensure_location_helper)
    if app_path is None:
        _cl_location = None
        return None

    tmp_fd, tmp_path = tempfile.mkstemp(prefix="stormscope_loc_")
    os.close(tmp_fd)
    try:
        proc = await asyncio.create_subprocess_exec(
            "open", "-W", "--background",
            "--stdout", tmp_path,
            str(app_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=15.0)
        output = Path(tmp_path).read_text().strip()
        lat_s, lon_s = output.split(",")
        _cl_location = (round(float(lat_s), 4), round(float(lon_s), 4))
        logger.info("CoreLocation: %s, %s", lat_s, lon_s)
    except Exception:
        logger.debug("CoreLocation geolocation failed", exc_info=True)
        _cl_location = None
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return _cl_location


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


async def geolocate(
    disabled: bool = False, enable_corelocation: bool = False,
) -> tuple[float, float] | None:
    """resolve location via CoreLocation (if opted in) then IP fallback."""
    if disabled:
        return None
    if enable_corelocation:
        coords = await geolocate_corelocation()
        if coords is not None:
            return coords
    return await geolocate_ip()

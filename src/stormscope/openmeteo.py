"""Open-Meteo API client for upper-air data: 500mb fields and model soundings."""

import asyncio
import logging

from stormscope.base_client import BaseAPIClient

logger = logging.getLogger(__name__)

BASE_URL = "https://api.open-meteo.com"
_TTL = 3600  # 1 hour
_FORECAST_HOURS = 12
_SOUNDING_LEVELS = (1000, 975, 950, 925, 900, 850, 800, 700, 600, 500, 400, 300, 250, 200, 150, 100)
_SOUNDING_VARS = ("temperature", "dew_point", "wind_speed", "wind_direction", "geopotential_height")
_SOUNDING_SURFACE_VARS = (
    "temperature_2m", "dew_point_2m", "surface_pressure",
    "wind_speed_10m", "wind_direction_10m",
)
MAX_SOUNDING_HOURS_AHEAD = 48


class OpenMeteoClient(BaseAPIClient):
    def __init__(self):
        super().__init__(
            headers={"User-Agent": "stormscope"},
            timeout=15.0,
            base_url=BASE_URL,
        )

    async def _fetch_point(self, lat: float, lon: float) -> dict:
        """fetch 500mb data for a single point."""
        client = await self._get_client()
        resp = await client.get(
            "/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "geopotential_height_500hPa,temperature_500hPa,wind_speed_500hPa,wind_direction_500hPa",
                "wind_speed_unit": "ms",
                "forecast_hours": _FORECAST_HOURS,
                "timezone": "UTC",
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def get_upper_air(self, lat: float, lon: float) -> dict:
        """fetch 5-point cross pattern for vorticity computation."""
        async def _fetch():
            points = await asyncio.gather(
                self._fetch_point(lat, lon),
                self._fetch_point(lat + 1, lon),
                self._fetch_point(lat - 1, lon),
                self._fetch_point(lat, lon + 1),
                self._fetch_point(lat, lon - 1),
            )
            return {
                "center": points[0],
                "north": points[1],
                "south": points[2],
                "east": points[3],
                "west": points[4],
            }

        key = f"upper_air:{lat:.4f},{lon:.4f}"
        return await self._cache.get_or_fetch(key, _TTL, _fetch)

    async def get_sounding(self, lat: float, lon: float, hours_ahead: int = 0) -> dict:
        """model sounding at one point as surface-first levels.

        returns {valid, elevation_m, profile}. pressure levels at or below the
        model surface are dropped and replaced by the 2m/10m surface values.
        """
        async def _fetch():
            client = await self._get_client()
            hourly = list(_SOUNDING_SURFACE_VARS) + [
                f"{var}_{level}hPa" for level in _SOUNDING_LEVELS for var in _SOUNDING_VARS
            ]
            resp = await client.get(
                "/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "hourly": ",".join(hourly),
                    "wind_speed_unit": "kn",
                    "forecast_hours": hours_ahead + 1,
                    "timezone": "UTC",
                },
            )
            resp.raise_for_status()
            return _parse_sounding(resp.json(), hours_ahead)

        key = f"sounding:{lat:.2f},{lon:.2f}:{hours_ahead}"
        return await self._cache.get_or_fetch(key, _TTL, _fetch)


def _parse_sounding(data: dict, idx: int) -> dict:
    hourly = data["hourly"]

    def at(name: str):
        series = hourly.get(name)
        return series[idx] if series and idx < len(series) else None

    sfc_p = at("surface_pressure")
    sfc_height = data.get("elevation")
    profile = []
    if None not in (sfc_p, sfc_height):
        profile.append({
            "pressure": sfc_p,
            "height": sfc_height,
            "temp": at("temperature_2m"),
            "dewpoint": at("dew_point_2m"),
            "wind_dir": at("wind_direction_10m"),
            "wind_speed": at("wind_speed_10m"),
        })
    for level in _SOUNDING_LEVELS:
        if sfc_p is not None and level >= sfc_p:
            continue
        profile.append({
            "pressure": float(level),
            "height": at(f"geopotential_height_{level}hPa"),
            "temp": at(f"temperature_{level}hPa"),
            "dewpoint": at(f"dew_point_{level}hPa"),
            "wind_dir": at(f"wind_direction_{level}hPa"),
            "wind_speed": at(f"wind_speed_{level}hPa"),
        })
    return {
        "valid": hourly["time"][idx],
        "elevation_m": sfc_height,
        "profile": profile,
    }

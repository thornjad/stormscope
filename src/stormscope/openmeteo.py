"""Open-Meteo API client for 500mb upper-air data."""

import asyncio
import logging

from stormscope.base_client import BaseAPIClient

logger = logging.getLogger(__name__)

BASE_URL = "https://api.open-meteo.com"
_TTL = 3600  # 1 hour
_FORECAST_HOURS = 12


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

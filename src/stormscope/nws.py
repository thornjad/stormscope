"""Async NWS API client with caching and retry."""

import asyncio
import logging
from urllib.parse import urlparse

import httpx

from stormscope.base_client import BaseAPIClient
from stormscope.config import config

logger = logging.getLogger(__name__)

BASE_URL = "https://api.weather.gov"

_TTL_POINT = 86400       # 24h
_TTL_STATIONS = 86400    # 24h
_TTL_OBSERVATION = 600   # 10min
_TTL_FORECAST = 3600     # 1h
_TTL_ALERTS = 120        # 2min
_TTL_GRIDPOINT = 1800    # 30min

_MAX_RETRIES = 3
_RATE_LIMIT_WAIT = 5.0
_UNITS_PARAM = "si" if config.units == "si" else "us"


class NWSClient(BaseAPIClient):
    def __init__(self):
        super().__init__(
            headers={
                "User-Agent": config.user_agent,
                "Accept": "application/geo+json",
            },
            timeout=30.0,
            base_url=BASE_URL,
            follow_redirects=True,
        )

    _ALLOWED_HOSTS = {"api.weather.gov"}

    async def _request(self, url: str) -> dict:
        """Make a GET request with retry logic for 5xx and rate limits."""
        if url.startswith("http"):
            host = urlparse(url).hostname
            if host not in self._ALLOWED_HOSTS:
                raise ValueError(f"request to disallowed host: {host}")
        client = await self._get_client()

        for attempt in range(_MAX_RETRIES):
            try:
                resp = await client.get(url)

                if resp.status_code == 429:
                    logger.warning("rate limited, waiting %ss", _RATE_LIMIT_WAIT)
                    await asyncio.sleep(_RATE_LIMIT_WAIT)
                    continue

                if resp.status_code >= 500:
                    wait = 2 ** attempt
                    logger.warning(
                        "server error %s, retry %d/%d in %ss",
                        resp.status_code, attempt + 1, _MAX_RETRIES, wait,
                    )
                    await asyncio.sleep(wait)
                    continue

                resp.raise_for_status()
                return resp.json()

            except httpx.HTTPStatusError:
                raise
            except httpx.HTTPError as exc:
                if attempt < _MAX_RETRIES - 1:
                    wait = 2 ** attempt
                    logger.warning("request error: %s, retry in %ss", exc, wait)
                    await asyncio.sleep(wait)
                else:
                    raise

        raise httpx.HTTPStatusError(
            "max retries exceeded",
            request=httpx.Request("GET", url),
            response=httpx.Response(503),
        )

    async def get_point(self, lat: float, lon: float) -> dict:
        """Fetch grid point metadata for a lat/lon pair."""
        key = f"point:{lat},{lon}"
        cached, is_stale = await self._cache.get(key)
        if cached is not None and not is_stale:
            return cached

        try:
            url = f"/points/{lat},{lon}"
            data = await self._request(url)
            props = data["properties"]
            await self._cache.set(key, props, _TTL_POINT)
            return props
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise ValueError(
                    "location not supported — NWS only covers US territories"
                ) from exc
            if cached is not None:
                return cached
            raise
        except Exception:
            if cached is not None:
                return cached
            raise

    async def get_stations(self, url: str) -> list[dict]:
        """Fetch station list from a points-provided URL."""
        async def _fetch():
            data = await self._request(url)
            return [f["properties"] for f in data.get("features", [])]
        return await self._cache.get_or_fetch(f"stations:{url}", _TTL_STATIONS, _fetch)

    async def get_latest_observation(self, station_id: str) -> dict:
        """Fetch latest observation for a station."""
        async def _fetch():
            data = await self._request(f"/stations/{station_id}/observations/latest")
            return data["properties"]
        return await self._cache.get_or_fetch(f"obs:{station_id}", _TTL_OBSERVATION, _fetch)

    async def get_forecast(self, wfo: str, x: int, y: int) -> dict:
        """Fetch standard forecast for a grid point."""
        async def _fetch():
            data = await self._request(f"/gridpoints/{wfo}/{x},{y}/forecast?units={_UNITS_PARAM}")
            return data["properties"]
        return await self._cache.get_or_fetch(f"fcst:{wfo},{x},{y}", _TTL_FORECAST, _fetch)

    async def get_hourly_forecast(self, wfo: str, x: int, y: int) -> dict:
        """Fetch hourly forecast for a grid point."""
        async def _fetch():
            data = await self._request(f"/gridpoints/{wfo}/{x},{y}/forecast/hourly?units={_UNITS_PARAM}")
            return data["properties"]
        return await self._cache.get_or_fetch(f"hrly:{wfo},{x},{y}", _TTL_FORECAST, _fetch)

    async def get_alerts(self, lat: float, lon: float) -> dict:
        """Fetch active alerts for a point."""
        async def _fetch():
            return await self._request(f"/alerts/active?point={lat},{lon}")
        return await self._cache.get_or_fetch(f"alerts:{lat},{lon}", _TTL_ALERTS, _fetch)

    async def get_detailed_forecast(self, wfo: str, x: int, y: int) -> dict:
        """Fetch raw gridpoint time-value series."""
        async def _fetch():
            data = await self._request(f"/gridpoints/{wfo}/{x},{y}")
            return data["properties"]
        return await self._cache.get_or_fetch(f"grid:{wfo},{x},{y}", _TTL_GRIDPOINT, _fetch)

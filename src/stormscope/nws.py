"""Async NWS API client with caching and retry."""

import asyncio
import logging

import httpx

from stormscope.cache import TTLCache
from stormscope.config import config

logger = logging.getLogger(__name__)

BASE_URL = "https://api.weather.gov"

_TTL_POINT = 86400      # 24h
_TTL_OBSERVATION = 600  # 10min
_TTL_FORECAST = 3600    # 1h
_TTL_ALERTS = 120       # 2min
_TTL_GRIDPOINT = 1800   # 30min

_MAX_RETRIES = 3
_RATE_LIMIT_WAIT = 5.0


class NWSClient:
    def __init__(self):
        self._cache = TTLCache()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=BASE_URL,
                headers={
                    "User-Agent": config.user_agent,
                    "Accept": "application/geo+json",
                },
                timeout=30.0,
            )
        return self._client

    async def _request(self, url: str) -> dict:
        """Make a GET request with retry logic for 5xx and rate limits."""
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
        data = await self._request(url)
        return [f["properties"] for f in data.get("features", [])]

    async def get_latest_observation(self, station_id: str) -> dict:
        """Fetch latest observation for a station."""
        key = f"obs:{station_id}"
        cached, is_stale = await self._cache.get(key)
        if cached is not None and not is_stale:
            return cached

        try:
            url = f"/stations/{station_id}/observations/latest"
            data = await self._request(url)
            props = data["properties"]
            await self._cache.set(key, props, _TTL_OBSERVATION)
            return props
        except Exception:
            if cached is not None:
                return cached
            raise

    async def get_forecast(self, wfo: str, x: int, y: int) -> dict:
        """Fetch standard forecast for a grid point."""
        key = f"fcst:{wfo},{x},{y}"
        cached, is_stale = await self._cache.get(key)
        if cached is not None and not is_stale:
            return cached

        try:
            url = f"/gridpoints/{wfo}/{x},{y}/forecast?units=us"
            data = await self._request(url)
            result = data["properties"]
            await self._cache.set(key, result, _TTL_FORECAST)
            return result
        except Exception:
            if cached is not None:
                return cached
            raise

    async def get_hourly_forecast(self, wfo: str, x: int, y: int) -> dict:
        """Fetch hourly forecast for a grid point."""
        key = f"hrly:{wfo},{x},{y}"
        cached, is_stale = await self._cache.get(key)
        if cached is not None and not is_stale:
            return cached

        try:
            url = f"/gridpoints/{wfo}/{x},{y}/forecast/hourly?units=us"
            data = await self._request(url)
            result = data["properties"]
            await self._cache.set(key, result, _TTL_FORECAST)
            return result
        except Exception:
            if cached is not None:
                return cached
            raise

    async def get_alerts(self, lat: float, lon: float) -> dict:
        """Fetch active alerts for a point."""
        key = f"alerts:{lat},{lon}"
        cached, is_stale = await self._cache.get(key)
        if cached is not None and not is_stale:
            return cached

        try:
            url = f"/alerts/active?point={lat},{lon}"
            data = await self._request(url)
            await self._cache.set(key, data, _TTL_ALERTS)
            return data
        except Exception:
            if cached is not None:
                return cached
            raise

    async def get_detailed_forecast(
        self, wfo: str, x: int, y: int, parameters: list[str] | None = None, hours: int = 48,
    ) -> dict:
        """Fetch raw gridpoint time-value series."""
        key = f"grid:{wfo},{x},{y}"
        cached, is_stale = await self._cache.get(key)
        if cached is not None and not is_stale:
            return cached

        try:
            url = f"/gridpoints/{wfo}/{x},{y}"
            data = await self._request(url)
            result = data["properties"]
            await self._cache.set(key, result, _TTL_GRIDPOINT)
            return result
        except Exception:
            if cached is not None:
                return cached
            raise

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.close()

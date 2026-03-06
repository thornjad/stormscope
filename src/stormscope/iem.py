"""IEM radar metadata: products, latest scans, and imagery URLs."""

import logging
from datetime import datetime, timedelta, timezone

import httpx

from stormscope.cache import TTLCache

logger = logging.getLogger(__name__)

IEM_BASE = "https://mesonet.agron.iastate.edu"
_CACHE_TTL = 300  # 5 minutes


class IEMClient:
    def __init__(self):
        self._cache = TTLCache()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": "stormscope"},
                timeout=15.0,
            )
        return self._client

    async def _request(self, url: str) -> dict:
        client = await self._get_client()
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()

    def _iem_site(self, station_id: str) -> str:
        """strip leading K from 4-letter radar ID for IEM queries."""
        if len(station_id) == 4 and station_id.startswith("K"):
            return station_id[1:]
        return station_id

    def _imagery_urls(self, site: str) -> dict[str, str]:
        return {
            "composite_url": f"{IEM_BASE}/data/gis/images/4326/USCOMP/n0r_0.png",
            "site_url": f"{IEM_BASE}/data/gis/images/4326/ridge/{site}/N0B/",
            "tile_url_template": (
                f"{IEM_BASE}/cache/tile.py/1.0.0/ridge::{site}-N0B-0"
                "/{z}/{x}/{y}.png"
            ),
        }

    async def _fetch_products(self, site: str, start_iso: str) -> list[str]:
        url = (
            f"{IEM_BASE}/json/radar.py"
            f"?operation=products&radar={site}&start={start_iso}"
        )
        data = await self._request(url)
        raw = data.get("products", [])
        if raw and isinstance(raw[0], dict):
            return [p["id"] for p in raw if "id" in p]
        return raw

    async def _fetch_latest_scan(
        self, site: str, start_iso: str, end_iso: str,
    ) -> str | None:
        url = (
            f"{IEM_BASE}/json/radar.py"
            f"?operation=list&radar={site}&product=N0B"
            f"&start={start_iso}&end={end_iso}"
        )
        data = await self._request(url)
        scans = data.get("scans", [])
        if not scans:
            return None
        return scans[-1].get("ts")

    async def get_radar_info(self, radar_station: str) -> dict:
        """Get radar metadata for a station ID."""
        key = f"radar:{radar_station}"
        cached, is_stale = await self._cache.get(key)
        if cached is not None and not is_stale:
            return cached

        site = self._iem_site(radar_station)
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=1)
        start_iso = start.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            products = await self._fetch_products(site, start_iso)
            latest_scan = await self._fetch_latest_scan(site, start_iso, end_iso)

            result = {
                "station_id": radar_station,
                "available_products": products,
                "latest_scan_time": latest_scan,
                "imagery_urls": self._imagery_urls(site),
            }
            await self._cache.set(key, result, _CACHE_TTL)
            return result

        except Exception:
            logger.warning("IEM request failed for %s", radar_station, exc_info=True)
            if cached is not None:
                return {**cached, "_stale": True, "_stale_reason": "source unavailable"}

            return {
                "station_id": radar_station,
                "available_products": [],
                "latest_scan_time": None,
                "imagery_urls": self._imagery_urls(site),
                "_stale": True,
                "_stale_reason": "iem api unavailable",
            }

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.close()

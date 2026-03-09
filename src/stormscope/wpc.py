"""NOAA Weather Prediction Center surface analysis client."""

import asyncio
import logging

import httpx

from stormscope.base_client import BaseAPIClient
from stormscope.config import config

logger = logging.getLogger(__name__)

WPC_BASE = "https://mapservices.weather.noaa.gov/vector/rest/services/outlooks/natl_fcst_wx_chart/MapServer"

# (pressure_centers_layer, fronts_layer) per forecast day
_DAY_LAYERS: dict[int, tuple[int, int]] = {
    1: (1, 2),
    2: (13, 14),
    3: (25, 26),
}

_TTL = 1800  # 30min

FRONT_TYPES = {
    "Cold Front Valid": "cold",
    "Warm Front Valid": "warm",
    "Stationary Front Valid": "stationary",
    "Occluded Front Valid": "occluded",
    "Trough Valid": "trough",
}

CENTER_TYPES = {
    "High Valid": "high",
    "Low Valid": "low",
}


class WPCClient(BaseAPIClient):
    def __init__(self):
        super().__init__(
            headers={"User-Agent": config.user_agent},
            timeout=30.0,
        )

    async def _fetch_layer(self, layer_id: int) -> dict:
        client = await self._get_client()
        url = f"{WPC_BASE}/{layer_id}/query"
        resp = await client.get(url, params={
            "where": "1=1",
            "outFields": "*",
            "f": "geojson",
            "inSR": "4326",
        })
        resp.raise_for_status()
        if not resp.content:
            return {"type": "FeatureCollection", "features": []}
        data = resp.json()
        if data.get("exceededTransferLimit"):
            logger.warning("WPC response was truncated by ArcGIS transfer limit")
        return data

    async def get_fronts(self, day: int = 1) -> dict:
        layers = _DAY_LAYERS.get(day)
        if layers is None:
            return {"type": "FeatureCollection", "features": []}
        _, fronts_layer = layers
        return await self._cache.get_or_fetch(
            f"wpc_fronts_day{day}", _TTL, lambda: self._fetch_layer(fronts_layer),
        )

    async def get_pressure_centers(self, day: int = 1) -> dict:
        layers = _DAY_LAYERS.get(day)
        if layers is None:
            return {"type": "FeatureCollection", "features": []}
        centers_layer, _ = layers
        return await self._cache.get_or_fetch(
            f"wpc_centers_day{day}", _TTL, lambda: self._fetch_layer(centers_layer),
        )

    async def get_surface_analysis(self, day: int = 1) -> tuple[dict, dict]:
        fronts, centers = await asyncio.gather(
            self.get_fronts(day),
            self.get_pressure_centers(day),
        )
        return fronts, centers

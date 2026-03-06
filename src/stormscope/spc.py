"""NOAA Storm Prediction Center outlook client."""

import asyncio
import logging

import httpx
from shapely.geometry import Point, shape

from stormscope.cache import TTLCache
from stormscope.config import config

logger = logging.getLogger(__name__)

SPC_BASE = "https://www.spc.noaa.gov/products/outlook"
SPC_OUTLOOK_URL = f"{SPC_BASE}/day{{day}}otlk_cat.nolyr.geojson"
SPC_PROB_URL = f"{SPC_BASE}/day{{day}}otlk_{{hazard}}_prob.nolyr.geojson"

_TTL_DAY1 = 900    # 15min
_TTL_DAY2_3 = 1800  # 30min

RISK_LEVELS: dict[int, tuple[str, str, bool]] = {
    2: ("TSTM", "General thunderstorm risk", False),
    3: ("MRGL", "Marginal Risk - isolated severe storms possible", False),
    4: ("SLGT", "Slight Risk - scattered severe storms possible", False),
    5: ("ENH", "Enhanced Risk - numerous severe storms possible", True),
    6: ("MDT", "Moderate Risk - widespread severe storms expected", True),
    8: ("HIGH", "High Risk - widespread severe storms with potential for long-lived intense events", True),
}

NO_RISK = ("NONE", "No severe weather risk", False)


def _cache_ttl(day: int) -> float:
    return _TTL_DAY1 if day == 1 else _TTL_DAY2_3


class SPCClient:
    def __init__(self):
        self._cache = TTLCache()
        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        async with self._client_lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(
                    headers={"User-Agent": config.user_agent},
                    timeout=30.0,
                )
            return self._client

    async def _fetch_geojson(self, url: str) -> dict:
        client = await self._get_client()
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def get_categorical_outlook(self, day: int = 1) -> dict:
        cache_key = f"spc_cat_day{day}"
        cached, is_stale = await self._cache.get(cache_key)
        if cached is not None and not is_stale:
            return cached

        try:
            url = SPC_OUTLOOK_URL.format(day=day)
            data = await self._fetch_geojson(url)
            await self._cache.set(cache_key, data, _cache_ttl(day))
            return data
        except Exception:
            if cached is not None:
                return cached
            raise

    async def get_probabilistic_outlook(self, day: int, hazard: str) -> dict:
        """Fetch probabilistic outlook for a specific hazard type."""
        cache_key = f"spc_prob_{hazard}_day{day}"
        cached, is_stale = await self._cache.get(cache_key)
        if cached is not None and not is_stale:
            return cached

        try:
            url = SPC_PROB_URL.format(day=day, hazard=hazard)
            data = await self._fetch_geojson(url)
            await self._cache.set(cache_key, data, _cache_ttl(day))
            return data
        except Exception:
            if cached is not None:
                return cached
            raise

    async def fetch_outlook(self, day: int, outlook_type: str) -> dict:
        """Unified fetch for categorical or probabilistic outlook."""
        if outlook_type == "categorical":
            return await self.get_categorical_outlook(day)
        return await self.get_probabilistic_outlook(day, outlook_type)

    async def check_risk_for_point(self, lat: float, lon: float, day: int = 1) -> dict:
        """Check categorical risk level for a point (backward-compatible)."""
        try:
            outlook = await self.get_categorical_outlook(day)
        except Exception as exc:
            return {"error": f"Failed to fetch SPC outlook: {exc}"}

        return self._point_in_categorical(outlook, lat, lon, day)

    async def get_spc_outlook(
        self, lat: float, lon: float, day: int, outlook_type: str,
    ) -> dict:
        """Fetch outlook and check point-in-polygon for categorical or probabilistic."""
        try:
            data = await self.fetch_outlook(day, outlook_type)
        except Exception as exc:
            return {"error": f"Failed to fetch SPC {outlook_type} outlook: {exc}"}

        if outlook_type == "categorical":
            return self._point_in_categorical(data, lat, lon, day)
        return self._point_in_probabilistic(data, lat, lon, day, outlook_type)

    def _point_in_categorical(self, outlook: dict, lat: float, lon: float, day: int) -> dict:
        point = Point(lon, lat)
        best_dn = 0
        valid_time = None
        expire_time = None

        for feature in outlook.get("features", []):
            dn = feature.get("properties", {}).get("DN", 0)
            try:
                polygon = shape(feature["geometry"])
            except Exception:
                continue
            if point.within(polygon) and dn > best_dn:
                best_dn = dn
                valid_time = feature["properties"].get("VALID")
                expire_time = feature["properties"].get("EXPIRE")

        label, description, significant = RISK_LEVELS.get(best_dn, NO_RISK)

        return {
            "risk_level": label,
            "risk_description": description,
            "valid_time": valid_time,
            "expire_time": expire_time,
            "is_significant": significant,
            "day": day,
        }

    def _point_in_probabilistic(
        self, data: dict, lat: float, lon: float, day: int, hazard: str,
    ) -> dict:
        point = Point(lon, lat)
        best_prob = 0
        significant = False
        valid_time = None
        expire_time = None

        for feature in data.get("features", []):
            props = feature.get("properties", {})
            try:
                polygon = shape(feature["geometry"])
            except Exception:
                continue
            if not point.within(polygon):
                continue

            label = props.get("LABEL", "")
            if label == "SIGN":
                significant = True
                continue

            try:
                prob = int(label)
            except (ValueError, TypeError):
                continue
            if prob > best_prob:
                best_prob = prob
                valid_time = props.get("VALID")
                expire_time = props.get("EXPIRE")

        return {
            "hazard": hazard,
            "probability": best_prob,
            "significant": significant,
            "valid_time": valid_time,
            "expire_time": expire_time,
            "day": day,
        }

    async def get_national_outlook_summary(self, day: int) -> dict:
        """Iterate all categorical features and describe regions."""
        from stormscope.geo import polygon_to_region

        try:
            outlook = await self.get_categorical_outlook(day)
        except Exception as exc:
            return {"error": f"Failed to fetch SPC outlook: {exc}"}

        areas = []
        for feature in outlook.get("features", []):
            props = feature.get("properties", {})
            dn = props.get("DN", 0)
            label, description, significant = RISK_LEVELS.get(dn, NO_RISK)
            if label == "NONE":
                continue

            try:
                polygon = shape(feature["geometry"])
                region = polygon_to_region(polygon)
            except Exception:
                region = "unknown region"

            areas.append({
                "risk_level": label,
                "risk_description": description,
                "region": region,
                "is_significant": significant,
            })

        return {
            "day": day,
            "areas": areas,
            "valid_time": outlook.get("features", [{}])[0].get("properties", {}).get("VALID") if outlook.get("features") else None,
        }

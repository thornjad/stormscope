"""IEM RAOB client: radiosonde station list and observed soundings."""

import logging
from datetime import datetime, timedelta, timezone

from stormscope.base_client import BaseAPIClient
from stormscope.geo import haversine_km
from stormscope.iem import IEM_BASE

logger = logging.getLogger(__name__)

_STATIONS_TTL = 86400  # 24 hours
_SOUNDING_TTL = 10800  # 3 hours; a published sounding never changes
_LAUNCH_HOURS = (0, 12)
_PUBLISH_LAG = timedelta(minutes=90)
_MAX_CANDIDATE_STATIONS = 3
_CYCLES_PER_STATION = 2


def _latest_cycles(now: datetime, count: int) -> list[datetime]:
    """most recent synoptic launch times that should be published, newest first."""
    t = (now - _PUBLISH_LAG).replace(minute=0, second=0, microsecond=0)
    cycles: list[datetime] = []
    while len(cycles) < count:
        if t.hour in _LAUNCH_HOURS:
            cycles.append(t)
        t -= timedelta(hours=1)
    return cycles


class RAOBClient(BaseAPIClient):
    def __init__(self):
        super().__init__(
            headers={"User-Agent": "stormscope"},
            timeout=20.0,
            base_url=IEM_BASE,
        )

    async def get_stations(self) -> list[dict]:
        """active radiosonde sites. IEM also lists retired sites and `_XXX` area aggregates."""
        async def _fetch():
            client = await self._get_client()
            resp = await client.get("/geojson/network/RAOB.geojson")
            resp.raise_for_status()
            stations = []
            for feat in resp.json().get("features", []):
                props = feat.get("properties", {})
                sid = feat.get("id", "")
                if sid.startswith("_") or not props.get("online") or props.get("archive_end"):
                    continue
                lon, lat = feat["geometry"]["coordinates"][:2]
                stations.append({
                    "id": sid,
                    "name": " ".join(props.get("sname", "").split()),
                    "lat": lat,
                    "lon": lon,
                    "elevation_m": props.get("elevation"),
                    "country": props.get("country"),
                })
            return stations

        return await self._cache.get_or_fetch("raob_stations", _STATIONS_TTL, _fetch)

    async def nearest_stations(
        self, lat: float, lon: float, count: int = _MAX_CANDIDATE_STATIONS,
    ) -> list[tuple[float, dict]]:
        """(distance_km, station) pairs, nearest first."""
        stations = await self.get_stations()
        ranked = sorted(
            ((haversine_km(lat, lon, s["lat"], s["lon"]), s) for s in stations),
            key=lambda pair: pair[0],
        )
        return ranked[:count]

    async def get_profile(self, station_id: str, valid: datetime) -> list[dict] | None:
        """one sounding as surface-first levels, or None if not (yet) published."""
        async def _fetch():
            client = await self._get_client()
            resp = await client.get(
                "/json/raob.py",
                params={"station": station_id, "ts": valid.strftime("%Y%m%d%H%M")},
            )
            resp.raise_for_status()
            profiles = resp.json().get("profiles", [])
            if not profiles or not profiles[0].get("profile"):
                return None
            return [
                {
                    "pressure": lv.get("pres"),
                    "height": lv.get("hght"),
                    "temp": lv.get("tmpc"),
                    "dewpoint": lv.get("dwpc"),
                    "wind_dir": lv.get("drct"),
                    "wind_speed": lv.get("sknt"),
                }
                for lv in profiles[0]["profile"]
            ]

        key = f"raob:{station_id}:{valid:%Y%m%d%H}"
        return await self._cache.get_or_fetch(key, _SOUNDING_TTL, _fetch)

    async def get_latest(
        self, lat: float, lon: float, station_id: str | None = None,
    ) -> dict | None:
        """latest available sounding from the nearest site (or a named one).

        walks the nearest few stations, trying the newest cycle first at each, and
        returns the first hit as {station, distance_km, valid, profile}.
        """
        if station_id:
            stations = await self.get_stations()
            wanted = station_id.upper()
            match = next(
                (s for s in stations if s["id"] == wanted or s["id"] == f"K{wanted}"),
                None,
            )
            if match is None:
                raise ValueError(f"unknown radiosonde station: {station_id}")
            candidates = [(haversine_km(lat, lon, match["lat"], match["lon"]), match)]
        else:
            candidates = await self.nearest_stations(lat, lon)

        cycles = _latest_cycles(datetime.now(timezone.utc), _CYCLES_PER_STATION)
        for dist_km, station in candidates:
            for valid in cycles:
                try:
                    profile = await self.get_profile(station["id"], valid)
                except Exception:
                    logger.warning(
                        "RAOB fetch failed for %s %s", station["id"], valid, exc_info=True,
                    )
                    continue
                if profile:
                    return {
                        "station": station,
                        "distance_km": dist_km,
                        "valid": valid,
                        "profile": profile,
                    }
        return None

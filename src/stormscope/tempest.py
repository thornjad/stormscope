"""Tempest WeatherFlow station client."""

import logging

from stormscope.base_client import BaseAPIClient
from stormscope.geo import haversine_km, KM_PER_MI
from stormscope.units import UnitPrefs, c_to_f, ms_to_mph, ms_to_kt, pa_to_inhg

# sentinel for caching None (no station found / too far away)
_CACHE_MISS = object()

logger = logging.getLogger(__name__)

_STATION_MAX_DIST_KM = 5.0 * KM_PER_MI  # 5 miles in km

_WIND_UNIT_MAP = {
    "mph": "mph",
    "kt": "kts",
    "kmh": "kph",
    "ms": "mps",
}

_TEMP_UNIT_MAP = {
    "f": "f",
    "c": "c",
}

_PRESSURE_UNIT_MAP = {
    "inhg": "inhg",
    "mb": "mb",
}

_PRECIP_UNIT_MAP = {
    "in": "in",
    "mm": "mm",
    "cm": "mm",  # tempest has no cm; use mm
}

_DISTANCE_UNIT_MAP = {
    "mi": "mi",
    "km": "km",
}


class TempestClient(BaseAPIClient):
    def __init__(self, token: str):
        super().__init__(
            headers={},
            timeout=15.0,
            base_url="https://swd.weatherflow.com/swd/rest",
        )
        self._token = token

    async def _request(self, path: str, params: dict | None = None) -> dict:
        merged = {"token": self._token}
        if params:
            merged.update(params)
        client = await self._get_client()
        resp = await client.get(path, params=merged)
        resp.raise_for_status()
        return resp.json()

    async def get_stations(self) -> list[dict]:
        """fetch all stations for this token. cached 24h."""
        async def _fetch():
            data = await self._request("/stations")
            return data.get("stations", [])
        return await self._cache.get_or_fetch("stations", 86400, _fetch)

    async def resolve_station(
        self,
        lat: float,
        lon: float,
        station_id: int | None = None,
        station_name: str | None = None,
        bypass_distance_check: bool = False,
    ) -> dict | None:
        """resolve a station by id, name, or proximity.

        all paths apply the 5-mile proximity gate. for explicit id/name
        resolution, a warning is logged when the station is too far (so the
        user knows their configured station is not being used). for proximity
        resolution, the miss is silent. pass bypass_distance_check=True to
        skip the gate entirely (used when fetching the station's own location).
        """
        cache_key = f"resolved_station:{station_id}:{station_name}:{lat:.4f}:{lon:.4f}"
        cached, is_stale = await self._cache.get(cache_key)
        if cached is not None and not is_stale:
            return None if cached is _CACHE_MISS else cached

        stations = await self.get_stations()
        station = None
        explicit = station_id is not None or station_name is not None

        if station_id is not None:
            for s in stations:
                if s.get("station_id") == station_id:
                    station = s
                    break
        elif station_name is not None:
            name_lower = station_name.lower()
            for s in stations:
                if (s.get("name", "").lower() == name_lower or
                        s.get("public_name", "").lower() == name_lower):
                    station = s
                    break
        else:
            best_dist = float("inf")
            for s in stations:
                slat = s.get("latitude")
                slon = s.get("longitude")
                if slat is None or slon is None:
                    continue
                d = haversine_km(lat, lon, slat, slon)
                if d < best_dist:
                    best_dist = d
                    station = s

        # apply proximity gate to all resolution paths
        if station is not None and not bypass_distance_check:
            slat = station.get("latitude")
            slon = station.get("longitude")
            if slat is not None and slon is not None:
                dist_km = haversine_km(lat, lon, slat, slon)
                if dist_km > _STATION_MAX_DIST_KM:
                    if explicit:
                        logger.warning(
                            "configured tempest station is %.1f km away "
                            "(limit: %.1f km); Tempest enrichment disabled "
                            "for this location",
                            dist_km, _STATION_MAX_DIST_KM,
                        )
                    else:
                        logger.debug(
                            "nearest tempest station %.1f km away, exceeds limit",
                            dist_km,
                        )
                    await self._cache.set(cache_key, _CACHE_MISS, ttl_seconds=3600)
                    return None

        if station is None:
            await self._cache.set(cache_key, _CACHE_MISS, ttl_seconds=3600)
            return None

        await self._cache.set(cache_key, station, ttl_seconds=3600)
        return station

    async def get_observations(self, station_id: int) -> dict | None:
        """fetch latest observation for a station. cached 2 min. returns None if no obs."""
        async def _fetch():
            data = await self._request(f"/observations/station/{station_id}")
            obs_list = data.get("obs", [])
            if not obs_list:
                return None
            station_units = data.get("station_units", {})
            result = dict(obs_list[0])
            result["_station_units"] = station_units
            return result
        return await self._cache.get_or_fetch(f"obs:{station_id}", 120, _fetch)

    async def get_forecast(self, station_id: int, prefs: UnitPrefs) -> dict:
        """fetch better_forecast for a station with unit params. cached 30 min."""
        cache_key = (
            f"forecast:{station_id}:{prefs.temperature}:{prefs.wind}:"
            f"{prefs.pressure}:{prefs.accumulation}:{prefs.distance}"
        )
        async def _fetch():
            params = {
                "station_id": station_id,
                "units_temp": _TEMP_UNIT_MAP.get(prefs.temperature, "f"),
                "units_wind": _WIND_UNIT_MAP.get(prefs.wind, "mph"),
                "units_pressure": _PRESSURE_UNIT_MAP.get(prefs.pressure, "inhg"),
                "units_precip": _PRECIP_UNIT_MAP.get(prefs.accumulation, "in"),
                "units_distance": _DISTANCE_UNIT_MAP.get(prefs.distance, "mi"),
            }
            return await self._request("/better_forecast", params=params)
        return await self._cache.get_or_fetch(cache_key, 1800, _fetch)

    def normalize_obs(self, obs: dict, prefs: UnitPrefs) -> dict:
        """convert observation values to user's preferred units.

        The Tempest API returns observations in SI (metric) units by default:
        air_temperature: °C, wind_avg/gust/lull: m/s, station_pressure: mb.
        The _station_units dict indicates actual units.
        """
        result = dict(obs)
        station_units = obs.get("_station_units", {})

        temp_unit = station_units.get("units_temp", "c")
        wind_unit = station_units.get("units_wind", "mps")

        # normalize temperature fields
        for field in ("air_temperature", "wet_bulb_temperature", "feels_like",
                      "dew_point", "air_temperature_high", "air_temperature_low"):
            val = obs.get(field)
            if val is None:
                continue
            # convert to celsius first if needed
            temp_c = val if temp_unit == "c" else (val - 32) * 5 / 9
            if prefs.temperature == "f":
                result[field] = c_to_f(temp_c)
            else:
                result[field] = temp_c

        # normalize wind fields
        for field in ("wind_avg", "wind_gust", "wind_lull"):
            val = obs.get(field)
            if val is None:
                continue
            # convert to m/s first
            if wind_unit == "mps":
                ms = val
            elif wind_unit == "mph":
                ms = val / 2.236936
            elif wind_unit == "kph":
                ms = val / 3.6
            else:
                ms = val

            if prefs.wind == "mph":
                result[field] = ms_to_mph(ms)
            elif prefs.wind == "kt":
                result[field] = ms_to_kt(ms)
            elif prefs.wind == "kmh":
                result[field] = ms * 3.6
            else:
                result[field] = ms

        # normalize pressure
        press_unit = station_units.get("units_pressure", "mb")
        val = obs.get("station_pressure")
        if val is not None:
            # convert to Pa first
            if press_unit == "mb":
                pa = val * 100
            elif press_unit == "inhg":
                pa = val * 3386.389
            else:
                pa = val
            if prefs.pressure == "inhg":
                result["station_pressure"] = pa_to_inhg(pa)
            else:
                result["station_pressure"] = pa / 100  # mb

        return result

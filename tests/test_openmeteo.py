"""Tests for Open-Meteo client."""

import httpx
import pytest
import respx

from stormscope.openmeteo import BASE_URL, OpenMeteoClient


def _mock_point_response(lat: float, lon: float) -> dict:
    return {
        "latitude": lat,
        "longitude": lon,
        "hourly": {
            "time": [f"2026-03-09T{h:02d}:00" for h in range(12)],
            "geopotential_height_500hPa": [5520.0 + i for i in range(12)],
            "temperature_500hPa": [-22.0 + i * 0.1 for i in range(12)],
            "wind_speed_500hPa": [20.0 + i * 0.5 for i in range(12)],
            "wind_direction_500hPa": [250.0] * 12,
        },
    }


class TestFetchPoint:
    @respx.mock
    async def test_fetch_point(self):
        client = OpenMeteoClient()
        try:
            mock_data = _mock_point_response(44.98, -93.27)
            respx.get(f"{BASE_URL}/v1/forecast").mock(
                return_value=httpx.Response(200, json=mock_data),
            )

            result = await client._fetch_point(44.98, -93.27)
            assert result["latitude"] == 44.98
            assert "hourly" in result
            assert len(result["hourly"]["time"]) == 12
            assert len(result["hourly"]["geopotential_height_500hPa"]) == 12
        finally:
            await client.close()


class TestGetUpperAir:
    @respx.mock
    async def test_returns_five_points(self):
        client = OpenMeteoClient()
        try:
            respx.get(f"{BASE_URL}/v1/forecast").mock(
                side_effect=lambda request: httpx.Response(
                    200,
                    json=_mock_point_response(
                        float(request.url.params["latitude"]),
                        float(request.url.params["longitude"]),
                    ),
                ),
            )

            result = await client.get_upper_air(44.98, -93.27)

            assert set(result.keys()) == {"center", "north", "south", "east", "west"}
            assert result["center"]["latitude"] == 44.98
            assert result["north"]["latitude"] == 45.98
            assert result["south"]["latitude"] == 43.98
            assert len(respx.calls) == 5
        finally:
            await client.close()

    @respx.mock
    async def test_caching(self):
        client = OpenMeteoClient()
        try:
            respx.get(f"{BASE_URL}/v1/forecast").mock(
                side_effect=lambda request: httpx.Response(
                    200,
                    json=_mock_point_response(
                        float(request.url.params["latitude"]),
                        float(request.url.params["longitude"]),
                    ),
                ),
            )

            await client.get_upper_air(44.98, -93.27)
            assert len(respx.calls) == 5

            await client.get_upper_air(44.98, -93.27)
            assert len(respx.calls) == 5  # no new calls
        finally:
            await client.close()

    @respx.mock
    async def test_stale_fallback(self):
        client = OpenMeteoClient()
        try:
            respx.get(f"{BASE_URL}/v1/forecast").mock(
                side_effect=lambda request: httpx.Response(
                    200,
                    json=_mock_point_response(
                        float(request.url.params["latitude"]),
                        float(request.url.params["longitude"]),
                    ),
                ),
            )

            # prime the cache
            result1 = await client.get_upper_air(44.98, -93.27)

            # expire the cache entry manually
            key = "upper_air:44.9800,-93.2700"
            async with client._cache._lock:
                if key in client._cache._store:
                    _, value = client._cache._store[key]
                    client._cache._store[key] = (0.0, value)  # expired

            # make API fail
            respx.get(f"{BASE_URL}/v1/forecast").mock(
                return_value=httpx.Response(500),
            )

            # should return stale data
            result2 = await client.get_upper_air(44.98, -93.27)
            assert result2["center"]["latitude"] == result1["center"]["latitude"]
        finally:
            await client.close()


def _mock_sounding_response(elevation=300.0, sfc_p=970.0, hours=2) -> dict:
    hourly = {
        "time": [f"2026-09-20T{h:02d}:00" for h in range(17, 17 + hours)],
        "surface_pressure": [sfc_p] * hours,
        "temperature_2m": [30.0] * hours,
        "dew_point_2m": [18.0] * hours,
        "wind_speed_10m": [8.0] * hours,
        "wind_direction_10m": [200] * hours,
    }
    for level in (1000, 975, 950, 925, 900, 850, 800, 700, 600, 500, 400, 300, 250, 200, 150, 100):
        hourly[f"temperature_{level}hPa"] = [20.0 - (1000 - level) / 30] * hours
        hourly[f"dew_point_{level}hPa"] = [10.0 - (1000 - level) / 30] * hours
        hourly[f"wind_speed_{level}hPa"] = [15.0] * hours
        hourly[f"wind_direction_{level}hPa"] = [250] * hours
        hourly[f"geopotential_height_{level}hPa"] = [(1000 - level) * 10.0 + 100] * hours
    return {"elevation": elevation, "hourly": hourly}


class TestGetSounding:
    @respx.mock
    async def test_surface_first_and_below_ground_levels_dropped(self):
        respx.get(f"{BASE_URL}/v1/forecast").mock(
            return_value=httpx.Response(200, json=_mock_sounding_response(sfc_p=970.0)),
        )
        client = OpenMeteoClient()
        try:
            result = await client.get_sounding(35.2, -97.4)
            pressures = [lv["pressure"] for lv in result["profile"]]
            assert pressures[0] == 970.0
            assert 1000.0 not in pressures and 975.0 not in pressures
            assert pressures[1] == 950.0
            assert pressures == sorted(pressures, reverse=True)
            sfc = result["profile"][0]
            assert sfc["height"] == 300.0
            assert sfc["temp"] == 30.0 and sfc["dewpoint"] == 18.0
            assert sfc["wind_speed"] == 8.0 and sfc["wind_dir"] == 200
            assert result["valid"] == "2026-09-20T17:00"
            assert result["elevation_m"] == 300.0
        finally:
            await client.close()

    @respx.mock
    async def test_high_terrain_drops_more_levels(self):
        respx.get(f"{BASE_URL}/v1/forecast").mock(
            return_value=httpx.Response(
                200, json=_mock_sounding_response(elevation=1600.0, sfc_p=845.0),
            ),
        )
        client = OpenMeteoClient()
        try:
            result = await client.get_sounding(39.7, -105.0)
            pressures = [lv["pressure"] for lv in result["profile"]]
            assert pressures[:2] == [845.0, 800.0]
            assert 850.0 not in pressures
        finally:
            await client.close()

    @respx.mock
    async def test_hours_ahead_selects_hour_and_requests_knots(self):
        route = respx.get(f"{BASE_URL}/v1/forecast").mock(
            return_value=httpx.Response(200, json=_mock_sounding_response(hours=4)),
        )
        client = OpenMeteoClient()
        try:
            result = await client.get_sounding(35.2, -97.4, hours_ahead=3)
            params = route.calls.last.request.url.params
            assert params["forecast_hours"] == "4"
            assert params["wind_speed_unit"] == "kn"
            assert result["valid"] == "2026-09-20T20:00"
        finally:
            await client.close()

    @respx.mock
    async def test_caching_keyed_on_hours_ahead(self):
        route = respx.get(f"{BASE_URL}/v1/forecast").mock(
            return_value=httpx.Response(200, json=_mock_sounding_response(hours=3)),
        )
        client = OpenMeteoClient()
        try:
            await client.get_sounding(35.2, -97.4, 0)
            await client.get_sounding(35.2, -97.4, 0)
            assert route.call_count == 1
            await client.get_sounding(35.2, -97.4, 2)
            assert route.call_count == 2
        finally:
            await client.close()

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

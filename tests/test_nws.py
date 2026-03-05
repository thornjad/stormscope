"""Tests for NWS API client."""

import httpx
import pytest
import respx

from stormscope.nws import BASE_URL, NWSClient
from tests.conftest import (
    MINNEAPOLIS_LAT,
    MINNEAPOLIS_LON,
    MOCK_ALERTS_RESPONSE,
    MOCK_FORECAST_RESPONSE,
    MOCK_HOURLY_FORECAST_RESPONSE,
    MOCK_OBSERVATION_RESPONSE,
    MOCK_POINTS_RESPONSE,
    MOCK_STATIONS_RESPONSE,
)


@pytest.fixture
def nws():
    return NWSClient()


class TestGetPoint:
    @respx.mock
    async def test_returns_properties(self, nws):
        respx.get(f"{BASE_URL}/points/{MINNEAPOLIS_LAT},{MINNEAPOLIS_LON}").mock(
            return_value=httpx.Response(200, json=MOCK_POINTS_RESPONSE),
        )
        result = await nws.get_point(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)
        assert result["gridId"] == "MPX"
        assert result["gridX"] == 107
        assert result["gridY"] == 69

    @respx.mock
    async def test_caches_result(self, nws):
        route = respx.get(f"{BASE_URL}/points/{MINNEAPOLIS_LAT},{MINNEAPOLIS_LON}").mock(
            return_value=httpx.Response(200, json=MOCK_POINTS_RESPONSE),
        )
        await nws.get_point(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)
        await nws.get_point(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)
        assert route.call_count == 1

    @respx.mock
    async def test_non_us_location_raises(self, nws):
        respx.get(f"{BASE_URL}/points/51.5,-0.1").mock(
            return_value=httpx.Response(404, json={"detail": "not found"}),
        )
        with pytest.raises(ValueError, match="NWS only covers US"):
            await nws.get_point(51.5, -0.1)


class TestGetStations:
    @respx.mock
    async def test_returns_station_list(self, nws):
        url = f"{BASE_URL}/gridpoints/MPX/107,69/stations"
        respx.get(url).mock(
            return_value=httpx.Response(200, json=MOCK_STATIONS_RESPONSE),
        )
        result = await nws.get_stations(url)
        assert len(result) == 1
        assert result[0]["stationIdentifier"] == "KMSP"


class TestGetLatestObservation:
    @respx.mock
    async def test_returns_properties(self, nws):
        respx.get(f"{BASE_URL}/stations/KMSP/observations/latest").mock(
            return_value=httpx.Response(200, json=MOCK_OBSERVATION_RESPONSE),
        )
        result = await nws.get_latest_observation("KMSP")
        assert result["textDescription"] == "Mostly Sunny"
        assert result["temperature"]["value"] == 22.2

    @respx.mock
    async def test_handles_null_values(self, nws):
        respx.get(f"{BASE_URL}/stations/KMSP/observations/latest").mock(
            return_value=httpx.Response(200, json=MOCK_OBSERVATION_RESPONSE),
        )
        result = await nws.get_latest_observation("KMSP")
        assert result["windGust"]["value"] is None
        assert result["heatIndex"]["value"] is None


class TestGetForecast:
    @respx.mock
    async def test_returns_periods(self, nws):
        respx.get(f"{BASE_URL}/gridpoints/MPX/107,69/forecast?units=us").mock(
            return_value=httpx.Response(200, json=MOCK_FORECAST_RESPONSE),
        )
        result = await nws.get_forecast("MPX", 107, 69)
        assert len(result["periods"]) == 2
        assert result["periods"][0]["name"] == "Today"


class TestGetHourlyForecast:
    @respx.mock
    async def test_returns_periods(self, nws):
        respx.get(f"{BASE_URL}/gridpoints/MPX/107,69/forecast/hourly?units=us").mock(
            return_value=httpx.Response(200, json=MOCK_HOURLY_FORECAST_RESPONSE),
        )
        result = await nws.get_hourly_forecast("MPX", 107, 69)
        assert len(result["periods"]) == 6


class TestGetAlerts:
    @respx.mock
    async def test_returns_alert_data(self, nws):
        respx.get(
            f"{BASE_URL}/alerts/active",
            params={"point": f"{MINNEAPOLIS_LAT},{MINNEAPOLIS_LON}"},
        ).mock(
            return_value=httpx.Response(200, json=MOCK_ALERTS_RESPONSE),
        )
        result = await nws.get_alerts(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)
        assert len(result["features"]) == 1


class TestRetryLogic:
    @respx.mock
    async def test_retries_on_500(self, nws):
        route = respx.get(f"{BASE_URL}/points/40.0,-90.0")
        route.side_effect = [
            httpx.Response(500),
            httpx.Response(200, json=MOCK_POINTS_RESPONSE),
        ]
        result = await nws.get_point(40.0, -90.0)
        assert result["gridId"] == "MPX"
        assert route.call_count == 2

    @respx.mock
    async def test_retries_on_429(self, nws):
        route = respx.get(f"{BASE_URL}/points/40.0,-90.0")
        route.side_effect = [
            httpx.Response(429),
            httpx.Response(200, json=MOCK_POINTS_RESPONSE),
        ]
        result = await nws.get_point(40.0, -90.0)
        assert result["gridId"] == "MPX"

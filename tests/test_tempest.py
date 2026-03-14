"""Tests for TempestClient."""

import pytest
import respx
import httpx

from stormscope.tempest import TempestClient
from stormscope.units import UnitPrefs

from tests.conftest import (
    TEMPEST_STATION_NEARBY,
    TEMPEST_STATION_FAR,
    MOCK_TEMPEST_STATIONS_RESPONSE,
    MOCK_TEMPEST_STATIONS_FAR_ONLY,
    MOCK_TEMPEST_OBSERVATION_RESPONSE,
    MOCK_TEMPEST_OBSERVATION_EMPTY,
    MOCK_TEMPEST_FORECAST_RESPONSE,
    MINNEAPOLIS_LAT,
    MINNEAPOLIS_LON,
)

_BASE = "https://swd.weatherflow.com/swd/rest"
_US_PREFS = UnitPrefs(temperature="f", pressure="inhg", wind="mph", distance="mi", accumulation="in")
_SI_PREFS = UnitPrefs(temperature="c", pressure="mb", wind="kmh", distance="km", accumulation="mm")


@pytest.fixture()
def client():
    return TempestClient(token="test-token")


@respx.mock
async def test_get_stations(client):
    respx.get(f"{_BASE}/stations").mock(return_value=httpx.Response(200, json=MOCK_TEMPEST_STATIONS_RESPONSE))
    stations = await client.get_stations()
    assert len(stations) == 2
    assert stations[0]["station_id"] == 211167


@respx.mock
async def test_get_stations_cached(client):
    route = respx.get(f"{_BASE}/stations").mock(return_value=httpx.Response(200, json=MOCK_TEMPEST_STATIONS_RESPONSE))
    await client.get_stations()
    await client.get_stations()
    # only called once due to cache
    assert route.call_count == 1


@respx.mock
async def test_resolve_station_by_id(client):
    respx.get(f"{_BASE}/stations").mock(return_value=httpx.Response(200, json=MOCK_TEMPEST_STATIONS_RESPONSE))
    station = await client.resolve_station(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, station_id=211167)
    assert station is not None
    assert station["station_id"] == 211167


@respx.mock
async def test_resolve_station_by_name(client):
    respx.get(f"{_BASE}/stations").mock(return_value=httpx.Response(200, json=MOCK_TEMPEST_STATIONS_RESPONSE))
    station = await client.resolve_station(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, station_name="holz lake")
    assert station is not None
    assert station["name"] == "Holz Lake"


@respx.mock
async def test_resolve_station_by_public_name(client):
    respx.get(f"{_BASE}/stations").mock(return_value=httpx.Response(200, json=MOCK_TEMPEST_STATIONS_RESPONSE))
    station = await client.resolve_station(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, station_name="HOLZ LAKE PUBLIC")
    assert station is not None
    assert station["public_name"] == "Holz Lake Public"


@respx.mock
async def test_resolve_station_by_name_no_match(client):
    respx.get(f"{_BASE}/stations").mock(return_value=httpx.Response(200, json=MOCK_TEMPEST_STATIONS_RESPONSE))
    station = await client.resolve_station(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, station_name="nonexistent")
    assert station is None


@respx.mock
async def test_resolve_station_closest(client):
    respx.get(f"{_BASE}/stations").mock(return_value=httpx.Response(200, json=MOCK_TEMPEST_STATIONS_RESPONSE))
    # use coords near the nearby station (44.990, -93.270)
    station = await client.resolve_station(44.991, -93.271)
    assert station is not None
    assert station["station_id"] == 211167


@respx.mock
async def test_resolve_station_too_far(client):
    respx.get(f"{_BASE}/stations").mock(return_value=httpx.Response(200, json=MOCK_TEMPEST_STATIONS_FAR_ONLY))
    station = await client.resolve_station(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)
    assert station is None


@respx.mock
async def test_get_observations(client):
    respx.get(f"{_BASE}/observations/station/211167").mock(
        return_value=httpx.Response(200, json=MOCK_TEMPEST_OBSERVATION_RESPONSE)
    )
    obs = await client.get_observations(211167)
    assert obs is not None
    assert obs["air_temperature"] == 18.5
    assert obs["solar_radiation"] == 450
    assert "_station_units" in obs


@respx.mock
async def test_get_observations_empty(client):
    respx.get(f"{_BASE}/observations/station/211167").mock(
        return_value=httpx.Response(200, json=MOCK_TEMPEST_OBSERVATION_EMPTY)
    )
    obs = await client.get_observations(211167)
    assert obs is None


@respx.mock
async def test_get_forecast_unit_mapping_us(client):
    route = respx.get(f"{_BASE}/better_forecast").mock(
        return_value=httpx.Response(200, json=MOCK_TEMPEST_FORECAST_RESPONSE)
    )
    await client.get_forecast(211167, _US_PREFS)
    request = route.calls[0].request
    assert b"units_temp=f" in request.url.query
    assert b"units_wind=mph" in request.url.query
    assert b"units_pressure=inhg" in request.url.query
    assert b"units_precip=in" in request.url.query
    assert b"units_distance=mi" in request.url.query


@respx.mock
async def test_get_forecast_unit_mapping_si(client):
    route = respx.get(f"{_BASE}/better_forecast").mock(
        return_value=httpx.Response(200, json=MOCK_TEMPEST_FORECAST_RESPONSE)
    )
    await client.get_forecast(211167, _SI_PREFS)
    request = route.calls[0].request
    assert b"units_temp=c" in request.url.query
    assert b"units_wind=kph" in request.url.query
    assert b"units_pressure=mb" in request.url.query
    assert b"units_precip=mm" in request.url.query
    assert b"units_distance=km" in request.url.query


def test_normalize_obs_celsius_to_fahrenheit(client):
    obs = {
        "air_temperature": 20.0,
        "_station_units": {"units_temp": "c", "units_wind": "mps"},
    }
    result = client.normalize_obs(obs, _US_PREFS)
    # 20°C == 68°F
    assert abs(result["air_temperature"] - 68.0) < 0.1


def test_normalize_obs_mps_to_mph(client):
    obs = {
        "wind_avg": 10.0,
        "_station_units": {"units_temp": "c", "units_wind": "mps"},
    }
    result = client.normalize_obs(obs, _US_PREFS)
    # 10 m/s ≈ 22.37 mph
    assert abs(result["wind_avg"] - 22.37) < 0.1


def test_normalize_obs_pressure_mb_to_inhg(client):
    obs = {
        "station_pressure": 1013.25,
        "_station_units": {"units_temp": "c", "units_wind": "mps", "units_pressure": "mb"},
    }
    result = client.normalize_obs(obs, _US_PREFS)
    # 1013.25 mb == 29.92 inHg
    assert abs(result["station_pressure"] - 29.92) < 0.05


def test_normalize_obs_si_passthrough(client):
    obs = {
        "air_temperature": 20.0,
        "wind_avg": 5.0,
        "_station_units": {"units_temp": "c", "units_wind": "mps", "units_pressure": "mb"},
    }
    result = client.normalize_obs(obs, _SI_PREFS)
    assert result["air_temperature"] == 20.0  # c -> c
    # 5 m/s -> km/h = 18.0
    assert abs(result["wind_avg"] - 18.0) < 0.1


@respx.mock
async def test_auth_token_in_requests(client):
    route = respx.get(f"{_BASE}/stations").mock(
        return_value=httpx.Response(200, json=MOCK_TEMPEST_STATIONS_RESPONSE)
    )
    await client.get_stations()
    request = route.calls[0].request
    assert b"token=test-token" in request.url.query


@respx.mock
async def test_api_error_stale_fallback(client):
    # prime the cache
    respx.get(f"{_BASE}/stations").mock(return_value=httpx.Response(200, json=MOCK_TEMPEST_STATIONS_RESPONSE))
    await client.get_stations()

    # now fail with 500 — should get stale data
    respx.get(f"{_BASE}/stations").mock(return_value=httpx.Response(500))
    # TTL cache may serve stale; we just confirm no exception is raised
    stations = await client.get_stations()
    assert stations is not None


@respx.mock
async def test_resolve_station_by_id_warns_when_too_far(client, caplog):
    """explicit station_id that is outside the proximity limit returns None and logs a warning."""
    import logging
    respx.get(f"{_BASE}/stations").mock(return_value=httpx.Response(200, json=MOCK_TEMPEST_STATIONS_FAR_ONLY))
    with caplog.at_level(logging.WARNING, logger="stormscope.tempest"):
        station = await client.resolve_station(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, station_id=99999)
    assert station is None
    assert any("configured tempest station" in r.message for r in caplog.records)


@respx.mock
async def test_resolve_station_by_name_warns_when_too_far(client, caplog):
    """explicit station_name that is outside the proximity limit returns None and logs a warning."""
    import logging
    respx.get(f"{_BASE}/stations").mock(return_value=httpx.Response(200, json=MOCK_TEMPEST_STATIONS_FAR_ONLY))
    with caplog.at_level(logging.WARNING, logger="stormscope.tempest"):
        station = await client.resolve_station(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, station_name="far away station")
    assert station is None
    assert any("configured tempest station" in r.message for r in caplog.records)


@respx.mock
async def test_resolve_station_proximity_miss_cached(client):
    """S5: a proximity miss (too far) should be cached so the station list is fetched only once."""
    route = respx.get(f"{_BASE}/stations").mock(
        return_value=httpx.Response(200, json=MOCK_TEMPEST_STATIONS_FAR_ONLY)
    )
    result1 = await client.resolve_station(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)
    result2 = await client.resolve_station(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)
    assert result1 is None
    assert result2 is None
    # station list fetched once; second call served from cache
    assert route.call_count == 1


@respx.mock
async def test_resolve_station_no_match_cached(client):
    """S5: a name miss (no matching station) should also be cached."""
    route = respx.get(f"{_BASE}/stations").mock(
        return_value=httpx.Response(200, json=MOCK_TEMPEST_STATIONS_RESPONSE)
    )
    result1 = await client.resolve_station(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, station_name="nonexistent")
    result2 = await client.resolve_station(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, station_name="nonexistent")
    assert result1 is None
    assert result2 is None
    assert route.call_count == 1

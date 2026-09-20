"""Tests for IEM RAOB client."""

from datetime import datetime, timezone

import httpx
import pytest
import respx

from stormscope.iem import IEM_BASE
from stormscope.raob import RAOBClient, _latest_cycles

STATIONS_URL = f"{IEM_BASE}/geojson/network/RAOB.geojson"
RAOB_URL = f"{IEM_BASE}/json/raob.py"


def _feature(sid, lon, lat, name="Test  Site", online=True, archive_end=None, country="US"):
    return {
        "id": sid,
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "sname": name, "online": online, "archive_end": archive_end,
            "elevation": 300.0, "country": country,
        },
    }


STATIONS = {"features": [
    _feature("KAAA", -97.4, 35.2, "Norman  OK/US"),
    _feature("KBBB", -93.5, 44.8, "Chanhassen  MN/US"),
    _feature("KCCC", -104.7, 39.8, "Denver", archive_end="2022-07-08"),
    _feature("_DEN", -103.2, 39.9, "Denver Area -- KDEN"),
    _feature("KDDD", -100.0, 40.0, "Offline", online=False),
]}


def _profile_response(station="KAAA"):
    return httpx.Response(200, json={"profiles": [{
        "station": station,
        "valid": "2026-09-20T12:00:00Z",
        "profile": [
            {"pres": 1000.0, "hght": 93.0, "tmpc": None, "dwpc": None, "drct": None, "sknt": None},
            {"pres": 972.0, "hght": 357.0, "tmpc": 25.4, "dwpc": 17.4, "drct": 160.0, "sknt": 4.0},
        ],
    }]})


EMPTY = httpx.Response(200, json={"profiles": [], "generated_at": "2026-09-20T17:00:00Z"})


class TestLatestCycles:
    def test_afternoon_gives_12z_then_00z(self):
        now = datetime(2026, 9, 20, 17, 35, tzinfo=timezone.utc)
        assert _latest_cycles(now, 2) == [
            datetime(2026, 9, 20, 12, tzinfo=timezone.utc),
            datetime(2026, 9, 20, 0, tzinfo=timezone.utc),
        ]

    def test_before_publish_lag_uses_previous_cycle(self):
        now = datetime(2026, 9, 20, 12, 30, tzinfo=timezone.utc)
        assert _latest_cycles(now, 1) == [datetime(2026, 9, 20, 0, tzinfo=timezone.utc)]

    def test_crosses_midnight(self):
        now = datetime(2026, 9, 20, 0, 30, tzinfo=timezone.utc)
        assert _latest_cycles(now, 2) == [
            datetime(2026, 9, 19, 12, tzinfo=timezone.utc),
            datetime(2026, 9, 19, 0, tzinfo=timezone.utc),
        ]


class TestStations:
    @respx.mock
    async def test_filters_retired_offline_and_area_sites(self):
        respx.get(STATIONS_URL).mock(return_value=httpx.Response(200, json=STATIONS))
        client = RAOBClient()
        try:
            stations = await client.get_stations()
            assert [s["id"] for s in stations] == ["KAAA", "KBBB"]
            assert stations[0]["name"] == "Norman OK/US"  # whitespace normalized
            assert stations[0]["lat"] == 35.2 and stations[0]["lon"] == -97.4
        finally:
            await client.close()

    @respx.mock
    async def test_station_list_is_cached(self):
        route = respx.get(STATIONS_URL).mock(return_value=httpx.Response(200, json=STATIONS))
        client = RAOBClient()
        try:
            await client.get_stations()
            await client.get_stations()
            assert route.call_count == 1
        finally:
            await client.close()

    @respx.mock
    async def test_nearest_stations_sorted_by_distance(self):
        respx.get(STATIONS_URL).mock(return_value=httpx.Response(200, json=STATIONS))
        client = RAOBClient()
        try:
            ranked = await client.nearest_stations(45.0, -93.3)
            assert [s["id"] for _, s in ranked] == ["KBBB", "KAAA"]
            assert ranked[0][0] < 50 < ranked[1][0]
        finally:
            await client.close()


class TestGetProfile:
    @respx.mock
    async def test_parses_levels(self):
        route = respx.get(RAOB_URL).mock(return_value=_profile_response())
        client = RAOBClient()
        try:
            valid = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)
            profile = await client.get_profile("KAAA", valid)
            assert route.calls.last.request.url.params["ts"] == "202609201200"
            assert route.calls.last.request.url.params["station"] == "KAAA"
            assert profile[1] == {
                "pressure": 972.0, "height": 357.0, "temp": 25.4,
                "dewpoint": 17.4, "wind_dir": 160.0, "wind_speed": 4.0,
            }
            assert profile[0]["temp"] is None
        finally:
            await client.close()

    @respx.mock
    async def test_empty_response_is_none(self):
        respx.get(RAOB_URL).mock(return_value=EMPTY)
        client = RAOBClient()
        try:
            valid = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)
            assert await client.get_profile("KAAA", valid) is None
        finally:
            await client.close()


class TestGetLatest:
    @respx.mock
    async def test_nearest_station_newest_cycle(self):
        respx.get(STATIONS_URL).mock(return_value=httpx.Response(200, json=STATIONS))
        respx.get(RAOB_URL).mock(return_value=_profile_response("KBBB"))
        client = RAOBClient()
        try:
            found = await client.get_latest(45.0, -93.3)
            assert found["station"]["id"] == "KBBB"
            assert found["distance_km"] < 50
            assert found["valid"] == _latest_cycles(datetime.now(timezone.utc), 1)[0]
        finally:
            await client.close()

    @respx.mock
    async def test_falls_back_to_previous_cycle(self):
        respx.get(STATIONS_URL).mock(return_value=httpx.Response(200, json=STATIONS))
        respx.get(RAOB_URL).mock(side_effect=[EMPTY, _profile_response("KBBB")])
        client = RAOBClient()
        try:
            found = await client.get_latest(45.0, -93.3)
            assert found["station"]["id"] == "KBBB"
            assert found["valid"] == _latest_cycles(datetime.now(timezone.utc), 2)[1]
        finally:
            await client.close()

    @respx.mock
    async def test_falls_back_to_next_station(self):
        respx.get(STATIONS_URL).mock(return_value=httpx.Response(200, json=STATIONS))
        # nearest station has neither cycle; second station has the newest
        respx.get(RAOB_URL).mock(side_effect=[EMPTY, EMPTY, _profile_response("KAAA")])
        client = RAOBClient()
        try:
            found = await client.get_latest(45.0, -93.3)
            assert found["station"]["id"] == "KAAA"
            assert found["distance_km"] > 500
        finally:
            await client.close()

    @respx.mock
    async def test_http_error_skips_to_next_candidate(self):
        respx.get(STATIONS_URL).mock(return_value=httpx.Response(200, json=STATIONS))
        respx.get(RAOB_URL).mock(side_effect=[
            httpx.Response(500), httpx.Response(500), _profile_response("KAAA"),
        ])
        client = RAOBClient()
        try:
            found = await client.get_latest(45.0, -93.3)
            assert found["station"]["id"] == "KAAA"
        finally:
            await client.close()

    @respx.mock
    async def test_none_when_nothing_available(self):
        respx.get(STATIONS_URL).mock(return_value=httpx.Response(200, json=STATIONS))
        respx.get(RAOB_URL).mock(return_value=EMPTY)
        client = RAOBClient()
        try:
            assert await client.get_latest(45.0, -93.3) is None
        finally:
            await client.close()

    @respx.mock
    async def test_named_station_ignores_distance_ranking(self):
        respx.get(STATIONS_URL).mock(return_value=httpx.Response(200, json=STATIONS))
        route = respx.get(RAOB_URL).mock(return_value=_profile_response("KAAA"))
        client = RAOBClient()
        try:
            found = await client.get_latest(45.0, -93.3, station_id="kaaa")
            assert found["station"]["id"] == "KAAA"
            assert route.calls.last.request.url.params["station"] == "KAAA"
        finally:
            await client.close()

    @respx.mock
    async def test_named_station_accepts_missing_k_prefix(self):
        respx.get(STATIONS_URL).mock(return_value=httpx.Response(200, json=STATIONS))
        respx.get(RAOB_URL).mock(return_value=_profile_response("KAAA"))
        client = RAOBClient()
        try:
            found = await client.get_latest(45.0, -93.3, station_id="AAA")
            assert found["station"]["id"] == "KAAA"
        finally:
            await client.close()

    @respx.mock
    async def test_unknown_station_raises(self):
        respx.get(STATIONS_URL).mock(return_value=httpx.Response(200, json=STATIONS))
        client = RAOBClient()
        try:
            with pytest.raises(ValueError, match="unknown radiosonde station"):
                await client.get_latest(45.0, -93.3, station_id="ZZZZ")
        finally:
            await client.close()

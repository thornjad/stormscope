"""Tests for the 7 collapsed tool functions."""

from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import (
    MINNEAPOLIS_LAT,
    MINNEAPOLIS_LON,
    MOCK_ALERTS_RESPONSE,
    MOCK_FORECAST_RESPONSE,
    MOCK_GRIDPOINT_RESPONSE,
    MOCK_HOURLY_FORECAST_RESPONSE,
    MOCK_OBSERVATION_RESPONSE,
    MOCK_POINTS_RESPONSE,
    MOCK_RADAR_RESPONSE,
    MOCK_SPC_OUTLOOK,
    MOCK_STATIONS_RESPONSE,
)


POINT_PROPS = MOCK_POINTS_RESPONSE["properties"]
STATION_LIST = [s["properties"] for s in MOCK_STATIONS_RESPONSE["features"]]
OBS_PROPS = MOCK_OBSERVATION_RESPONSE["properties"]
FORECAST_PROPS = MOCK_FORECAST_RESPONSE["properties"]
HOURLY_PROPS = MOCK_HOURLY_FORECAST_RESPONSE["properties"]
GRIDPOINT_PROPS = MOCK_GRIDPOINT_RESPONSE["properties"]


def _mock_nws():
    mock = AsyncMock()
    mock.get_point.return_value = POINT_PROPS
    mock.get_stations.return_value = STATION_LIST
    mock.get_latest_observation.return_value = OBS_PROPS
    mock.get_forecast.return_value = FORECAST_PROPS
    mock.get_hourly_forecast.return_value = HOURLY_PROPS
    mock.get_alerts.return_value = MOCK_ALERTS_RESPONSE
    mock.get_detailed_forecast.return_value = GRIDPOINT_PROPS
    return mock


class TestGetConditions:
    @patch("stormscope.tools._nws")
    async def test_standard_detail(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_stations = m.get_stations
        mock_nws.get_latest_observation = m.get_latest_observation

        from stormscope.tools import get_conditions
        result = await get_conditions(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "error" not in result
        assert result["temperature"] == "72°F"
        assert result["humidity"] == "45%"
        assert result["sky_condition"] == "Mostly Sunny"
        assert result["station_name"] == "Minneapolis-St Paul International Airport"
        assert "°F" in result["feels_like"]
        assert "mi" in result["visibility"]
        assert "inHg" in result["pressure"]
        assert "dewpoint" not in result
        assert "cloud_layers" not in result

    @patch("stormscope.tools._nws")
    async def test_full_detail(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_stations = m.get_stations
        mock_nws.get_latest_observation = m.get_latest_observation

        from stormscope.tools import get_conditions
        result = await get_conditions(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, detail="full")

        assert "error" not in result
        assert result["temperature"] == "72°F"
        assert "dewpoint" in result
        assert result["dewpoint"] == "50°F"
        assert "cloud_layers" in result
        assert "present_weather" in result
        assert "raw_observation" in result

    @patch("stormscope.tools._nws")
    async def test_null_wind_gust(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_stations = m.get_stations
        mock_nws.get_latest_observation = m.get_latest_observation

        from stormscope.tools import get_conditions
        result = await get_conditions(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert result["wind_gust"] == "calm"

    @patch("stormscope.tools._nws")
    async def test_error_for_non_us(self, mock_nws):
        mock_nws.get_point = AsyncMock(
            side_effect=ValueError("NWS only covers US territories"),
        )

        from stormscope.tools import get_conditions
        result = await get_conditions(51.5, -0.1)

        assert "error" in result
        assert "US" in result["error"]

    @patch("stormscope.tools._nws")
    async def test_no_stations(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_stations = AsyncMock(return_value=[])

        from stormscope.tools import get_conditions
        result = await get_conditions(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "error" in result
        assert "station" in result["error"]


class TestGetForecast:
    @patch("stormscope.tools._nws")
    async def test_daily_mode(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_forecast = m.get_forecast

        from stormscope.tools import get_forecast
        result = await get_forecast(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "error" not in result
        assert result["location"] == "Minneapolis, MN"
        assert len(result["periods"]) == 2
        assert result["periods"][0]["name"] == "Today"
        assert result["periods"][0]["temperature"] == "78°F"

    @patch("stormscope.tools._nws")
    async def test_hourly_mode(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_hourly_forecast = m.get_hourly_forecast

        from stormscope.tools import get_forecast
        result = await get_forecast(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, mode="hourly")

        assert "error" not in result
        assert result["location"] == "Minneapolis, MN"
        assert len(result["periods"]) == 6
        assert "°F" in result["periods"][0]["temperature"]

    @patch("stormscope.tools._nws")
    async def test_raw_mode(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_detailed_forecast = m.get_detailed_forecast

        from stormscope.tools import get_forecast
        result = await get_forecast(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, mode="raw")

        assert "error" not in result
        assert result["location"] == "Minneapolis, MN"
        assert "grid" in result
        assert "temperature" in result["grid"]

    @patch("stormscope.tools._nws")
    async def test_hourly_caps_to_hours(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_hourly_forecast = m.get_hourly_forecast

        from stormscope.tools import get_forecast
        result = await get_forecast(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, mode="hourly", hours=3)

        assert len(result["periods"]) == 3

    @patch("stormscope.tools._nws")
    async def test_daily_caps_to_days(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_forecast = m.get_forecast

        from stormscope.tools import get_forecast
        result = await get_forecast(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, days=1)

        assert len(result["periods"]) == 2

    @patch("stormscope.tools._nws")
    async def test_error_handling(self, mock_nws):
        mock_nws.get_point = AsyncMock(
            side_effect=ValueError("NWS only covers US territories"),
        )

        from stormscope.tools import get_forecast
        result = await get_forecast(51.5, -0.1)

        assert "error" in result


class TestGetAlerts:
    @patch("stormscope.tools._nws")
    async def test_standard_detail(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_alerts = m.get_alerts

        from stormscope.tools import get_alerts
        result = await get_alerts(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "error" not in result
        assert result["location"] == "Minneapolis, MN"
        assert result["count"] == 1
        assert result["alerts"][0]["event"] == "Heat Advisory"
        assert result["alerts"][0]["severity"] == "Moderate"
        assert "vtec" not in result["alerts"][0]

    @patch("stormscope.tools._nws")
    async def test_full_detail(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_alerts = m.get_alerts

        from stormscope.tools import get_alerts
        result = await get_alerts(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, detail="full")

        assert "error" not in result
        alert = result["alerts"][0]
        assert alert["event"] == "Heat Advisory"
        assert "vtec" in alert
        assert "area_desc" in alert
        assert "sender_name" in alert

    @patch("stormscope.tools._nws")
    async def test_severity_filter(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_alerts = m.get_alerts

        from stormscope.tools import get_alerts
        result = await get_alerts(
            MINNEAPOLIS_LAT, MINNEAPOLIS_LON, severity_filter="Extreme",
        )

        assert result["count"] == 0
        assert result["alerts"] == []

    @patch("stormscope.tools._nws")
    async def test_empty_alerts(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_alerts = AsyncMock(return_value={"features": []})

        from stormscope.tools import get_alerts
        result = await get_alerts(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert result["count"] == 0
        assert result["alerts"] == []

    @patch("stormscope.tools._nws")
    async def test_error_handling(self, mock_nws):
        mock_nws.get_point = AsyncMock(
            side_effect=ValueError("NWS only covers US territories"),
        )

        from stormscope.tools import get_alerts
        result = await get_alerts(51.5, -0.1)

        assert "error" in result


class TestGetSpcOutlook:
    @patch("stormscope.tools._spc")
    async def test_categorical(self, mock_spc):
        mock_spc.get_spc_outlook = AsyncMock(return_value={
            "risk_level": "MRGL",
            "risk_description": "Marginal Risk - isolated severe storms possible",
            "valid_time": "202603041200",
            "expire_time": "202603051200",
            "is_significant": False,
            "day": 1,
        })

        from stormscope.tools import get_spc_outlook
        result = await get_spc_outlook(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert result["risk_level"] == "MRGL"
        assert result["is_significant"] is False

    @patch("stormscope.tools._spc")
    async def test_probabilistic(self, mock_spc):
        mock_spc.get_spc_outlook = AsyncMock(return_value={
            "hazard": "tornado",
            "probability": 5,
            "significant": True,
            "valid_time": "202603041200",
            "expire_time": "202603051200",
            "day": 1,
        })

        from stormscope.tools import get_spc_outlook
        result = await get_spc_outlook(
            MINNEAPOLIS_LAT, MINNEAPOLIS_LON, outlook_type="tornado",
        )

        assert result["hazard"] == "tornado"
        assert result["probability"] == 5
        assert result["significant"] is True


class TestGetNationalOutlook:
    @patch("stormscope.tools._spc")
    async def test_returns_areas(self, mock_spc):
        mock_spc.get_national_outlook_summary = AsyncMock(return_value={
            "day": 1,
            "areas": [
                {"risk_level": "TSTM", "region": "central Minnesota", "is_significant": False},
                {"risk_level": "MRGL", "region": "central Minnesota", "is_significant": False},
            ],
            "valid_time": "202603041200",
        })

        from stormscope.tools import get_national_outlook
        result = await get_national_outlook()

        assert result["day"] == 1
        assert len(result["areas"]) == 2


class TestGetRadar:
    @patch("stormscope.tools._iem")
    @patch("stormscope.tools._nws")
    async def test_returns_radar_data(self, mock_nws, mock_iem):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_iem.get_radar_info = AsyncMock(return_value=MOCK_RADAR_RESPONSE)

        from stormscope.tools import get_radar
        result = await get_radar(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "error" not in result
        assert result["station_id"] == "KMPX"
        assert "imagery_urls" in result
        mock_iem.get_radar_info.assert_awaited_once_with("KMPX")

    @patch("stormscope.tools._nws")
    async def test_error_for_non_us(self, mock_nws):
        mock_nws.get_point = AsyncMock(
            side_effect=ValueError("NWS only covers US territories"),
        )

        from stormscope.tools import get_radar
        result = await get_radar(51.5, -0.1)

        assert "error" in result


class TestGetBriefing:
    @patch("stormscope.tools._spc")
    @patch("stormscope.tools._nws")
    async def test_standard_briefing(self, mock_nws, mock_spc):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_stations = m.get_stations
        mock_nws.get_latest_observation = m.get_latest_observation
        mock_nws.get_forecast = m.get_forecast
        mock_nws.get_alerts = m.get_alerts

        mock_spc.get_spc_outlook = AsyncMock(return_value={
            "risk_level": "NONE",
            "risk_description": "No severe weather risk",
            "valid_time": None,
            "expire_time": None,
            "is_significant": False,
            "day": 1,
        })

        from stormscope.tools import get_briefing
        result = await get_briefing(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert result["location"] == "Minneapolis, MN"
        assert "temperature" in result["current_conditions"]
        assert result["today"]["name"] == "Today"
        assert result["tonight"]["name"] == "Tonight"
        assert result["alert_count"] == 1
        assert result["severe_outlook"]["risk_level"] == "NONE"
        assert "radar" not in result

    @patch("stormscope.tools._iem")
    @patch("stormscope.tools._spc")
    @patch("stormscope.tools._nws")
    async def test_full_briefing(self, mock_nws, mock_spc, mock_iem):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_stations = m.get_stations
        mock_nws.get_latest_observation = m.get_latest_observation
        mock_nws.get_forecast = m.get_forecast
        mock_nws.get_alerts = m.get_alerts

        mock_spc.get_spc_outlook = AsyncMock(return_value={
            "risk_level": "NONE",
            "risk_description": "No severe weather risk",
            "valid_time": None,
            "expire_time": None,
            "is_significant": False,
            "day": 1,
        })
        mock_spc.get_national_outlook_summary = AsyncMock(return_value={
            "day": 1, "areas": [], "valid_time": None,
        })
        mock_iem.get_radar_info = AsyncMock(return_value=MOCK_RADAR_RESPONSE)

        from stormscope.tools import get_briefing
        result = await get_briefing(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, detail="full")

        assert result["location"] == "Minneapolis, MN"
        assert "temperature" in result["current_conditions"]
        assert "radar" in result
        assert "national_day1" in result
        assert result["radar"]["station_id"] == "KMPX"

    @patch("stormscope.tools._spc")
    @patch("stormscope.tools._nws")
    async def test_degrades_gracefully(self, mock_nws, mock_spc):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_stations = m.get_stations
        mock_nws.get_latest_observation = m.get_latest_observation
        mock_nws.get_forecast = AsyncMock(side_effect=Exception("API down"))
        mock_nws.get_alerts = m.get_alerts

        mock_spc.get_spc_outlook = AsyncMock(return_value={
            "risk_level": "NONE",
            "risk_description": "No severe weather risk",
            "valid_time": None,
            "expire_time": None,
            "is_significant": False,
            "day": 1,
        })

        from stormscope.tools import get_briefing
        result = await get_briefing(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "temperature" in result["current_conditions"]
        assert result["alert_count"] == 1

    @patch("stormscope.tools._iem")
    @patch("stormscope.tools._spc")
    @patch("stormscope.tools._nws")
    async def test_full_briefing_with_mrgl_includes_probabilistic(self, mock_nws, mock_spc, mock_iem):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_stations = m.get_stations
        mock_nws.get_latest_observation = m.get_latest_observation
        mock_nws.get_forecast = m.get_forecast
        mock_nws.get_alerts = m.get_alerts

        mock_spc.get_spc_outlook = AsyncMock(return_value={
            "risk_level": "MRGL",
            "risk_description": "Marginal Risk",
            "valid_time": "202603041200",
            "expire_time": "202603051200",
            "is_significant": False,
            "day": 1,
        })
        mock_spc.get_national_outlook_summary = AsyncMock(return_value={
            "day": 1, "areas": [], "valid_time": None,
        })
        mock_iem.get_radar_info = AsyncMock(return_value=MOCK_RADAR_RESPONSE)

        from stormscope.tools import get_briefing
        result = await get_briefing(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, detail="full")

        assert "probabilistic_tornado" in result
        assert "probabilistic_wind" in result
        assert "probabilistic_hail" in result
        assert "radar" in result
        assert "national_day1" in result


class TestValidation:
    async def test_invalid_forecast_mode(self):
        from stormscope.tools import get_forecast
        result = await get_forecast(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, mode="invalid")
        assert "error" in result
        assert "invalid mode" in result["error"]

    async def test_invalid_spc_day(self):
        from stormscope.tools import get_spc_outlook
        result = await get_spc_outlook(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, day=0)
        assert "error" in result
        assert "invalid day" in result["error"]

    async def test_invalid_spc_day_too_high(self):
        from stormscope.tools import get_spc_outlook
        result = await get_spc_outlook(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, day=99)
        assert "error" in result

    async def test_invalid_outlook_type(self):
        from stormscope.tools import get_spc_outlook
        result = await get_spc_outlook(
            MINNEAPOLIS_LAT, MINNEAPOLIS_LON, outlook_type="snow",
        )
        assert "error" in result
        assert "invalid outlook_type" in result["error"]

    async def test_invalid_national_day(self):
        from stormscope.tools import get_national_outlook
        result = await get_national_outlook(day=0)
        assert "error" in result


class TestAlertsResilience:
    @patch("stormscope.tools._nws")
    async def test_alerts_work_when_points_api_down(self, mock_nws):
        mock_nws.get_alerts = AsyncMock(return_value=MOCK_ALERTS_RESPONSE)
        mock_nws.get_point = AsyncMock(side_effect=Exception("points API down"))

        from stormscope.tools import get_alerts
        result = await get_alerts(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "error" not in result
        assert result["count"] == 1
        assert result["alerts"][0]["event"] == "Heat Advisory"
        assert str(MINNEAPOLIS_LAT) in result["location"]

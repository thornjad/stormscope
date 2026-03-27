"""Tests for the 9 tool functions."""

from unittest.mock import AsyncMock, patch

from stormscope.tools import (
    _fmt_accumulation, _fmt_temp, _fmt_wind, _fmt_visibility, _fmt_pressure,
    _fmt_upper_wind, _fmt_vorticity, _fmt_distance,
)
from stormscope.units import UnitPrefs

import pytest

from tests.conftest import (
    MINNEAPOLIS_LAT,
    MINNEAPOLIS_LON,
    MOCK_ALERTS_RESPONSE,
    MOCK_FORECAST_RESPONSE,
    MOCK_GRIDPOINT_COLD,
    MOCK_GRIDPOINT_RESPONSE,
    MOCK_HOURLY_FORECAST_RESPONSE,
    MOCK_OBSERVATION_COLD,
    MOCK_OBSERVATION_RESPONSE,
    MOCK_POINTS_RESPONSE,
    MOCK_RADAR_RESPONSE,
    MOCK_SPC_OUTLOOK,
    MOCK_STATIONS_RESPONSE,
    MOCK_TEMPEST_FORECAST_RESPONSE,
    MOCK_TEMPEST_OBSERVATION_RESPONSE,
    MOCK_TEMPEST_STATIONS_RESPONSE,
    MOCK_UPPER_AIR_RAW,
    MOCK_WPC_FRONTS,
    MOCK_WPC_PRESSURE_CENTERS,
    TEMPEST_STATION_NEARBY,
)


POINT_PROPS = MOCK_POINTS_RESPONSE["properties"]
STATION_LIST = [s["properties"] for s in MOCK_STATIONS_RESPONSE["features"]]
OBS_PROPS = MOCK_OBSERVATION_RESPONSE["properties"]
FORECAST_PROPS = MOCK_FORECAST_RESPONSE["properties"]
HOURLY_PROPS = MOCK_HOURLY_FORECAST_RESPONSE["properties"]
GRIDPOINT_PROPS = MOCK_GRIDPOINT_RESPONSE["properties"]
GRIDPOINT_COLD_PROPS = MOCK_GRIDPOINT_COLD["properties"]

US_PREFS = UnitPrefs.from_system("us")
SI_PREFS = UnitPrefs.from_system("si")


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
        assert result["dewpoint"] == "50°F"
        assert "mi" in result["visibility"]
        assert "inHg" in result["pressure"]
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

        assert result["wind_gust"] == "Calm"

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
        mock_nws.get_detailed_forecast = m.get_detailed_forecast

        from stormscope.tools import get_forecast
        result = await get_forecast(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "error" not in result
        assert result["location"] == "Minneapolis, MN"
        assert len(result["periods"]) == 2
        assert result["periods"][0]["name"] == "Today"
        assert result["periods"][0]["temperature"] == "78°F"
        assert result["periods"][0]["dewpoint"] == "50°F"
        assert result["periods"][1]["dewpoint"] == "46°F"

    @patch("stormscope.tools._nws")
    async def test_hourly_mode(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_hourly_forecast = m.get_hourly_forecast
        mock_nws.get_detailed_forecast = m.get_detailed_forecast

        from stormscope.tools import get_forecast
        result = await get_forecast(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, mode="hourly")

        assert "error" not in result
        assert result["location"] == "Minneapolis, MN"
        assert len(result["periods"]) == 6
        assert "°F" in result["periods"][0]["temperature"]
        assert result["periods"][0]["dewpoint"] == "50°F"

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
        mock_nws.get_detailed_forecast = m.get_detailed_forecast

        from stormscope.tools import get_forecast
        result = await get_forecast(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, mode="hourly", hours=3)

        assert len(result["periods"]) == 3

    @patch("stormscope.tools._nws")
    async def test_daily_caps_to_days(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_forecast = m.get_forecast
        mock_nws.get_detailed_forecast = m.get_detailed_forecast

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
    async def test_returns_enriched_radar_data(self, mock_nws, mock_iem):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_stations = m.get_stations
        mock_nws.get_latest_observation = m.get_latest_observation
        mock_nws.get_hourly_forecast = m.get_hourly_forecast
        mock_iem.get_radar_info = AsyncMock(return_value=MOCK_RADAR_RESPONSE)

        from stormscope.tools import get_radar
        result = await get_radar(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "error" not in result
        assert result["station_id"] == "KMPX"
        assert "summary" in result
        assert "Mostly Sunny" in result["summary"]
        assert result["current_weather"] == "Mostly Sunny"
        assert result["cloud_cover"] == "FEW"
        assert "links" in result
        assert "regional_composite" in result["links"]
        assert "local_radar" in result["links"]
        assert "imagery_urls" not in result

    @patch("stormscope.tools._iem")
    @patch("stormscope.tools._nws")
    async def test_radar_with_precipitation(self, mock_nws, mock_iem):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_stations = m.get_stations
        mock_nws.get_hourly_forecast = m.get_hourly_forecast

        rainy_obs = dict(OBS_PROPS)
        rainy_obs["textDescription"] = "Light Rain"
        rainy_obs["presentWeather"] = [
            {"weather": "Rain", "intensity": "Light"},
        ]
        rainy_obs["cloudLayers"] = [
            {"base": {"value": 900, "unitCode": "wmoUnit:m"}, "amount": "OVC"},
        ]
        mock_nws.get_latest_observation = AsyncMock(return_value=rainy_obs)
        mock_iem.get_radar_info = AsyncMock(return_value=MOCK_RADAR_RESPONSE)

        from stormscope.tools import get_radar
        result = await get_radar(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "error" not in result
        assert result["current_weather"] == "Light Rain"
        assert result["cloud_cover"] == "OVC"
        assert "Rain" in result["summary"]
        assert "OVC" in result["summary"]

    @patch("stormscope.tools._iem")
    @patch("stormscope.tools._nws")
    async def test_radar_degrades_without_obs(self, mock_nws, mock_iem):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_stations = AsyncMock(return_value=[])
        mock_nws.get_hourly_forecast = AsyncMock(side_effect=Exception("API down"))
        mock_iem.get_radar_info = AsyncMock(return_value=MOCK_RADAR_RESPONSE)

        from stormscope.tools import get_radar
        result = await get_radar(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "error" not in result
        assert result["station_id"] == "KMPX"
        assert "summary" in result
        assert "links" in result

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
        mock_nws.get_detailed_forecast = m.get_detailed_forecast
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
        mock_nws.get_detailed_forecast = m.get_detailed_forecast
        mock_nws.get_hourly_forecast = m.get_hourly_forecast
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
        assert "summary" in result["radar"]
        assert "links" in result["radar"]

    @patch("stormscope.tools._spc")
    @patch("stormscope.tools._nws")
    async def test_degrades_gracefully(self, mock_nws, mock_spc):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_stations = m.get_stations
        mock_nws.get_latest_observation = m.get_latest_observation
        mock_nws.get_forecast = AsyncMock(side_effect=Exception("API down"))
        mock_nws.get_detailed_forecast = m.get_detailed_forecast
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
        mock_nws.get_detailed_forecast = m.get_detailed_forecast
        mock_nws.get_hourly_forecast = m.get_hourly_forecast
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


class TestSIFormatting:
    def test_fmt_temp_si(self):
        assert _fmt_temp(72.0, 22.0, SI_PREFS) == "22°C"

    def test_fmt_temp_si_none_celsius(self):
        assert _fmt_temp(72.0, None, SI_PREFS) == "N/A"

    def test_fmt_temp_us(self):
        assert _fmt_temp(72.0, 22.0, US_PREFS) == "72°F"

    def test_fmt_temp_us_none(self):
        assert _fmt_temp(None, 22.0, US_PREFS) == "N/A"

    def test_fmt_wind_si(self):
        assert _fmt_wind(15.0, "SW", SI_PREFS) == "SW 15 km/h"

    def test_fmt_wind_si_calm(self):
        assert _fmt_wind(None, None, SI_PREFS) == "Calm"

    def test_fmt_wind_kt(self):
        kt_prefs = UnitPrefs.from_system("us")
        kt_prefs = UnitPrefs(
            temperature="f", pressure="inhg", wind="kt",
            distance="mi", accumulation="in",
        )
        assert _fmt_wind(39.0, "SW", kt_prefs) == "SW 39 kt"

    def test_fmt_visibility_si(self):
        assert _fmt_visibility(10.0, 16093.0, SI_PREFS) == "16.1 km"

    def test_fmt_visibility_si_none(self):
        assert _fmt_visibility(10.0, None, SI_PREFS) == "N/A"

    def test_fmt_pressure_mb(self):
        assert _fmt_pressure(29.92, 101325.0, SI_PREFS) == "1013.2 mb"

    def test_fmt_pressure_mb_none(self):
        assert _fmt_pressure(29.92, None, SI_PREFS) == "N/A"

    def test_fmt_pressure_inhg(self):
        assert _fmt_pressure(29.92, 101325.0, US_PREFS) == "29.92 inHg"


class TestUpperAirFormatters:
    def test_fmt_upper_wind_no_direction(self):
        assert _fmt_upper_wind(20.0, None, US_PREFS) == "45 mph"

    def test_fmt_upper_wind_kt(self):
        kt_prefs = UnitPrefs(
            temperature="f", pressure="inhg", wind="kt",
            distance="mi", accumulation="in",
        )
        assert _fmt_upper_wind(20.0, None, kt_prefs) == "39 kt"

    def test_fmt_upper_wind_calm(self):
        assert _fmt_upper_wind(0.0, 270.0, US_PREFS) == "Calm"

    def test_fmt_upper_wind_none(self):
        assert _fmt_upper_wind(None, None, US_PREFS) == "N/A"

    def test_fmt_upper_wind_si(self):
        assert _fmt_upper_wind(20.0, 270.0, SI_PREFS) == "W 72 km/h"

    def test_fmt_upper_wind_ms(self):
        ms_prefs = UnitPrefs(
            temperature="c", pressure="mb", wind="ms",
            distance="km", accumulation="mm",
        )
        assert _fmt_upper_wind(20.0, 270.0, ms_prefs) == "W 20 m/s"

    def test_fmt_vorticity_none(self):
        assert _fmt_vorticity(None) == "N/A"

    def test_fmt_vorticity_scales(self):
        # 1e-5 s^-1 should format as 1.0
        assert _fmt_vorticity(1e-5) == "1.0"


class TestGetUpperAir:
    @patch("stormscope.tools._openmeteo")
    async def test_returns_time_series(self, mock_openmeteo):
        mock_openmeteo.get_upper_air = AsyncMock(return_value=MOCK_UPPER_AIR_RAW)

        from stormscope.tools import get_upper_air
        result = await get_upper_air(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "error" not in result
        assert result["level"] == "500 hPa"
        assert len(result["time_series"]) == 12
        assert "dam" in result["time_series"][0]["height"]
        assert result["attribution"] == "Weather data by Open-Meteo.com (CC-BY 4.0) — https://open-meteo.com/"
        assert result["height_trend"] in ("rising", "falling", "steady")
        assert result["vorticity_trend"] in ("rising", "falling", "steady")

    @patch("stormscope.tools._openmeteo")
    async def test_error_handling(self, mock_openmeteo):
        mock_openmeteo.get_upper_air = AsyncMock(
            side_effect=Exception("API unavailable"),
        )

        from stormscope.tools import get_upper_air
        result = await get_upper_air(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "error" in result

    @patch("stormscope.tools._openmeteo")
    async def test_vorticity_computed(self, mock_openmeteo):
        mock_openmeteo.get_upper_air = AsyncMock(return_value=MOCK_UPPER_AIR_RAW)

        from stormscope.tools import get_upper_air
        result = await get_upper_air(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        for entry in result["time_series"]:
            assert entry["relative_vorticity"] != "N/A"
            assert entry["absolute_vorticity"] != "N/A"

    @patch("stormscope.tools._openmeteo")
    async def test_partial_data_degrades_gracefully(self, mock_openmeteo):
        partial = {k: dict(v) for k, v in MOCK_UPPER_AIR_RAW.items()}
        # truncate south point wind arrays to 6 entries
        south_hourly = dict(partial["south"]["hourly"])
        south_hourly["wind_speed_500hPa"] = south_hourly["wind_speed_500hPa"][:6]
        south_hourly["wind_direction_500hPa"] = south_hourly["wind_direction_500hPa"][:6]
        partial["south"] = {**partial["south"], "hourly": south_hourly}
        mock_openmeteo.get_upper_air = AsyncMock(return_value=partial)

        from stormscope.tools import get_upper_air
        result = await get_upper_air(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "error" not in result
        assert len(result["time_series"]) == 12
        # first 6 entries should have vorticity, last 6 fall back to N/A
        assert result["time_series"][0]["relative_vorticity"] != "N/A"
        assert result["time_series"][11]["relative_vorticity"] == "N/A"

    @patch("stormscope.tools._openmeteo")
    async def test_si_units(self, mock_openmeteo):
        mock_openmeteo.get_upper_air = AsyncMock(return_value=MOCK_UPPER_AIR_RAW)

        from stormscope.tools import get_upper_air
        result = await get_upper_air(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, units="si")

        assert "km/h" in result["time_series"][0]["wind"]
        assert "°C" in result["time_series"][0]["temperature"]


class TestComputeTrend:
    def test_rising(self):
        from stormscope.tools import _compute_trend
        assert _compute_trend([1.0, 1.0, 1.0, 2.0, 2.0, 2.0]) == "rising"

    def test_falling(self):
        from stormscope.tools import _compute_trend
        assert _compute_trend([2.0, 2.0, 2.0, 1.0, 1.0, 1.0]) == "falling"

    def test_steady(self):
        from stormscope.tools import _compute_trend
        assert _compute_trend([5.0, 5.0, 5.0, 5.0, 5.0, 5.0]) == "steady"

    def test_fewer_than_three(self):
        from stormscope.tools import _compute_trend
        assert _compute_trend([1.0, 2.0]) == "steady"

    def test_empty(self):
        from stormscope.tools import _compute_trend
        assert _compute_trend([]) == "steady"

    def test_zero_first_avg_with_change(self):
        from stormscope.tools import _compute_trend
        # first third averages to 0, last third is positive
        assert _compute_trend([0.0, 0.0, 0.0, 1e-5, 1e-5, 1e-5]) == "rising"

    def test_all_zeros(self):
        from stormscope.tools import _compute_trend
        assert _compute_trend([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]) == "steady"


class TestHaversine:
    def test_known_distance(self):
        from stormscope.geo import haversine_km
        # Minneapolis to Chicago is ~571 km
        d = haversine_km(44.9778, -93.2650, 41.8781, -87.6298)
        assert 565 < d < 580

    def test_same_point(self):
        from stormscope.geo import haversine_km
        assert haversine_km(45.0, -93.0, 45.0, -93.0) == 0.0


class TestBearing:
    def test_due_north(self):
        from stormscope.tools import _bearing_deg
        b = _bearing_deg(44.0, -93.0, 46.0, -93.0)
        assert abs(b - 0) < 1

    def test_due_east(self):
        from stormscope.tools import _bearing_deg
        b = _bearing_deg(44.0, -93.0, 44.0, -91.0)
        assert 85 < b < 95


class TestGetSurfaceAnalysis:
    @patch("stormscope.tools._wpc")
    async def test_forecast_standard_detail(self, mock_wpc):
        mock_wpc.get_surface_analysis = AsyncMock(
            return_value=(MOCK_WPC_FRONTS, MOCK_WPC_PRESSURE_CENTERS),
        )

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, product="forecast", day=1)

        assert "error" not in result
        assert result["day"] == 1
        assert result["source"] == "WPC forecast chart"
        assert len(result["nearest_fronts"]) == 2
        assert len(result["nearest_pressure_centers"]) == 2
        assert result["nearest_fronts"][0]["type"] in ("cold", "warm")
        assert "distance" in result["nearest_fronts"][0]
        assert "bearing" in result["nearest_fronts"][0]
        assert "nearest_point" not in result["nearest_fronts"][0]

    @patch("stormscope.tools._wpc")
    async def test_forecast_full_detail(self, mock_wpc):
        mock_wpc.get_surface_analysis = AsyncMock(
            return_value=(MOCK_WPC_FRONTS, MOCK_WPC_PRESSURE_CENTERS),
        )

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(
            MINNEAPOLIS_LAT, MINNEAPOLIS_LON, product="forecast", day=1, detail="full",
        )

        assert "error" not in result
        assert len(result["nearest_fronts"]) == 2
        assert len(result["nearest_pressure_centers"]) == 2
        front = result["nearest_fronts"][0]
        assert "nearest_point" in front
        assert front["geometry_type"] == "MultiLineString"
        center = result["nearest_pressure_centers"][0]
        assert "coordinates" in center

    @patch("stormscope.tools._wpc")
    async def test_forecast_warm_sector_detection(self, mock_wpc):
        mock_wpc.get_surface_analysis = AsyncMock(
            return_value=(MOCK_WPC_FRONTS, MOCK_WPC_PRESSURE_CENTERS),
        )

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, product="forecast", day=1)

        cold_fronts = [f for f in result["nearest_fronts"] if f["type"] == "cold"]
        assert len(cold_fronts) > 0
        assert cold_fronts[0].get("position") == "warm side (ahead of front)"
        assert "location_summary" in result
        assert "warm side" in result["location_summary"]

    @patch("stormscope.tools._wpc")
    async def test_forecast_cold_sector_detection(self, mock_wpc):
        mock_wpc.get_surface_analysis = AsyncMock(
            return_value=(MOCK_WPC_FRONTS, MOCK_WPC_PRESSURE_CENTERS),
        )

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(48.0, -95.0, product="forecast", day=1)

        cold_fronts = [f for f in result["nearest_fronts"] if f["type"] == "cold"]
        assert len(cold_fronts) > 0
        assert cold_fronts[0].get("position") == "cold side (behind front)"

    @patch("stormscope.tools._wpc")
    async def test_forecast_empty_features(self, mock_wpc):
        empty = {"type": "FeatureCollection", "features": []}
        mock_wpc.get_surface_analysis = AsyncMock(return_value=(empty, empty))

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, product="forecast", day=1)

        assert "error" not in result
        assert result["nearest_fronts"] == []
        assert result["nearest_pressure_centers"] == []
        assert "location_summary" not in result

    @patch("stormscope.tools._wpc")
    async def test_forecast_error_handling(self, mock_wpc):
        mock_wpc.get_surface_analysis = AsyncMock(side_effect=Exception("API down"))

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, product="forecast", day=1)

        assert "error" in result

    async def test_forecast_invalid_day(self):
        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, product="forecast", day=0)
        assert "error" in result
        assert "invalid day" in result["error"]

    async def test_forecast_invalid_day_too_high(self):
        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, product="forecast", day=4)
        assert "error" in result

    @patch("stormscope.tools._wpc")
    async def test_forecast_unknown_front_type_skipped(self, mock_wpc):
        fronts_with_unknown = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"feat": "Imaginary Front Valid"},
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[-95.0, 47.0], [-93.0, 45.0]],
                    },
                },
                MOCK_WPC_FRONTS["features"][0],
            ],
        }
        mock_wpc.get_surface_analysis = AsyncMock(
            return_value=(fronts_with_unknown, MOCK_WPC_PRESSURE_CENTERS),
        )

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, product="forecast", day=1)

        assert len(result["nearest_fronts"]) == 1
        assert result["nearest_fronts"][0]["type"] == "cold"

    @patch("stormscope.tools._wpc")
    async def test_forecast_null_geometry_does_not_crash(self, mock_wpc):
        """GeoJSON features with geometry: null must be skipped without raising."""
        fronts_with_null_geom = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"feat": "COLD_FRONT"},
                    "geometry": None,
                },
                MOCK_WPC_FRONTS["features"][0],
            ],
        }
        centers_with_null_geom = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"feat": "LOW"},
                    "geometry": None,
                },
            ],
        }
        mock_wpc.get_surface_analysis = AsyncMock(
            return_value=(fronts_with_null_geom, centers_with_null_geom),
        )

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, product="forecast", day=1)

        assert "error" not in result
        assert len(result["nearest_fronts"]) == 1
        assert result["nearest_fronts"][0]["type"] == "cold"
        assert result["nearest_pressure_centers"] == []

    @patch("stormscope.tools._wpc")
    async def test_forecast_scope_local_suppresses_distant_cold_front(self, mock_wpc):
        # cold front ~800km south of Minneapolis
        fronts = {
            "type": "FeatureCollection",
            "features": [{
                "properties": {"feat": "Cold Front Valid"},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-95.0, 37.0], [-94.0, 36.0], [-93.0, 35.0]],
                },
            }],
        }
        centers = {
            "type": "FeatureCollection",
            "features": [{
                "properties": {"feat": "High Valid"},
                "geometry": {"type": "Point", "coordinates": [-100.0, 46.0]},
            }],
        }
        mock_wpc.get_surface_analysis = AsyncMock(return_value=(fronts, centers))

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(
            MINNEAPOLIS_LAT, MINNEAPOLIS_LON, product="forecast", day=1,
        )

        assert "location_summary" in result
        assert "warm side" not in result["location_summary"]
        assert "high" in result["location_summary"]

    @patch("stormscope.tools._codsus")
    async def test_analysis_default_product(self, mock_codsus):
        from stormscope.codsus import SurfaceAnalysis, Front, PressureCenter
        mock_codsus.get_analysis = AsyncMock(return_value=SurfaceAnalysis(
            valid_time="261500Z",
            fronts=[
                Front(type="cold", strength="standard", coords=[
                    (47.0, -95.0), (46.0, -94.0), (45.0, -93.0), (44.0, -92.0),
                ]),
            ],
            pressure_centers=[
                PressureCenter(type="low", pressure_mb=1007, lat=45.0, lon=-91.5),
            ],
        ))

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "error" not in result
        assert "warning" not in result
        assert result["source"] == "WPC surface analysis (CODSUS)"
        assert result["valid_time"] == "261500Z"
        assert len(result["nearest_fronts"]) == 1
        assert result["nearest_fronts"][0]["type"] == "cold"
        assert len(result["nearest_pressure_centers"]) == 1
        assert result["nearest_pressure_centers"][0]["pressure_mb"] == 1007

    @patch("stormscope.tools._codsus")
    async def test_analysis_full_detail(self, mock_codsus):
        from stormscope.codsus import SurfaceAnalysis, Front, PressureCenter
        mock_codsus.get_analysis = AsyncMock(return_value=SurfaceAnalysis(
            valid_time="261500Z",
            fronts=[
                Front(type="cold", strength="weak", coords=[
                    (47.0, -95.0), (46.0, -94.0), (45.0, -93.0),
                ]),
            ],
            pressure_centers=[
                PressureCenter(type="low", pressure_mb=1007, lat=45.0, lon=-91.5),
            ],
        ))

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, detail="full")

        front = result["nearest_fronts"][0]
        assert "nearest_point" in front
        assert "latitude" in front["nearest_point"]
        assert front["strength"] == "weak"
        center = result["nearest_pressure_centers"][0]
        assert "coordinates" in center

    @patch("stormscope.tools._codsus")
    async def test_analysis_warm_sector_detection(self, mock_codsus):
        from stormscope.codsus import SurfaceAnalysis, Front
        # cold front running NW-SE: Minneapolis is south/east, should be warm side
        mock_codsus.get_analysis = AsyncMock(return_value=SurfaceAnalysis(
            valid_time="261500Z",
            fronts=[
                Front(type="cold", strength="standard", coords=[
                    (47.0, -95.0), (46.0, -94.0), (45.0, -93.0), (44.0, -92.0),
                ]),
            ],
            pressure_centers=[],
        ))

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        cold_fronts = [f for f in result["nearest_fronts"] if f["type"] == "cold"]
        assert len(cold_fronts) > 0
        assert cold_fronts[0].get("position") == "warm side (ahead of front)"
        assert "location_summary" in result
        assert "warm side" in result["location_summary"]

    @patch("stormscope.tools._codsus")
    async def test_analysis_cold_sector_detection(self, mock_codsus):
        from stormscope.codsus import SurfaceAnalysis, Front
        mock_codsus.get_analysis = AsyncMock(return_value=SurfaceAnalysis(
            valid_time="261500Z",
            fronts=[
                Front(type="cold", strength="standard", coords=[
                    (47.0, -95.0), (46.0, -94.0), (45.0, -93.0), (44.0, -92.0),
                ]),
            ],
            pressure_centers=[],
        ))

        from stormscope.tools import get_surface_analysis
        # point north of the cold front should be on cold side
        result = await get_surface_analysis(48.0, -95.0)

        cold_fronts = [f for f in result["nearest_fronts"] if f["type"] == "cold"]
        assert len(cold_fronts) > 0
        assert cold_fronts[0].get("position") == "cold side (behind front)"

    @patch("stormscope.tools._codsus")
    async def test_analysis_single_coord_front_skipped(self, mock_codsus):
        from stormscope.codsus import SurfaceAnalysis, Front
        mock_codsus.get_analysis = AsyncMock(return_value=SurfaceAnalysis(
            valid_time="261500Z",
            fronts=[
                Front(type="cold", strength="standard", coords=[(45.0, -93.0)]),
            ],
            pressure_centers=[],
        ))

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "error" not in result
        assert result["nearest_fronts"] == []

    @patch("stormscope.tools._codsus")
    async def test_analysis_error_handling(self, mock_codsus):
        mock_codsus.get_analysis = AsyncMock(side_effect=Exception("API down"))

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "error" in result

    async def test_analysis_day_greater_than_1_errors(self):
        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, product="analysis", day=2)
        assert "error" in result
        assert "forecast" in result["error"]

    @patch("stormscope.tools._codsus")
    async def test_analysis_day_1_warns(self, mock_codsus):
        from stormscope.codsus import SurfaceAnalysis
        mock_codsus.get_analysis = AsyncMock(return_value=SurfaceAnalysis(
            valid_time="261500Z", fronts=[], pressure_centers=[],
        ))

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, product="analysis", day=1)

        assert "warning" in result
        assert "forecast" in result["warning"]

    @patch("stormscope.tools._codsus")
    async def test_scope_local_suppresses_distant_cold_front(self, mock_codsus):
        from stormscope.codsus import SurfaceAnalysis, Front, PressureCenter
        # cold front far away (~800km south)
        mock_codsus.get_analysis = AsyncMock(return_value=SurfaceAnalysis(
            valid_time="261500Z",
            fronts=[
                Front(type="cold", strength="standard", coords=[
                    (37.0, -95.0), (36.0, -94.0), (35.0, -93.0),
                ]),
            ],
            pressure_centers=[
                PressureCenter(type="high", pressure_mb=1036, lat=46.0, lon=-100.0),
            ],
        ))

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        # default scope is local — should not mention warm/cold sector for distant front
        assert "location_summary" in result
        assert "warm side" not in result["location_summary"]
        assert "high" in result["location_summary"]

    @patch("stormscope.tools._codsus")
    async def test_scope_all_includes_distant_cold_front(self, mock_codsus):
        from stormscope.codsus import SurfaceAnalysis, Front
        mock_codsus.get_analysis = AsyncMock(return_value=SurfaceAnalysis(
            valid_time="261500Z",
            fronts=[
                Front(type="cold", strength="standard", coords=[
                    (37.0, -95.0), (36.0, -94.0), (35.0, -93.0),
                ]),
            ],
            pressure_centers=[],
        ))

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, scope="all")

        assert "location_summary" in result
        assert "warm side" in result["location_summary"] or "cold side" in result["location_summary"]

    @patch("stormscope.tools._codsus")
    async def test_summary_falls_back_to_pressure_center(self, mock_codsus):
        from stormscope.codsus import SurfaceAnalysis, Front, PressureCenter
        # only a trough (no cold front) + pressure center
        mock_codsus.get_analysis = AsyncMock(return_value=SurfaceAnalysis(
            valid_time="261500Z",
            fronts=[
                Front(type="trough", strength="standard", coords=[
                    (42.0, -85.0), (44.0, -87.0),
                ]),
            ],
            pressure_centers=[
                PressureCenter(type="high", pressure_mb=1038, lat=46.0, lon=-100.0),
            ],
        ))

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "location_summary" in result
        assert "1038 mb" in result["location_summary"]
        assert "high" in result["location_summary"]

    @patch("stormscope.tools._codsus")
    async def test_no_summary_when_no_features(self, mock_codsus):
        from stormscope.codsus import SurfaceAnalysis
        mock_codsus.get_analysis = AsyncMock(return_value=SurfaceAnalysis(
            valid_time="261500Z", fronts=[], pressure_centers=[],
        ))

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "location_summary" not in result

    async def test_invalid_product(self):
        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, product="bogus")
        assert "error" in result
        assert "invalid product" in result["error"]

    async def test_invalid_scope(self):
        from stormscope.server import get_surface_analysis
        result = await get_surface_analysis(
            latitude=MINNEAPOLIS_LAT, longitude=MINNEAPOLIS_LON, scope="nearby",
        )
        assert "error" in result
        assert "invalid scope" in result["error"]


class TestMultiLineStringSegments:
    """verify that disconnected MultiLineString segments are processed independently,
    not flattened into phantom cross-continent connections."""

    @patch("stormscope.tools._wpc")
    async def test_disconnected_segments_no_phantom(self, mock_wpc):
        # two cold front segments far apart: one in Missouri, one in Maine.
        # Minneapolis is ~350 mi from Missouri and ~1000 mi from Maine.
        # if flattened, a phantom segment connects Missouri to Maine and passes
        # near Minneapolis, producing a spurious ~30 mi result.
        fronts_disconnected = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"feat": "Cold Front Valid"},
                "geometry": {
                    "type": "MultiLineString",
                    "coordinates": [
                        # segment 1: Missouri
                        [[-94.0, 39.0], [-92.0, 39.5], [-90.0, 39.7]],
                        # segment 2: Maine (far from Minneapolis)
                        [[-70.0, 48.0], [-69.0, 47.5], [-68.0, 47.0]],
                    ],
                },
            }],
        }
        empty_centers = {"type": "FeatureCollection", "features": []}
        mock_wpc.get_surface_analysis = AsyncMock(
            return_value=(fronts_disconnected, empty_centers),
        )

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, product="forecast", day=1)

        front = result["nearest_fronts"][0]
        # nearest real segment is Missouri at ~550-620 km (340-385 mi),
        # not a phantom segment at ~50 km
        assert front["distance_km"] > 500


class TestNearestPointOnLine:
    def test_midpoint_of_segment(self):
        from stormscope.tools import _nearest_point_on_line
        # point directly south of the midpoint of a W-E segment
        coords = [[-94.0, 46.0], [-92.0, 46.0]]
        nlat, nlon, dist = _nearest_point_on_line(45.0, -93.0, coords)
        assert abs(nlon - (-93.0)) < 0.01
        assert abs(nlat - 46.0) < 0.01
        assert 100 < dist < 120  # ~111 km per degree of latitude

    def test_clamps_to_segment_start(self):
        from stormscope.tools import _nearest_point_on_line
        # point far west of a short segment
        coords = [[-90.0, 45.0], [-89.0, 45.0]]
        nlat, nlon, dist = _nearest_point_on_line(45.0, -95.0, coords)
        assert abs(nlon - (-90.0)) < 0.01
        assert abs(nlat - 45.0) < 0.01

    def test_clamps_to_segment_end(self):
        from stormscope.tools import _nearest_point_on_line
        # point far east of a short segment
        coords = [[-95.0, 45.0], [-94.0, 45.0]]
        nlat, nlon, dist = _nearest_point_on_line(45.0, -89.0, coords)
        assert abs(nlon - (-94.0)) < 0.01
        assert abs(nlat - 45.0) < 0.01

    def test_single_point_linestring(self):
        from stormscope.tools import _nearest_point_on_line
        coords = [[-93.0, 45.0]]
        nlat, nlon, dist = _nearest_point_on_line(45.0, -93.0, coords)
        assert dist == 0.0
        assert abs(nlat - 45.0) < 0.01
        assert abs(nlon - (-93.0)) < 0.01

    def test_single_point_nonzero_distance(self):
        from stormscope.tools import _nearest_point_on_line
        coords = [[-93.0, 46.0]]
        nlat, nlon, dist = _nearest_point_on_line(45.0, -93.0, coords)
        assert 100 < dist < 120
        assert abs(nlat - 46.0) < 0.01

    def test_degenerate_zero_length_segment(self):
        from stormscope.tools import _nearest_point_on_line
        coords = [[-93.0, 45.0], [-93.0, 45.0]]
        nlat, nlon, dist = _nearest_point_on_line(45.0, -93.0, coords)
        assert dist == 0.0


class TestWhichSideOfFront:
    def test_warm_side(self):
        from stormscope.tools import _which_side_of_front
        # NW-SE cold front, point to the SE (warm sector)
        coords = [[-95.0, 47.0], [-93.0, 45.0]]
        result = _which_side_of_front(44.0, -92.0, coords, "cold")
        assert result == "warm side (ahead of front)"

    def test_cold_side(self):
        from stormscope.tools import _which_side_of_front
        # NW-SE cold front, point to the north (cold sector)
        coords = [[-95.0, 47.0], [-93.0, 45.0]]
        result = _which_side_of_front(48.0, -95.0, coords, "cold")
        assert result == "cold side (behind front)"

    def test_non_cold_front_returns_none(self):
        from stormscope.tools import _which_side_of_front
        coords = [[-95.0, 43.0], [-91.0, 44.0]]
        assert _which_side_of_front(44.0, -93.0, coords, "warm") is None
        assert _which_side_of_front(44.0, -93.0, coords, "stationary") is None
        assert _which_side_of_front(44.0, -93.0, coords, "occluded") is None
        assert _which_side_of_front(44.0, -93.0, coords, "trough") is None

    def test_on_front_line_defaults_warm(self):
        from stormscope.tools import _which_side_of_front
        # point exactly on the line extension (cross product == 0)
        coords = [[-95.0, 47.0], [-93.0, 45.0]]
        result = _which_side_of_front(46.0, -94.0, coords, "cold")
        assert result == "warm side (ahead of front)"


class TestFmtDistance:
    def test_us_units(self):
        result = _fmt_distance(160.934, US_PREFS)
        assert "mi" in result
        assert "100" in result

    def test_si_units(self):
        result = _fmt_distance(150.0, SI_PREFS)
        assert result == "150 km"

    def test_si_rounds(self):
        result = _fmt_distance(150.7, SI_PREFS)
        assert result == "151 km"


class TestFmtAccumulation:
    def test_inches(self):
        assert _fmt_accumulation(25.4, US_PREFS) == "1.00 in"

    def test_mm(self):
        assert _fmt_accumulation(25.4, SI_PREFS) == "25.4 mm"

    def test_cm(self):
        cm_prefs = UnitPrefs(
            temperature="f", pressure="inhg", wind="mph",
            distance="mi", accumulation="cm",
        )
        assert _fmt_accumulation(25.4, cm_prefs) == "2.5 cm"

    def test_zero(self):
        assert _fmt_accumulation(0, US_PREFS) == "0"

    def test_none(self):
        assert _fmt_accumulation(None, US_PREFS) == "0"

    def test_small_value(self):
        assert _fmt_accumulation(2.5, US_PREFS) == "0.10 in"


class TestFrostPoint:
    @patch("stormscope.tools._nws")
    async def test_conditions_frost_point(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_stations = m.get_stations
        mock_nws.get_latest_observation = AsyncMock(return_value=MOCK_OBSERVATION_COLD)

        from stormscope.tools import get_conditions
        result = await get_conditions(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "frost_point" in result
        assert "dewpoint" not in result
        assert "°F" in result["frost_point"]

    @patch("stormscope.tools._nws")
    async def test_conditions_dewpoint_above_zero(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_stations = m.get_stations
        mock_nws.get_latest_observation = m.get_latest_observation

        from stormscope.tools import get_conditions
        result = await get_conditions(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "dewpoint" in result
        assert "frost_point" not in result

    @patch("stormscope.tools._nws")
    async def test_forecast_frost_point(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_forecast = m.get_forecast
        mock_nws.get_detailed_forecast = AsyncMock(return_value=GRIDPOINT_COLD_PROPS)

        from stormscope.tools import get_forecast
        result = await get_forecast(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        period = result["periods"][0]
        assert "frost_point" in period
        assert "dewpoint" not in period


class TestForecastEnrichedFields:
    @patch("stormscope.tools._nws")
    async def test_daily_has_pressure_and_feels_like(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_forecast = m.get_forecast
        mock_nws.get_detailed_forecast = m.get_detailed_forecast

        from stormscope.tools import get_forecast
        result = await get_forecast(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        period = result["periods"][0]
        assert "pressure" in period
        assert period["pressure"] != "N/A"
        assert "feels_like" in period
        assert period["feels_like"] != "N/A"

    @patch("stormscope.tools._nws")
    async def test_daily_has_snow_accumulation(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_forecast = m.get_forecast
        mock_nws.get_detailed_forecast = m.get_detailed_forecast

        from stormscope.tools import get_forecast
        result = await get_forecast(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        # "Today" period (12:00-18:00 UTC) should have snow from mock data
        period = result["periods"][0]
        assert "snow_accumulation" in period
        assert "in" in period["snow_accumulation"]

    @patch("stormscope.tools._nws")
    async def test_daily_pressure_trend(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_forecast = m.get_forecast
        mock_nws.get_detailed_forecast = m.get_detailed_forecast

        from stormscope.tools import get_forecast
        result = await get_forecast(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "pressure_trend" in result
        assert result["pressure_trend"] in ("rising", "falling", "steady")

    @patch("stormscope.tools._nws")
    async def test_hourly_has_enriched_fields(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_hourly_forecast = m.get_hourly_forecast
        mock_nws.get_detailed_forecast = m.get_detailed_forecast

        from stormscope.tools import get_forecast
        result = await get_forecast(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, mode="hourly")

        period = result["periods"][0]
        assert "pressure" in period
        assert "feels_like" in period

    @patch("stormscope.tools._nws")
    async def test_raw_mode_includes_new_params(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_detailed_forecast = m.get_detailed_forecast

        from stormscope.tools import get_forecast
        result = await get_forecast(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, mode="raw")

        grid = result["grid"]
        assert "apparentTemperature" in grid
        assert "pressure" in grid
        assert "snowfallAmount" in grid
        assert "iceAccumulation" in grid


class TestUnitsOverride:
    @patch("stormscope.tools._nws")
    async def test_conditions_si(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_stations = m.get_stations
        mock_nws.get_latest_observation = m.get_latest_observation

        from stormscope.tools import get_conditions
        result = await get_conditions(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, units="si")

        assert "°C" in result["temperature"]
        assert "km" in result["visibility"]
        assert "mb" in result["pressure"]

    @patch("stormscope.tools._nws")
    async def test_conditions_us_with_pressure_override(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_stations = m.get_stations
        mock_nws.get_latest_observation = m.get_latest_observation

        from stormscope.tools import get_conditions
        result = await get_conditions(
            MINNEAPOLIS_LAT, MINNEAPOLIS_LON, units="us,pressure:mb",
        )

        assert "°F" in result["temperature"]
        assert "mb" in result["pressure"]
        assert "mi" in result["visibility"]

    @patch("stormscope.tools._nws")
    async def test_conditions_wind_kt_override(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_stations = m.get_stations
        mock_nws.get_latest_observation = m.get_latest_observation

        from stormscope.tools import get_conditions
        result = await get_conditions(
            MINNEAPOLIS_LAT, MINNEAPOLIS_LON, units="us,wind:kt",
        )

        # wind should be in knots (observation wind is 3.6 km/h -> ~1 kt)
        assert "kt" in result["wind"] or result["wind"] == "Calm"


class TestTempestIntegration:
    """integration tests for tempest enrichment in conditions and forecast."""

    def _mock_tempest(self):
        from unittest.mock import AsyncMock
        from stormscope.tempest import TempestClient
        mock = AsyncMock(spec=TempestClient)
        obs = dict(MOCK_TEMPEST_OBSERVATION_RESPONSE["obs"][0])
        obs["station_name"] = "Holz Lake"
        mock.get_observations.return_value = obs
        mock.get_stations.return_value = MOCK_TEMPEST_STATIONS_RESPONSE["stations"]
        mock.resolve_station.return_value = TEMPEST_STATION_NEARBY
        mock.get_forecast.return_value = MOCK_TEMPEST_FORECAST_RESPONSE
        mock.normalize_obs.side_effect = lambda o, p: o
        return mock

    @patch("stormscope.tools._tempest")
    @patch("stormscope.tools._nws")
    async def test_conditions_include_tempest_fields(self, mock_nws, mock_tempest):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_stations = m.get_stations
        mock_nws.get_latest_observation = m.get_latest_observation

        t = self._mock_tempest()
        mock_tempest.resolve_station = t.resolve_station
        mock_tempest.get_observations = t.get_observations
        mock_tempest.normalize_obs = t.normalize_obs

        from stormscope.tools import get_conditions
        result = await get_conditions(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "error" not in result
        assert "solar_radiation" in result
        assert "uv_index" in result
        assert "air_density" in result
        assert "wet_bulb_temperature" in result
        assert "tempest_station" in result

    @patch("stormscope.tools._tempest", None)
    @patch("stormscope.tools._nws")
    async def test_conditions_without_tempest(self, mock_nws):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_stations = m.get_stations
        mock_nws.get_latest_observation = m.get_latest_observation

        from stormscope.tools import get_conditions
        result = await get_conditions(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "error" not in result
        assert "solar_radiation" not in result
        assert "uv_index" not in result

    @patch("stormscope.tools._tempest")
    @patch("stormscope.tools._nws")
    async def test_forecast_includes_sunrise_sunset(self, mock_nws, mock_tempest):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_forecast = m.get_forecast
        mock_nws.get_detailed_forecast = m.get_detailed_forecast

        t = self._mock_tempest()
        mock_tempest.resolve_station = t.resolve_station
        mock_tempest.get_forecast = t.get_forecast

        from stormscope.tools import get_forecast
        result = await get_forecast(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "error" not in result
        # Tempest data merged — station name propagated
        assert "tempest_station" in result

    @patch("stormscope.tools._tempest")
    @patch("stormscope.tools._nws")
    async def test_tempest_offline_graceful_degradation(self, mock_nws, mock_tempest):
        m = _mock_nws()
        mock_nws.get_point = m.get_point
        mock_nws.get_stations = m.get_stations
        mock_nws.get_latest_observation = m.get_latest_observation

        # simulate Tempest API failure
        mock_tempest.resolve_station.side_effect = Exception("API down")

        from stormscope.tools import get_conditions
        result = await get_conditions(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        # NWS data returned without error
        assert "error" not in result
        assert "temperature" in result
        assert "solar_radiation" not in result

    def test_merge_conditions_uses_normalized_units(self):
        """B1: _merge_tempest_conditions must use normalize_obs output, not raw obs."""
        from stormscope.tempest import TempestClient
        from stormscope.tools import _merge_tempest_conditions

        client = TempestClient(token="test")
        obs = {
            "air_temperature": 0.0,       # 0°C → 32°F
            "wind_avg": 10.0,             # 10 m/s → 22.37 mph
            "station_pressure": 1013.25,  # mb → ~29.92 inHg
            "wind_direction": 270,
            "solar_radiation": 200,
        }
        nws_result = {
            "temperature": "50°F",
            "wind": "W 5 mph",
            "pressure": "29.00 inHg",
        }

        import stormscope.tools as tools_mod
        orig = tools_mod._tempest
        tools_mod._tempest = client
        try:
            result = _merge_tempest_conditions(nws_result, obs, US_PREFS)
        finally:
            tools_mod._tempest = orig

        # temperature must be 32°F (converted from 0°C), not 0°F (raw value)
        assert result["temperature"] == "32°F"
        assert result["data_source"] == "tempest"
        # wind must show ~22 mph (converted from 10 m/s), not raw 10
        wind_str = result["wind"]
        wind_val = int(wind_str.split()[1])
        assert 21 <= wind_val <= 23, f"expected ~22 mph, got {wind_str}"
        # pressure must show inHg (~29.92), not raw mb value
        assert "inHg" in result["pressure"]
        inhg_val = float(result["pressure"].split()[0])
        assert 29.8 <= inhg_val <= 30.1, f"expected ~29.92 inHg, got {result['pressure']}"

    def test_merge_forecast_no_tempest_hourly_key(self):
        """S2: _merge_tempest_forecast must not leak _tempest_hourly into output."""
        from stormscope.tools import _merge_tempest_forecast

        nws_result = {"periods": [], "location": "Minneapolis, MN"}
        result = _merge_tempest_forecast(nws_result, MOCK_TEMPEST_FORECAST_RESPONSE, US_PREFS)

        assert "_tempest_hourly" not in result

    def test_merge_forecast_hourly_wind_gust(self):
        """hourly Tempest wind_gust surfaces as tempest_wind_gust on matching period."""
        from stormscope.tools import _merge_tempest_forecast
        from datetime import datetime, timezone

        hourly_epoch = MOCK_TEMPEST_FORECAST_RESPONSE["forecast"]["hourly"][0]["time"]
        start_str = datetime.fromtimestamp(hourly_epoch, tz=timezone.utc).isoformat()
        nws_result = {
            "periods": [{"start_time": start_str, "name": "This Hour"}],
            "location": "Minneapolis, MN",
        }
        result = _merge_tempest_forecast(nws_result, MOCK_TEMPEST_FORECAST_RESPONSE, US_PREFS)
        period = result["periods"][0]
        assert "tempest_wind_gust" in period
        assert "15" in period["tempest_wind_gust"]
        # first hourly entry has precip_type: "none" — must not appear in output
        assert "tempest_precip_type" not in period

    def test_merge_forecast_hourly_conditions_override(self):
        """hourly conditions overrides daily tempest_conditions when both match the same period."""
        from stormscope.tools import _merge_tempest_forecast
        from datetime import datetime, timezone

        # second hourly entry (time: 1741050000) falls on the same date as the first daily
        # entry, so the daily block sets tempest_conditions = "Partly Cloudy" first;
        # the hourly block then overwrites it with "Snow Likely"
        hourly_epoch = MOCK_TEMPEST_FORECAST_RESPONSE["forecast"]["hourly"][1]["time"]
        start_str = datetime.fromtimestamp(hourly_epoch, tz=timezone.utc).isoformat()
        nws_result = {
            "periods": [{"start_time": start_str, "name": "This Hour"}],
            "location": "Minneapolis, MN",
        }
        result = _merge_tempest_forecast(nws_result, MOCK_TEMPEST_FORECAST_RESPONSE, US_PREFS)
        period = result["periods"][0]
        assert period.get("tempest_conditions") == "Snow Likely"

    def test_merge_forecast_hourly_precip_type(self):
        """hourly Tempest precip_type surfaces on matching period."""
        from stormscope.tools import _merge_tempest_forecast
        from datetime import datetime, timezone

        hourly_epoch = MOCK_TEMPEST_FORECAST_RESPONSE["forecast"]["hourly"][1]["time"]
        start_str = datetime.fromtimestamp(hourly_epoch, tz=timezone.utc).isoformat()
        nws_result = {
            "periods": [{"start_time": start_str, "name": "This Hour"}],
            "location": "Minneapolis, MN",
        }
        result = _merge_tempest_forecast(nws_result, MOCK_TEMPEST_FORECAST_RESPONSE, US_PREFS)
        period = result["periods"][0]
        assert period.get("tempest_precip_type") == "snow"

    def test_merge_forecast_hourly_precip_type_none_suppressed(self):
        """precip_type "none" from Tempest must not surface as tempest_precip_type."""
        from stormscope.tools import _merge_tempest_forecast
        from datetime import datetime, timezone

        # first hourly entry has precip_type: "none"
        hourly_epoch = MOCK_TEMPEST_FORECAST_RESPONSE["forecast"]["hourly"][0]["time"]
        start_str = datetime.fromtimestamp(hourly_epoch, tz=timezone.utc).isoformat()
        nws_result = {
            "periods": [{"start_time": start_str, "name": "This Hour"}],
            "location": "Minneapolis, MN",
        }
        result = _merge_tempest_forecast(nws_result, MOCK_TEMPEST_FORECAST_RESPONSE, US_PREFS)
        period = result["periods"][0]
        assert "tempest_precip_type" not in period

    def test_merge_forecast_hourly_no_match(self):
        """NWS periods at non-matching times get no hourly Tempest fields."""
        from stormscope.tools import _merge_tempest_forecast

        nws_result = {
            "periods": [{"start_time": "2099-01-01T00:00:00+00:00", "name": "Far Future"}],
            "location": "Minneapolis, MN",
        }
        result = _merge_tempest_forecast(nws_result, MOCK_TEMPEST_FORECAST_RESPONSE, US_PREFS)
        period = result["periods"][0]
        assert "tempest_wind_gust" not in period
        assert "tempest_precip_type" not in period
        assert "tempest_conditions" not in period

    def test_merge_forecast_precip_cm_conversion(self):
        """S4: daily precip from Tempest (mm) must be converted to cm when requested."""
        from stormscope.tools import _merge_tempest_forecast
        from stormscope.units import UnitPrefs
        from datetime import datetime, timezone

        si_cm_prefs = UnitPrefs(
            temperature="c", pressure="mb", wind="kmh", distance="km", accumulation="cm",
        )
        # derive the date from the mock epoch so they match regardless of comment accuracy
        day_epoch = MOCK_TEMPEST_FORECAST_RESPONSE["forecast"]["daily"][0]["day_start_local"]
        date_str = datetime.fromtimestamp(day_epoch, tz=timezone.utc).strftime("%Y-%m-%d")
        nws_result = {
            "periods": [{"start_time": f"{date_str}T06:00:00+00:00", "name": "Today"}],
            "location": "Minneapolis, MN",
        }
        result = _merge_tempest_forecast(nws_result, MOCK_TEMPEST_FORECAST_RESPONSE, si_cm_prefs)
        period = result["periods"][0]
        assert "tempest_precip" in period
        assert "cm" in period["tempest_precip"]

    def test_merge_forecast_precip_mm_passthrough(self):
        """S4: daily precip stays in mm when accumulation pref is mm."""
        from stormscope.tools import _merge_tempest_forecast
        from stormscope.units import UnitPrefs
        from datetime import datetime, timezone

        si_prefs = UnitPrefs(
            temperature="c", pressure="mb", wind="kmh", distance="km", accumulation="mm",
        )
        day_epoch = MOCK_TEMPEST_FORECAST_RESPONSE["forecast"]["daily"][0]["day_start_local"]
        date_str = datetime.fromtimestamp(day_epoch, tz=timezone.utc).strftime("%Y-%m-%d")
        nws_result = {
            "periods": [{"start_time": f"{date_str}T06:00:00+00:00", "name": "Today"}],
            "location": "Minneapolis, MN",
        }
        result = _merge_tempest_forecast(nws_result, MOCK_TEMPEST_FORECAST_RESPONSE, si_prefs)
        period = result["periods"][0]
        assert "tempest_precip" in period
        assert "mm" in period["tempest_precip"]

    @patch("stormscope.tools._tempest")
    async def test_get_tempest_station_location_uses_resolve_station(self, mock_tempest):
        """S1: get_tempest_station_location delegates to resolve_station, not duplicate loop."""
        from unittest.mock import AsyncMock
        mock_tempest.resolve_station = AsyncMock(return_value=TEMPEST_STATION_NEARBY)

        from stormscope.tools import get_tempest_station_location
        result = await get_tempest_station_location()

        assert result is not None
        lat, lon = result
        assert lat == TEMPEST_STATION_NEARBY["latitude"]
        assert lon == TEMPEST_STATION_NEARBY["longitude"]
        # called with dummy coords and bypass_distance_check=True
        mock_tempest.resolve_station.assert_awaited_once_with(
            0.0, 0.0,
            station_id=None,
            station_name=None,
            bypass_distance_check=True,
        )

    def test_merge_conditions_tempest_data_source_unconditional(self):
        """Tempest data_source is always 'tempest' when _merge_tempest_conditions is called."""
        from stormscope.tools import _merge_tempest_conditions

        obs = {
            "solar_radiation": 450,
            "uv": 3.2,
            "station_name": "Holz Lake",
        }
        nws_result = {
            "temperature": "72°F",
            "observation_time": "N/A",
        }
        result = _merge_tempest_conditions(nws_result, obs, US_PREFS)

        assert result["data_source"] == "tempest"
        # no air_temperature in obs, so NWS temperature is not overwritten
        assert result["temperature"] == "72°F"
        assert result["uv_index"] == 3.2

    def test_merge_conditions_sensor_divergence_large_diff(self):
        """sensor_divergence is emitted when Tempest and NWS temps differ by >5°F."""
        from stormscope.tempest import TempestClient
        from stormscope.tools import _merge_tempest_conditions

        client = TempestClient(token="test")
        # -2.28°C → ~27.9°F; NWS reports 58°F → diff ~30°F
        obs = {"air_temperature": -2.28}
        nws_result = {"temperature": "58°F"}

        import stormscope.tools as tools_mod
        orig = tools_mod._tempest
        tools_mod._tempest = client
        try:
            result = _merge_tempest_conditions(nws_result, obs, US_PREFS, nws_temp_f=58.0)
        finally:
            tools_mod._tempest = orig

        assert "sensor_divergence" in result
        assert "27." in result["sensor_divergence"]

    def test_merge_conditions_sensor_divergence_small_diff(self):
        """no sensor_divergence when Tempest and NWS temps are within 5°F."""
        from stormscope.tempest import TempestClient
        from stormscope.tools import _merge_tempest_conditions

        client = TempestClient(token="test")
        # -2.28°C → ~27.9°F; NWS reports 28°F → diff ~0.1°F
        obs = {"air_temperature": -2.28}
        nws_result = {"temperature": "28°F"}

        import stormscope.tools as tools_mod
        orig = tools_mod._tempest
        tools_mod._tempest = client
        try:
            result = _merge_tempest_conditions(nws_result, obs, US_PREFS, nws_temp_f=28.0)
        finally:
            tools_mod._tempest = orig

        assert "sensor_divergence" not in result


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
    MOCK_UPPER_AIR_RAW,
    MOCK_WPC_FRONTS,
    MOCK_WPC_PRESSURE_CENTERS,
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
        from stormscope.tools import _haversine_km
        # Minneapolis to Chicago is ~571 km
        d = _haversine_km(44.9778, -93.2650, 41.8781, -87.6298)
        assert 565 < d < 580

    def test_same_point(self):
        from stormscope.tools import _haversine_km
        assert _haversine_km(45.0, -93.0, 45.0, -93.0) == 0.0


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
    async def test_standard_detail(self, mock_wpc):
        mock_wpc.get_surface_analysis = AsyncMock(
            return_value=(MOCK_WPC_FRONTS, MOCK_WPC_PRESSURE_CENTERS),
        )

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "error" not in result
        assert result["day"] == 1
        assert len(result["nearest_fronts"]) == 2
        assert len(result["nearest_pressure_centers"]) == 2
        assert result["nearest_fronts"][0]["type"] in ("cold", "warm")
        assert "distance" in result["nearest_fronts"][0]
        assert "bearing" in result["nearest_fronts"][0]
        # should not have full-detail fields
        assert "nearest_point" not in result["nearest_fronts"][0]

    @patch("stormscope.tools._wpc")
    async def test_full_detail(self, mock_wpc):
        mock_wpc.get_surface_analysis = AsyncMock(
            return_value=(MOCK_WPC_FRONTS, MOCK_WPC_PRESSURE_CENTERS),
        )

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, detail="full")

        assert "error" not in result
        # full detail returns all fronts unsliced with extra fields
        assert len(result["nearest_fronts"]) == 2
        assert len(result["nearest_pressure_centers"]) == 2
        front = result["nearest_fronts"][0]
        assert "nearest_point" in front
        assert "geometry_type" in front
        center = result["nearest_pressure_centers"][0]
        assert "coordinates" in center

    @patch("stormscope.tools._wpc")
    async def test_warm_sector_detection(self, mock_wpc):
        mock_wpc.get_surface_analysis = AsyncMock(
            return_value=(MOCK_WPC_FRONTS, MOCK_WPC_PRESSURE_CENTERS),
        )

        from stormscope.tools import get_surface_analysis
        # Minneapolis (44.98, -93.27) is south/east of the cold front line
        # which runs NW-SE. Should be on the warm side.
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        cold_fronts = [f for f in result["nearest_fronts"] if f["type"] == "cold"]
        assert len(cold_fronts) > 0
        assert cold_fronts[0].get("position") == "warm side (ahead of front)"
        assert "location_summary" in result
        assert "warm side" in result["location_summary"]

    @patch("stormscope.tools._wpc")
    async def test_cold_sector_detection(self, mock_wpc):
        mock_wpc.get_surface_analysis = AsyncMock(
            return_value=(MOCK_WPC_FRONTS, MOCK_WPC_PRESSURE_CENTERS),
        )

        from stormscope.tools import get_surface_analysis
        # point north of the cold front should be on cold side
        result = await get_surface_analysis(48.0, -95.0)

        cold_fronts = [f for f in result["nearest_fronts"] if f["type"] == "cold"]
        assert len(cold_fronts) > 0
        assert cold_fronts[0].get("position") == "cold side (behind front)"

    @patch("stormscope.tools._wpc")
    async def test_empty_features(self, mock_wpc):
        empty = {"type": "FeatureCollection", "features": []}
        mock_wpc.get_surface_analysis = AsyncMock(return_value=(empty, empty))

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "error" not in result
        assert result["nearest_fronts"] == []
        assert result["nearest_pressure_centers"] == []
        assert "location_summary" not in result

    @patch("stormscope.tools._wpc")
    async def test_error_handling(self, mock_wpc):
        mock_wpc.get_surface_analysis = AsyncMock(side_effect=Exception("API down"))

        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert "error" in result

    async def test_invalid_day(self):
        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, day=0)
        assert "error" in result
        assert "invalid day" in result["error"]

    async def test_invalid_day_too_high(self):
        from stormscope.tools import get_surface_analysis
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, day=4)
        assert "error" in result

    @patch("stormscope.tools._wpc")
    async def test_unknown_front_type_skipped(self, mock_wpc):
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
        result = await get_surface_analysis(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

        assert len(result["nearest_fronts"]) == 1
        assert result["nearest_fronts"][0]["type"] == "cold"


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

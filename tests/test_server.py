"""Tests for server location resolution."""

from unittest.mock import AsyncMock, patch

import pytest

from stormscope.server import _resolve_location
from tests.conftest import TEMPEST_STATION_NEARBY


class TestResolveLocation:
    @pytest.mark.asyncio
    async def test_explicit_coordinates(self):
        lat, lon = await _resolve_location(44.9, -93.2)
        assert lat == 44.9
        assert lon == -93.2

    @pytest.mark.asyncio
    @patch("stormscope.server.config")
    async def test_fallback_to_config(self, mock_config):
        mock_config.primary_latitude = 44.9
        mock_config.primary_longitude = -93.2
        lat, lon = await _resolve_location(None, None)
        assert lat == 44.9
        assert lon == -93.2

    @pytest.mark.asyncio
    @patch("stormscope.server.config")
    async def test_partial_explicit_overrides_config(self, mock_config):
        mock_config.primary_latitude = 44.9
        mock_config.primary_longitude = -93.2
        lat, lon = await _resolve_location(40.0, None)
        assert lat == 40.0
        assert lon == -93.2

    @pytest.mark.asyncio
    @patch("stormscope.server.geolocate", new_callable=AsyncMock, return_value=None)
    @patch("stormscope.server.config")
    async def test_no_location_raises(self, mock_config, _mock_geo):
        mock_config.primary_latitude = None
        mock_config.primary_longitude = None
        mock_config.disable_auto_geolocation = False
        mock_config.enable_corelocation = False
        with pytest.raises(ValueError, match="PRIMARY_LATITUDE"):
            await _resolve_location(None, None)

    @pytest.mark.asyncio
    @patch("stormscope.server.geolocate", new_callable=AsyncMock, return_value=(40.7, -74.0))
    @patch("stormscope.server.config")
    async def test_fallback_to_geolocation(self, mock_config, mock_geo):
        mock_config.primary_latitude = None
        mock_config.primary_longitude = None
        mock_config.disable_auto_geolocation = False
        mock_config.enable_corelocation = False
        lat, lon = await _resolve_location(None, None)
        assert lat == 40.7
        assert lon == -74.0
        mock_geo.assert_awaited_once_with(
            disabled=False, enable_corelocation=False,
        )

    @pytest.mark.asyncio
    @patch("stormscope.server.geolocate", new_callable=AsyncMock)
    @patch("stormscope.server.config")
    async def test_config_skips_geolocation(self, mock_config, mock_geo):
        mock_config.primary_latitude = 44.9
        mock_config.primary_longitude = -93.2
        await _resolve_location(None, None)
        mock_geo.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("stormscope.server.geolocate", new_callable=AsyncMock, return_value=None)
    @patch("stormscope.server.config")
    async def test_disable_auto_geolocation(self, mock_config, mock_geo):
        mock_config.primary_latitude = None
        mock_config.primary_longitude = None
        mock_config.disable_auto_geolocation = True
        mock_config.enable_corelocation = False
        with pytest.raises(ValueError, match="PRIMARY_LATITUDE"):
            await _resolve_location(None, None)
        mock_geo.assert_awaited_once_with(
            disabled=True, enable_corelocation=False,
        )

    @pytest.mark.asyncio
    async def test_latitude_out_of_range(self):
        with pytest.raises(ValueError, match="latitude"):
            await _resolve_location(91.0, -93.0)

    @pytest.mark.asyncio
    async def test_latitude_negative_out_of_range(self):
        with pytest.raises(ValueError, match="latitude"):
            await _resolve_location(-91.0, -93.0)

    @pytest.mark.asyncio
    async def test_longitude_out_of_range(self):
        with pytest.raises(ValueError, match="longitude"):
            await _resolve_location(44.0, 181.0)

    @pytest.mark.asyncio
    async def test_longitude_negative_out_of_range(self):
        with pytest.raises(ValueError, match="longitude"):
            await _resolve_location(44.0, -181.0)

    @pytest.mark.asyncio
    async def test_boundary_values_accepted(self):
        lat, lon = await _resolve_location(90.0, 180.0)
        assert lat == 90.0
        assert lon == 180.0
        lat, lon = await _resolve_location(-90.0, -180.0)
        assert lat == -90.0
        assert lon == -180.0

    @pytest.mark.asyncio
    @patch("stormscope.server.tools.get_tempest_station_location", new_callable=AsyncMock)
    @patch("stormscope.server.config")
    async def test_tempest_station_location_override(self, mock_config, mock_get_loc):
        """TEMPEST_USE_STATION_LOCATION uses the station's coords as primary location."""
        mock_config.tempest_enabled = True
        mock_config.tempest_use_station_location = True
        mock_config.primary_latitude = None
        mock_config.primary_longitude = None
        station_lat = TEMPEST_STATION_NEARBY["latitude"]
        station_lon = TEMPEST_STATION_NEARBY["longitude"]
        mock_get_loc.return_value = (station_lat, station_lon)

        import stormscope.server as server_mod
        orig_fetched = server_mod._tempest_station_location_fetched
        orig_loc = server_mod._tempest_station_location
        server_mod._tempest_station_location_fetched = False
        server_mod._tempest_station_location = None
        try:
            lat, lon = await _resolve_location(None, None)
        finally:
            server_mod._tempest_station_location_fetched = orig_fetched
            server_mod._tempest_station_location = orig_loc

        assert lat == station_lat
        assert lon == station_lon

    @pytest.mark.asyncio
    @patch("stormscope.server.tools.get_tempest_station_location", new_callable=AsyncMock)
    @patch("stormscope.server.config")
    async def test_tempest_station_location_fallback_on_none(self, mock_config, mock_get_loc):
        """when station location returns None, fall through to primary location."""
        mock_config.tempest_enabled = True
        mock_config.tempest_use_station_location = True
        mock_config.primary_latitude = 44.9
        mock_config.primary_longitude = -93.2
        mock_get_loc.return_value = None

        import stormscope.server as server_mod
        orig_fetched = server_mod._tempest_station_location_fetched
        orig_loc = server_mod._tempest_station_location
        server_mod._tempest_station_location_fetched = False
        server_mod._tempest_station_location = None
        try:
            lat, lon = await _resolve_location(None, None)
        finally:
            server_mod._tempest_station_location_fetched = orig_fetched
            server_mod._tempest_station_location = orig_loc

        assert lat == 44.9
        assert lon == -93.2


class TestServerValidation:
    @pytest.mark.asyncio
    @patch("stormscope.server.config")
    async def test_invalid_detail_conditions(self, mock_config):
        mock_config.primary_latitude = 44.9
        mock_config.primary_longitude = -93.2
        from stormscope.server import get_conditions
        result = await get_conditions(detail="verbose")
        assert "error" in result
        assert "invalid detail" in result["error"]

    @pytest.mark.asyncio
    @patch("stormscope.server.config")
    async def test_invalid_detail_alerts(self, mock_config):
        mock_config.primary_latitude = 44.9
        mock_config.primary_longitude = -93.2
        from stormscope.server import get_alerts
        result = await get_alerts(detail="verbose")
        assert "error" in result
        assert "invalid detail" in result["error"]

    @pytest.mark.asyncio
    @patch("stormscope.server.config")
    async def test_invalid_detail_briefing(self, mock_config):
        mock_config.primary_latitude = 44.9
        mock_config.primary_longitude = -93.2
        from stormscope.server import get_briefing
        result = await get_briefing(detail="verbose")
        assert "error" in result
        assert "invalid detail" in result["error"]

    @pytest.mark.asyncio
    @patch("stormscope.server.config")
    async def test_invalid_detail_surface_analysis(self, mock_config):
        mock_config.primary_latitude = 44.9
        mock_config.primary_longitude = -93.2
        from stormscope.server import get_surface_analysis
        result = await get_surface_analysis(detail="verbose")
        assert "error" in result
        assert "invalid detail" in result["error"]

    @pytest.mark.asyncio
    @patch("stormscope.server.config")
    async def test_invalid_days_forecast(self, mock_config):
        mock_config.primary_latitude = 44.9
        mock_config.primary_longitude = -93.2
        from stormscope.server import get_forecast
        result = await get_forecast(days=0)
        assert "error" in result
        assert "invalid days" in result["error"]

    @pytest.mark.asyncio
    @patch("stormscope.server.config")
    async def test_invalid_days_too_high(self, mock_config):
        mock_config.primary_latitude = 44.9
        mock_config.primary_longitude = -93.2
        from stormscope.server import get_forecast
        result = await get_forecast(days=8)
        assert "error" in result
        assert "invalid days" in result["error"]

    @pytest.mark.asyncio
    @patch("stormscope.server.config")
    async def test_invalid_hours_forecast(self, mock_config):
        mock_config.primary_latitude = 44.9
        mock_config.primary_longitude = -93.2
        from stormscope.server import get_forecast
        result = await get_forecast(hours=0)
        assert "error" in result
        assert "invalid hours" in result["error"]

    @pytest.mark.asyncio
    @patch("stormscope.server.config")
    async def test_invalid_hours_too_high(self, mock_config):
        mock_config.primary_latitude = 44.9
        mock_config.primary_longitude = -93.2
        from stormscope.server import get_forecast
        result = await get_forecast(hours=49)
        assert "error" in result
        assert "invalid hours" in result["error"]


class TestUnitsValidation:
    @pytest.mark.asyncio
    @patch("stormscope.server.config")
    async def test_invalid_units_system(self, mock_config):
        mock_config.primary_latitude = 44.9
        mock_config.primary_longitude = -93.2
        mock_config.units = "us"
        from stormscope.server import get_conditions
        result = await get_conditions(units="metric")
        assert "error" in result
        assert "invalid unit system" in result["error"]

    @pytest.mark.asyncio
    @patch("stormscope.server.config")
    async def test_invalid_units_field(self, mock_config):
        mock_config.primary_latitude = 44.9
        mock_config.primary_longitude = -93.2
        mock_config.units = "us"
        from stormscope.server import get_forecast
        result = await get_forecast(units="us,humidity:pct")
        assert "error" in result
        assert "unknown unit field" in result["error"]

    @pytest.mark.asyncio
    @patch("stormscope.server.config")
    async def test_invalid_units_value(self, mock_config):
        mock_config.primary_latitude = 44.9
        mock_config.primary_longitude = -93.2
        mock_config.units = "us"
        from stormscope.server import get_briefing
        result = await get_briefing(units="us,wind:lightyears")
        assert "error" in result
        assert "invalid value" in result["error"]

    @pytest.mark.asyncio
    @patch("stormscope.server.config")
    async def test_valid_units_pass_through(self, mock_config):
        mock_config.primary_latitude = 44.9
        mock_config.primary_longitude = -93.2
        mock_config.units = "us"
        from stormscope.server import _validate_units
        assert _validate_units("us,pressure:mb") is None
        assert _validate_units("si") is None
        assert _validate_units(None) is None

    @pytest.mark.asyncio
    async def test_invalid_units_alerts(self):
        from stormscope.server import get_alerts
        result = await get_alerts(units="metric")
        assert "error" in result
        assert "invalid unit system" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_units_spc_outlook(self):
        from stormscope.server import get_spc_outlook
        result = await get_spc_outlook(units="metric")
        assert "error" in result
        assert "invalid unit system" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_units_national_outlook(self):
        from stormscope.server import get_national_outlook
        result = await get_national_outlook(units="metric")
        assert "error" in result
        assert "invalid unit system" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_units_radar(self):
        from stormscope.server import get_radar
        result = await get_radar(units="metric")
        assert "error" in result
        assert "invalid unit system" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_units_upper_air(self):
        from stormscope.server import get_upper_air
        result = await get_upper_air(units="metric")
        assert "error" in result
        assert "invalid unit system" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_units_surface_analysis(self):
        from stormscope.server import get_surface_analysis
        result = await get_surface_analysis(units="metric")
        assert "error" in result
        assert "invalid unit system" in result["error"]


class TestServerDelegation:
    """Verify each server tool delegates to the tools module with valid inputs."""

    @pytest.mark.asyncio
    @patch("stormscope.tools.get_conditions", new_callable=AsyncMock)
    async def test_conditions_delegates(self, mock_fn):
        mock_fn.return_value = {"temperature": "72°F"}
        from stormscope.server import get_conditions
        result = await get_conditions(latitude=44.9, longitude=-93.2)
        assert result == {"temperature": "72°F"}

    @pytest.mark.asyncio
    @patch("stormscope.tools.get_forecast", new_callable=AsyncMock)
    async def test_forecast_delegates(self, mock_fn):
        mock_fn.return_value = {"periods": []}
        from stormscope.server import get_forecast
        result = await get_forecast(latitude=44.9, longitude=-93.2)
        assert result == {"periods": []}

    @pytest.mark.asyncio
    @patch("stormscope.tools.get_alerts", new_callable=AsyncMock)
    async def test_alerts_delegates(self, mock_fn):
        mock_fn.return_value = {"count": 0, "alerts": []}
        from stormscope.server import get_alerts
        result = await get_alerts(latitude=44.9, longitude=-93.2)
        assert result == {"count": 0, "alerts": []}

    @pytest.mark.asyncio
    @patch("stormscope.tools.get_spc_outlook", new_callable=AsyncMock)
    async def test_spc_outlook_delegates(self, mock_fn):
        mock_fn.return_value = {"risk_level": "NONE"}
        from stormscope.server import get_spc_outlook
        result = await get_spc_outlook(latitude=44.9, longitude=-93.2)
        assert result == {"risk_level": "NONE"}

    @pytest.mark.asyncio
    @patch("stormscope.tools.get_national_outlook", new_callable=AsyncMock)
    async def test_national_outlook_delegates(self, mock_fn):
        mock_fn.return_value = {"areas": []}
        from stormscope.server import get_national_outlook
        result = await get_national_outlook()
        assert result == {"areas": []}

    @pytest.mark.asyncio
    @patch("stormscope.tools.get_radar", new_callable=AsyncMock)
    async def test_radar_delegates(self, mock_fn):
        mock_fn.return_value = {"station_id": "KMPX"}
        from stormscope.server import get_radar
        result = await get_radar(latitude=44.9, longitude=-93.2)
        assert result == {"station_id": "KMPX"}

    @pytest.mark.asyncio
    @patch("stormscope.tools.get_briefing", new_callable=AsyncMock)
    async def test_briefing_delegates(self, mock_fn):
        mock_fn.return_value = {"location": "Minneapolis, MN"}
        from stormscope.server import get_briefing
        result = await get_briefing(latitude=44.9, longitude=-93.2)
        assert result == {"location": "Minneapolis, MN"}

    @pytest.mark.asyncio
    @patch("stormscope.tools.get_upper_air", new_callable=AsyncMock)
    async def test_upper_air_delegates(self, mock_fn):
        mock_fn.return_value = {"height_dam": "560"}
        from stormscope.server import get_upper_air
        result = await get_upper_air(latitude=44.9, longitude=-93.2)
        assert result == {"height_dam": "560"}

    @pytest.mark.asyncio
    @patch("stormscope.tools.get_surface_analysis", new_callable=AsyncMock)
    async def test_surface_analysis_delegates(self, mock_fn):
        mock_fn.return_value = {"fronts": []}
        from stormscope.server import get_surface_analysis
        result = await get_surface_analysis(latitude=44.9, longitude=-93.2)
        assert result == {"fronts": []}


class TestServerLocationErrors:
    """Verify server tools return an error dict for out-of-range coordinates."""

    @pytest.mark.asyncio
    async def test_conditions_invalid_coords(self):
        from stormscope.server import get_conditions
        result = await get_conditions(latitude=95.0, longitude=-93.2)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_forecast_invalid_coords(self):
        from stormscope.server import get_forecast
        result = await get_forecast(latitude=95.0, longitude=-93.2)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_alerts_invalid_coords(self):
        from stormscope.server import get_alerts
        result = await get_alerts(latitude=95.0, longitude=-93.2)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_spc_outlook_invalid_coords(self):
        from stormscope.server import get_spc_outlook
        result = await get_spc_outlook(latitude=95.0, longitude=-93.2)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_radar_invalid_coords(self):
        from stormscope.server import get_radar
        result = await get_radar(latitude=95.0, longitude=-93.2)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_briefing_invalid_coords(self):
        from stormscope.server import get_briefing
        result = await get_briefing(latitude=95.0, longitude=-93.2)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_upper_air_invalid_coords(self):
        from stormscope.server import get_upper_air
        result = await get_upper_air(latitude=95.0, longitude=-93.2)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_surface_analysis_invalid_coords(self):
        from stormscope.server import get_surface_analysis
        result = await get_surface_analysis(latitude=95.0, longitude=-93.2)
        assert "error" in result


class TestMCPRegistration:
    @pytest.mark.asyncio
    async def test_all_tools_registered(self):
        from stormscope.server import mcp
        tools = await mcp.list_tools()
        names = [t.name for t in tools]
        assert len(tools) == 9, f"expected 9 tools, got {len(tools)}: {names}"

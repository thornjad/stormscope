"""Tests for server location resolution."""

from unittest.mock import AsyncMock, patch

import pytest

from stormscope.server import _resolve_location


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


class TestMCPRegistration:
    @pytest.mark.asyncio
    async def test_all_tools_registered(self):
        from stormscope.server import mcp
        tools = await mcp.list_tools()
        names = [t.name for t in tools]
        assert len(tools) == 8, f"expected 8 tools, got {len(tools)}: {names}"

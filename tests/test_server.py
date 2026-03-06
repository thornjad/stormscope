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
    @patch("stormscope.server.geolocate_ip", new_callable=AsyncMock, return_value=None)
    @patch("stormscope.server.config")
    async def test_no_location_raises(self, mock_config, _mock_geo):
        mock_config.primary_latitude = None
        mock_config.primary_longitude = None
        with pytest.raises(ValueError, match="PRIMARY_LATITUDE"):
            await _resolve_location(None, None)

    @pytest.mark.asyncio
    @patch("stormscope.server.geolocate_ip", new_callable=AsyncMock, return_value=(40.7, -74.0))
    @patch("stormscope.server.config")
    async def test_fallback_to_ip_geolocation(self, mock_config, mock_geo):
        mock_config.primary_latitude = None
        mock_config.primary_longitude = None
        lat, lon = await _resolve_location(None, None)
        assert lat == 40.7
        assert lon == -74.0
        mock_geo.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("stormscope.server.geolocate_ip", new_callable=AsyncMock)
    @patch("stormscope.server.config")
    async def test_config_skips_ip_geolocation(self, mock_config, mock_geo):
        mock_config.primary_latitude = 44.9
        mock_config.primary_longitude = -93.2
        await _resolve_location(None, None)
        mock_geo.assert_not_awaited()

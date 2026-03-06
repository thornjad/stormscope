"""Tests for geographic utilities."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from shapely.geometry import Polygon

import stormscope.geo as geo_module
from stormscope.geo import geolocate, geolocate_corelocation, geolocate_ip, polygon_to_region


def test_oklahoma_polygon():
    poly = Polygon([(-97.8, 35.2), (-97.2, 35.2), (-97.2, 35.8), (-97.8, 35.8)])
    region = polygon_to_region(poly)
    assert "Oklahoma" in region


def test_minnesota_polygon():
    poly = Polygon([(-93.5, 44.8), (-93.0, 44.8), (-93.0, 45.2), (-93.5, 45.2)])
    region = polygon_to_region(poly)
    assert "Minnesota" in region


def test_fallback_for_ocean():
    poly = Polygon([(-60.0, 30.0), (-59.0, 30.0), (-59.0, 31.0), (-60.0, 31.0)])
    region = polygon_to_region(poly)
    assert "near" in region


@pytest.fixture(autouse=True)
def _reset_geo_cache():
    """reset geolocation caches between tests."""
    geo_module._ip_location = None
    geo_module._ip_location_fetched = False
    geo_module._cl_location = None
    geo_module._cl_location_fetched = False


class TestGeolocateIp:
    @pytest.mark.asyncio
    async def test_successful_geolocation(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"loc": "44.9778,-93.2650"}
        mock_resp.raise_for_status = MagicMock()

        with patch("stormscope.geo.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await geolocate_ip()

        assert result == (44.9778, -93.265)

    @pytest.mark.asyncio
    async def test_network_failure_returns_none(self):
        with patch("stormscope.geo.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("no network")
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await geolocate_ip()

        assert result is None

    @pytest.mark.asyncio
    async def test_malformed_response_returns_none(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ip": "1.2.3.4"}
        mock_resp.raise_for_status = MagicMock()

        with patch("stormscope.geo.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await geolocate_ip()

        assert result is None

    @pytest.mark.asyncio
    async def test_caching_skips_second_request(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"loc": "40.7128,-74.0060"}
        mock_resp.raise_for_status = MagicMock()

        with patch("stormscope.geo.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            first = await geolocate_ip()

        # second call should use cache, not create a new client
        with patch("stormscope.geo.httpx.AsyncClient") as mock_client_cls2:
            second = await geolocate_ip()
            mock_client_cls2.assert_not_called()

        assert first == second == (40.7128, -74.006)


class TestGeolocateCorelocation:
    @pytest.mark.asyncio
    async def test_successful_parse(self):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"44.9778,-93.2650\n", b"")

        with patch("stormscope.geo.asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await geolocate_corelocation()

        assert result == (44.9778, -93.265)

    @pytest.mark.asyncio
    async def test_command_not_found_returns_none(self):
        with patch(
            "stormscope.geo.asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("CoreLocationCLI not found"),
        ):
            result = await geolocate_corelocation()

        assert result is None

    @pytest.mark.asyncio
    async def test_timeout_returns_none(self):
        mock_proc = AsyncMock()
        mock_proc.communicate.side_effect = asyncio.TimeoutError()

        with patch("stormscope.geo.asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await geolocate_corelocation()

        assert result is None

    @pytest.mark.asyncio
    async def test_caching_skips_second_call(self):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"40.7128,-74.0060\n", b"")

        with patch("stormscope.geo.asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            first = await geolocate_corelocation()

        with patch("stormscope.geo.asyncio.create_subprocess_exec") as mock_exec2:
            second = await geolocate_corelocation()
            mock_exec2.assert_not_called()

        assert first == second == (40.7128, -74.006)


class TestGeolocate:
    @pytest.mark.asyncio
    @patch("stormscope.geo.geolocate_ip", new_callable=AsyncMock)
    @patch("stormscope.geo.geolocate_corelocation", new_callable=AsyncMock, return_value=(44.9, -93.2))
    async def test_corelocation_succeeds_skips_ip(self, mock_cl, mock_ip):
        result = await geolocate()
        assert result == (44.9, -93.2)
        mock_ip.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("stormscope.geo.geolocate_ip", new_callable=AsyncMock, return_value=(40.7, -74.0))
    @patch("stormscope.geo.geolocate_corelocation", new_callable=AsyncMock, return_value=None)
    async def test_corelocation_fails_falls_through_to_ip(self, mock_cl, mock_ip):
        result = await geolocate()
        assert result == (40.7, -74.0)

    @pytest.mark.asyncio
    @patch("stormscope.geo.geolocate_ip", new_callable=AsyncMock, return_value=None)
    @patch("stormscope.geo.geolocate_corelocation", new_callable=AsyncMock, return_value=None)
    async def test_both_fail_returns_none(self, mock_cl, mock_ip):
        result = await geolocate()
        assert result is None

    @pytest.mark.asyncio
    @patch("stormscope.geo.geolocate_ip", new_callable=AsyncMock)
    @patch("stormscope.geo.geolocate_corelocation", new_callable=AsyncMock)
    async def test_disabled_returns_none(self, mock_cl, mock_ip):
        result = await geolocate(disabled=True)
        assert result is None
        mock_cl.assert_not_awaited()
        mock_ip.assert_not_awaited()

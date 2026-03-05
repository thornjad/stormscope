"""Tests for IEM radar client."""

from unittest.mock import AsyncMock, patch

from stormscope.iem import IEMClient


async def test_get_radar_info():
    client = IEMClient()

    mock_products = [{"id": "N0B"}, {"id": "N0S"}]
    mock_scans = {"scans": [{"ts": "2026-03-04T12:00:00Z"}]}

    with patch.object(client, "_request") as mock_req:
        mock_req.side_effect = [
            {"products": mock_products},
            mock_scans,
        ]

        result = await client.get_radar_info("KMSP")

    assert result["station_id"] == "KMSP"
    assert result["available_products"] == ["N0B", "N0S"]
    assert result["latest_scan_time"] == "2026-03-04T12:00:00Z"
    assert "imagery_urls" in result
    assert "MSP" in result["imagery_urls"]["site_url"]


async def test_iem_site_strips_k():
    client = IEMClient()
    assert client._iem_site("KMSP") == "MSP"
    assert client._iem_site("MSP") == "MSP"
    assert client._iem_site("KABR") == "ABR"


async def test_fallback_on_failure():
    client = IEMClient()

    with patch.object(client, "_request", side_effect=Exception("connection error")):
        result = await client.get_radar_info("KMSP")

    assert result["station_id"] == "KMSP"
    assert result["_stale"] is True
    assert result["available_products"] == []


async def test_stale_fallback_returns_cached():
    client = IEMClient()

    cached_result = {
        "station_id": "KMSP",
        "available_products": ["N0B"],
        "latest_scan_time": "old",
        "imagery_urls": {},
    }
    await client._cache.set("radar:KMSP", cached_result, 0.01)

    import asyncio
    await asyncio.sleep(0.02)

    with patch.object(client, "_request", side_effect=Exception("down")):
        result = await client.get_radar_info("KMSP")

    assert result["station_id"] == "KMSP"
    assert result["_stale"] is True
    assert result["available_products"] == ["N0B"]

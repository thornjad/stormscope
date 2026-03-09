"""Tests for IEM radar client."""

import asyncio

import httpx
import respx

from stormscope.iem import IEM_BASE, IEMClient


async def test_iem_site_strips_k():
    client = IEMClient()
    assert client._iem_site("KMSP") == "MSP"
    assert client._iem_site("MSP") == "MSP"
    assert client._iem_site("KABR") == "ABR"


@respx.mock
async def test_get_radar_info():
    client = IEMClient()

    respx.get(f"{IEM_BASE}/json/radar.py").mock(
        side_effect=[
            httpx.Response(200, json={"products": [{"id": "N0B"}, {"id": "N0S"}]}),
            httpx.Response(200, json={"scans": [{"ts": "2026-03-04T12:00:00Z"}]}),
        ],
    )

    result = await client.get_radar_info("KMSP")

    assert result["station_id"] == "KMSP"
    assert result["available_products"] == ["N0B", "N0S"]
    assert result["latest_scan_time"] == "2026-03-04T12:00:00Z"
    assert "imagery_urls" in result
    assert "MSP" in result["imagery_urls"]["site_url"]


@respx.mock
async def test_fallback_on_failure():
    client = IEMClient()

    respx.get(f"{IEM_BASE}/json/radar.py").mock(
        return_value=httpx.Response(500),
    )

    result = await client.get_radar_info("KMSP")

    assert result["station_id"] == "KMSP"
    assert result["_stale"] is True
    assert result["available_products"] == []


@respx.mock
async def test_stale_fallback_returns_cached():
    client = IEMClient()

    cached_result = {
        "station_id": "KMSP",
        "available_products": ["N0B"],
        "latest_scan_time": "old",
        "imagery_urls": {},
    }
    await client._cache.set("radar:KMSP", cached_result, 0.01)
    await asyncio.sleep(0.02)

    respx.get(f"{IEM_BASE}/json/radar.py").mock(
        return_value=httpx.Response(500),
    )

    result = await client.get_radar_info("KMSP")

    assert result["station_id"] == "KMSP"
    assert result["_stale"] is True
    assert result["available_products"] == ["N0B"]


@respx.mock
async def test_fetch_products_flat_list():
    """IEM sometimes returns product list as flat strings instead of dicts."""
    client = IEMClient()

    respx.get(f"{IEM_BASE}/json/radar.py").mock(
        return_value=httpx.Response(200, json={"products": ["N0B", "N0S"]}),
    )

    result = await client._fetch_products("MSP", "2026-03-04T11:00:00Z")
    assert result == ["N0B", "N0S"]

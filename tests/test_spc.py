"""Tests for SPC outlook client."""

import httpx
import pytest
import respx

from stormscope.spc import SPCClient, SPC_OUTLOOK_URL
from tests.conftest import MOCK_SPC_OUTLOOK, MINNEAPOLIS_LAT, MINNEAPOLIS_LON


@pytest.fixture
def spc_client():
    return SPCClient()


@respx.mock
async def test_point_in_tstm_only(spc_client):
    """Point inside TSTM polygon but outside MRGL returns TSTM."""
    url = SPC_OUTLOOK_URL.format(day=1)
    respx.get(url).mock(return_value=httpx.Response(200, json=MOCK_SPC_OUTLOOK))

    # lat=43.5, lon=-93.0 is inside TSTM (43-47, -95 to -91) but outside MRGL (44-46, -94 to -92)
    result = await spc_client.check_risk_for_point(43.5, -93.0)

    assert result["risk_level"] == "TSTM"
    assert result["is_significant"] is False
    assert result["day"] == 1
    assert result["valid_time"] == "202603041200"
    assert result["expire_time"] == "202603051200"


@respx.mock
async def test_point_in_tstm_and_mrgl_returns_higher(spc_client):
    """Point inside both TSTM and MRGL returns MRGL (higher DN)."""
    url = SPC_OUTLOOK_URL.format(day=1)
    respx.get(url).mock(return_value=httpx.Response(200, json=MOCK_SPC_OUTLOOK))

    # Minneapolis is inside both polygons
    result = await spc_client.check_risk_for_point(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

    assert result["risk_level"] == "MRGL"
    assert result["risk_description"] == "Marginal Risk - isolated severe storms possible"
    assert result["is_significant"] is False
    assert result["day"] == 1


@respx.mock
async def test_point_outside_all_polygons(spc_client):
    """Point outside all polygons returns NONE."""
    url = SPC_OUTLOOK_URL.format(day=1)
    respx.get(url).mock(return_value=httpx.Response(200, json=MOCK_SPC_OUTLOOK))

    # lat=40.0, lon=-80.0 is far outside both polygons
    result = await spc_client.check_risk_for_point(40.0, -80.0)

    assert result["risk_level"] == "NONE"
    assert result["risk_description"] == "No severe weather risk"
    assert result["is_significant"] is False
    assert result["valid_time"] is None
    assert result["expire_time"] is None


@respx.mock
async def test_minneapolis_in_mrgl(spc_client):
    """Minneapolis (44.9778, -93.2650) is within the MRGL polygon."""
    url = SPC_OUTLOOK_URL.format(day=1)
    respx.get(url).mock(return_value=httpx.Response(200, json=MOCK_SPC_OUTLOOK))

    result = await spc_client.check_risk_for_point(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

    assert result["risk_level"] == "MRGL"
    assert result["day"] == 1


@respx.mock
async def test_outlook_cached(spc_client):
    """Second call uses cache, no additional HTTP request."""
    url = SPC_OUTLOOK_URL.format(day=1)
    route = respx.get(url).mock(return_value=httpx.Response(200, json=MOCK_SPC_OUTLOOK))

    await spc_client.check_risk_for_point(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)
    await spc_client.check_risk_for_point(43.5, -93.0)

    assert route.call_count == 1


@respx.mock
async def test_fetch_failure_returns_error(spc_client):
    """HTTP failure returns error dict."""
    url = SPC_OUTLOOK_URL.format(day=1)
    respx.get(url).mock(return_value=httpx.Response(500))

    result = await spc_client.check_risk_for_point(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

    assert "error" in result

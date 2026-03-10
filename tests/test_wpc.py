"""Tests for WPC surface analysis client."""

import asyncio

import httpx
import pytest
import respx

from stormscope.wpc import WPCClient, WPC_BASE, _DAY_LAYERS
from tests.conftest import MOCK_WPC_FRONTS, MOCK_WPC_PRESSURE_CENTERS


@pytest.fixture
def wpc_client():
    return WPCClient()


@respx.mock
async def test_fetch_fronts(wpc_client):
    _, layer = _DAY_LAYERS[1]
    url = f"{WPC_BASE}/{layer}/query"
    respx.get(url).mock(return_value=httpx.Response(200, json=MOCK_WPC_FRONTS))

    result = await wpc_client.get_fronts(1)

    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 2
    assert result["features"][0]["properties"]["feat"] == "Cold Front Valid"


@respx.mock
async def test_fetch_pressure_centers(wpc_client):
    layer, _ = _DAY_LAYERS[1]
    url = f"{WPC_BASE}/{layer}/query"
    respx.get(url).mock(return_value=httpx.Response(200, json=MOCK_WPC_PRESSURE_CENTERS))

    result = await wpc_client.get_pressure_centers(1)

    assert len(result["features"]) == 2
    assert result["features"][0]["properties"]["feat"] == "Low Valid"


@respx.mock
async def test_surface_analysis_fetches_both(wpc_client):
    centers_layer, fronts_layer = _DAY_LAYERS[1]
    respx.get(f"{WPC_BASE}/{fronts_layer}/query").mock(
        return_value=httpx.Response(200, json=MOCK_WPC_FRONTS),
    )
    respx.get(f"{WPC_BASE}/{centers_layer}/query").mock(
        return_value=httpx.Response(200, json=MOCK_WPC_PRESSURE_CENTERS),
    )

    fronts, centers = await wpc_client.get_surface_analysis(1)

    assert len(fronts["features"]) == 2
    assert len(centers["features"]) == 2


@respx.mock
async def test_caching(wpc_client):
    _, layer = _DAY_LAYERS[1]
    url = f"{WPC_BASE}/{layer}/query"
    route = respx.get(url).mock(return_value=httpx.Response(200, json=MOCK_WPC_FRONTS))

    await wpc_client.get_fronts(1)
    await wpc_client.get_fronts(1)

    assert route.call_count == 1


@respx.mock
async def test_http_failure(wpc_client):
    _, layer = _DAY_LAYERS[1]
    url = f"{WPC_BASE}/{layer}/query"
    respx.get(url).mock(return_value=httpx.Response(500))

    with pytest.raises(httpx.HTTPStatusError):
        await wpc_client.get_fronts(1)


@respx.mock
async def test_stale_fallback(wpc_client):
    await wpc_client._cache.set("wpc_fronts_day1", MOCK_WPC_FRONTS, 0.01)
    await asyncio.sleep(0.02)

    _, layer = _DAY_LAYERS[1]
    url = f"{WPC_BASE}/{layer}/query"
    respx.get(url).mock(return_value=httpx.Response(500))

    result = await wpc_client.get_fronts(1)

    assert result == MOCK_WPC_FRONTS


@respx.mock
async def test_day2_layer_mapping(wpc_client):
    _, layer = _DAY_LAYERS[2]
    assert layer == 14
    url = f"{WPC_BASE}/{layer}/query"
    respx.get(url).mock(return_value=httpx.Response(200, json=MOCK_WPC_FRONTS))

    result = await wpc_client.get_fronts(2)
    assert len(result["features"]) == 2


@respx.mock
async def test_day3_layer_mapping(wpc_client):
    _, layer = _DAY_LAYERS[3]
    assert layer == 26
    url = f"{WPC_BASE}/{layer}/query"
    respx.get(url).mock(return_value=httpx.Response(200, json=MOCK_WPC_FRONTS))

    result = await wpc_client.get_fronts(3)
    assert len(result["features"]) == 2


async def test_invalid_day(wpc_client):
    result = await wpc_client.get_fronts(4)
    assert result["features"] == []


@respx.mock
async def test_empty_features(wpc_client):
    empty = {"type": "FeatureCollection", "features": []}
    _, layer = _DAY_LAYERS[1]
    url = f"{WPC_BASE}/{layer}/query"
    respx.get(url).mock(return_value=httpx.Response(200, json=empty))

    result = await wpc_client.get_fronts(1)
    assert result["features"] == []


@respx.mock
async def test_empty_response_body(wpc_client):
    _, layer = _DAY_LAYERS[1]
    url = f"{WPC_BASE}/{layer}/query"
    respx.get(url).mock(return_value=httpx.Response(200, content=b""))

    result = await wpc_client.get_fronts(1)
    assert result["features"] == []


@respx.mock
async def test_null_json_response(wpc_client):
    _, layer = _DAY_LAYERS[1]
    url = f"{WPC_BASE}/{layer}/query"
    respx.get(url).mock(return_value=httpx.Response(200, content=b"null"))

    result = await wpc_client.get_fronts(1)
    assert result == {"type": "FeatureCollection", "features": []}


@respx.mock
async def test_non_dict_json_response(wpc_client):
    _, layer = _DAY_LAYERS[1]
    url = f"{WPC_BASE}/{layer}/query"
    respx.get(url).mock(return_value=httpx.Response(200, json=["unexpected", "array"]))

    result = await wpc_client.get_fronts(1)
    assert result == {"type": "FeatureCollection", "features": []}

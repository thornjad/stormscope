"""Tests for SPC outlook client."""

import asyncio

import httpx
import pytest
import respx

from stormscope.spc import SPCClient, SPC_OUTLOOK_URL, SPC_PROB_URL, _parse_probability
from tests.conftest import (
    MOCK_PROB_OUTLOOK,
    MOCK_SPC_OUTLOOK,
    MINNEAPOLIS_LAT,
    MINNEAPOLIS_LON,
)


@pytest.fixture
def spc_client():
    return SPCClient()


@pytest.mark.parametrize(
    "label,expected",
    [
        ("0.02", 2),
        ("0.05", 5),
        ("0.10", 10),
        ("0.60", 60),
        ("5", 5),
        ("30", 30),
        ("1", 1),  # legacy integer 1% — not scaled to 100%
        ("1.0", 100),  # decimal 1.0 — scaled like any fraction
        ("CIG1", None),
        ("SIGN", None),
        ("", None),
        ("-0.1", None),
        ("inf", None),
        ("nan", None),
    ],
)
def test_parse_probability(label, expected):
    assert _parse_probability(label) == expected


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
    """HTTP failure returns error dict with debug info."""
    url = SPC_OUTLOOK_URL.format(day=1)
    respx.get(url).mock(return_value=httpx.Response(500))

    result = await spc_client.check_risk_for_point(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

    assert "error" in result
    assert "debug" in result
    assert "url" in result["debug"]


@respx.mock
async def test_point_in_probabilistic_via_client(spc_client):
    """Probabilistic outlook returns hazard probability and significant flag."""
    url = SPC_PROB_URL.format(day=1, hazard="torn")
    respx.get(url).mock(return_value=httpx.Response(200, json=MOCK_PROB_OUTLOOK))

    result = await spc_client.get_spc_outlook(
        MINNEAPOLIS_LAT, MINNEAPOLIS_LON, 1, "tornado",
    )

    assert result["hazard"] == "tornado"
    assert result["probability"] == 5
    assert result["significant"] is True
    assert result["intensity_group"] == "CIG1"
    # regression: valid/expire must be populated, not null (GH zero-prob bug)
    assert result["valid_time"] == "202603041200"
    assert result["expire_time"] == "202603051200"
    assert result["day"] == 1


@respx.mock
async def test_probabilistic_real_spc_fraction_format(spc_client):
    """SPC serves probabilities as decimal fractions ("0.05"), not "5".

    Regression for the live bug: int("0.05") raised ValueError, every
    feature was skipped, and probability/valid_time came back 0/null.
    """
    outlook = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "LABEL": "0.02",
                    "VALID": "202606101300",
                    "EXPIRE": "202606111200",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-95, 43], [-91, 43], [-91, 47], [-95, 47], [-95, 43]]],
                },
            },
            {
                "type": "Feature",
                "properties": {
                    "LABEL": "0.10",
                    "VALID": "202606101300",
                    "EXPIRE": "202606111200",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-94, 44], [-92, 44], [-92, 46], [-94, 46], [-94, 44]]],
                },
            },
        ],
    }
    url = SPC_PROB_URL.format(day=1, hazard="torn")
    respx.get(url).mock(return_value=httpx.Response(200, json=outlook))

    result = await spc_client.get_spc_outlook(
        MINNEAPOLIS_LAT, MINNEAPOLIS_LON, 1, "tornado",
    )

    # Minneapolis sits inside both polygons; highest band wins.
    assert result["probability"] == 10
    assert result["significant"] is False
    assert result["intensity_group"] is None
    assert result["valid_time"] == "202606101300"
    assert result["expire_time"] == "202606111200"


@respx.mock
async def test_probabilistic_legacy_integer_format(spc_client):
    """Integer-percent labels ("5") still parse, for backward compatibility."""
    outlook = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"LABEL": "15", "VALID": "202606101300", "EXPIRE": "202606111200"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-94, 44], [-92, 44], [-92, 46], [-94, 46], [-94, 44]]],
                },
            },
        ],
    }
    url = SPC_PROB_URL.format(day=1, hazard="wind")
    respx.get(url).mock(return_value=httpx.Response(200, json=outlook))

    result = await spc_client.get_spc_outlook(
        MINNEAPOLIS_LAT, MINNEAPOLIS_LON, 1, "wind",
    )

    assert result["probability"] == 15


@respx.mock
async def test_probabilistic_highest_cig_group_wins(spc_client):
    """Overlapping CIG groups report the highest intensity group at the point."""
    poly = [[[-94, 44], [-92, 44], [-92, 46], [-94, 46], [-94, 44]]]
    outlook = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"LABEL": "CIG1", "VALID": "202606101300", "EXPIRE": "202606111200"},
                "geometry": {"type": "Polygon", "coordinates": poly},
            },
            {
                "type": "Feature",
                "properties": {"LABEL": "CIG3", "VALID": "202606101300", "EXPIRE": "202606111200"},
                "geometry": {"type": "Polygon", "coordinates": poly},
            },
        ],
    }
    url = SPC_PROB_URL.format(day=1, hazard="torn")
    respx.get(url).mock(return_value=httpx.Response(200, json=outlook))

    result = await spc_client.get_spc_outlook(
        MINNEAPOLIS_LAT, MINNEAPOLIS_LON, 1, "tornado",
    )

    assert result["significant"] is True
    assert result["intensity_group"] == "CIG3"


@respx.mock
async def test_probabilistic_legacy_sign_label(spc_client):
    """The pre-2026 "SIGN" hatched label still sets significant (no CIG group)."""
    poly = [[[-94, 44], [-92, 44], [-92, 46], [-94, 46], [-94, 44]]]
    outlook = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"LABEL": "0.10", "VALID": "202603041200", "EXPIRE": "202603051200"},
                "geometry": {"type": "Polygon", "coordinates": poly},
            },
            {
                "type": "Feature",
                "properties": {"LABEL": "SIGN", "VALID": "202603041200", "EXPIRE": "202603051200"},
                "geometry": {"type": "Polygon", "coordinates": poly},
            },
        ],
    }
    url = SPC_PROB_URL.format(day=1, hazard="torn")
    respx.get(url).mock(return_value=httpx.Response(200, json=outlook))

    result = await spc_client.get_spc_outlook(
        MINNEAPOLIS_LAT, MINNEAPOLIS_LON, 1, "tornado",
    )

    assert result["probability"] == 10
    assert result["significant"] is True
    assert result["intensity_group"] is None


@respx.mock
async def test_probabilistic_malformed_labels_do_not_crash(spc_client):
    """A null or numeric LABEL must be skipped, not raise (regression guard)."""
    poly = [[[-94, 44], [-92, 44], [-92, 46], [-94, 46], [-94, 44]]]
    outlook = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"LABEL": None, "VALID": "202603041200", "EXPIRE": "202603051200"},
                "geometry": {"type": "Polygon", "coordinates": poly},
            },
            {
                "type": "Feature",
                "properties": {"LABEL": 0.05, "VALID": "202603041200", "EXPIRE": "202603051200"},
                "geometry": {"type": "Polygon", "coordinates": poly},
            },
            {
                "type": "Feature",
                "properties": {"LABEL": "0.15", "VALID": "202603041200", "EXPIRE": "202603051200"},
                "geometry": {"type": "Polygon", "coordinates": poly},
            },
        ],
    }
    url = SPC_PROB_URL.format(day=1, hazard="hail")
    respx.get(url).mock(return_value=httpx.Response(200, json=outlook))

    result = await spc_client.get_spc_outlook(
        MINNEAPOLIS_LAT, MINNEAPOLIS_LON, 1, "hail",
    )

    # null is skipped, the numeric coerces to "0.05" (5%), "0.15" wins at 15%
    assert result["probability"] == 15
    assert result["significant"] is False


@respx.mock
async def test_empty_response_body(spc_client):
    """Empty response body is treated as no risk."""
    url = SPC_OUTLOOK_URL.format(day=1)
    respx.get(url).mock(return_value=httpx.Response(200, content=b""))

    result = await spc_client.check_risk_for_point(MINNEAPOLIS_LAT, MINNEAPOLIS_LON)

    assert result["risk_level"] == "NONE"


@respx.mock
async def test_stale_fallback_for_categorical(spc_client):
    """Stale cache entry is returned when upstream returns 500."""
    await spc_client._cache.set("spc_cat_day1", MOCK_SPC_OUTLOOK, 0.01)
    await asyncio.sleep(0.02)

    url = SPC_OUTLOOK_URL.format(day=1)
    respx.get(url).mock(return_value=httpx.Response(500))

    result = await spc_client.get_categorical_outlook(1)

    assert result == MOCK_SPC_OUTLOOK


@respx.mock
async def test_fetch_outlook_categorical_branch(spc_client):
    """fetch_outlook dispatches to categorical when outlook_type='categorical'."""
    url = SPC_OUTLOOK_URL.format(day=1)
    respx.get(url).mock(return_value=httpx.Response(200, json=MOCK_SPC_OUTLOOK))

    result = await spc_client.fetch_outlook(1, "categorical")

    assert "features" in result
    assert len(result["features"]) == 2


async def test_get_spc_outlook_exception(spc_client):
    """Exception in fetch_outlook returns error dict with debug info."""
    from unittest.mock import AsyncMock
    spc_client.fetch_outlook = AsyncMock(side_effect=Exception("network error"))

    result = await spc_client.get_spc_outlook(
        MINNEAPOLIS_LAT, MINNEAPOLIS_LON, 1, "tornado",
    )

    assert "error" in result
    assert "tornado" in result["error"]
    assert "debug" in result
    assert "url" in result["debug"]
    assert "network error" in result["debug"]["exception"]


@respx.mock
async def test_probabilistic_404_returns_no_risk(spc_client):
    """404 from SPC means no outlook issued — returns zero probability, not error."""
    url = SPC_PROB_URL.format(day=2, hazard="torn")
    respx.get(url).mock(return_value=httpx.Response(404))

    result = await spc_client.get_spc_outlook(
        MINNEAPOLIS_LAT, MINNEAPOLIS_LON, 2, "tornado",
    )

    assert "error" not in result
    assert result["probability"] == 0
    assert result["hazard"] == "tornado"
    assert result["day"] == 2


@respx.mock
async def test_categorical_404_returns_no_risk(spc_client):
    """404 for categorical outlook returns NONE risk, not error."""
    url = SPC_OUTLOOK_URL.format(day=3)
    respx.get(url).mock(return_value=httpx.Response(404))

    result = await spc_client.check_risk_for_point(MINNEAPOLIS_LAT, MINNEAPOLIS_LON, day=3)

    assert "error" not in result
    assert result["risk_level"] == "NONE"
    assert result["day"] == 3


@respx.mock
async def test_national_outlook_summary(spc_client):
    """national_outlook_summary returns areas list for each risk level."""
    url = SPC_OUTLOOK_URL.format(day=1)
    respx.get(url).mock(return_value=httpx.Response(200, json=MOCK_SPC_OUTLOOK))

    result = await spc_client.get_national_outlook_summary(1)

    assert "areas" in result
    assert result["day"] == 1
    # TSTM and MRGL features both present
    assert len(result["areas"]) == 2
    risk_levels = {a["risk_level"] for a in result["areas"]}
    assert "TSTM" in risk_levels
    assert "MRGL" in risk_levels
    for area in result["areas"]:
        assert "risk_description" in area
        assert "region" in area
        assert "is_significant" in area


@respx.mock
async def test_national_outlook_summary_error(spc_client):
    """HTTP failure in national_outlook_summary returns error dict with debug info."""
    url = SPC_OUTLOOK_URL.format(day=1)
    respx.get(url).mock(return_value=httpx.Response(500))

    result = await spc_client.get_national_outlook_summary(1)

    assert "error" in result
    assert "debug" in result

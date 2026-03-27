"""Tests for CODSUS bulletin parser and client."""

import asyncio

import httpx
import pytest
import respx

from stormscope.codsus import (
    CODSUSClient,
    Front,
    PressureCenter,
    SurfaceAnalysis,
    _decode_coord,
    parse_bulletin,
)
from stormscope.iem import IEM_BASE

SAMPLE_BULLETIN = """\
000
ASUS02 KWBC 261500
CODSUS

CODED SURFACE FRONTAL POSITIONS
NATIONAL WEATHER SERVICE WEATHER PREDICTION CENTER
COLLEGE PARK MD
1100 AM EDT WED MAR 26 2026

VALID 261500Z
HIGHS 1033 4151338 1038 6521384
LOWS 1007 4500915 1003 3831008
COLD 4350836 4300849 4250870 4200893
WARM 4500915 4500930 4500945
STNRY 4111054 4171062 4271074 4301088
OCFNT 5321372 5381374 5421359
TROF 4480917 4480927 4530938
COLD WK 3500900 3450910 3400920
WARM STG 4200900 4250910 4300920
DRYLN 3800950 3750960 3700970
"""

SAMPLE_ASUS01_TEXT = """\
419
ASUS01 KWBC 261500
CODSUS

CODED SURFACE FRONTAL POSITIONS
NWS WEATHER PREDICTION CENTER COLLEGE PARK MD

VALID 261500Z
HIGHS 1015 35112 1014 37108
LOWS 1005 3995 1000 36101
COLD 3995 3896 3897 37100
"""

SAMPLE_LIST_RESPONSE = {
    "data": [
        {"product_id": "202603261500-KWBC-ASUS02-CODSUS"},
        {"product_id": "202603261200-KWBC-ASUS01-CODSUS"},
        {"product_id": "202603261200-KWBC-ASUS02-CODSUS"},
    ],
}


class TestDecodeCoord:
    def test_basic(self):
        lat, lon = _decode_coord("4170931")
        assert lat == 41.7
        assert lon == -93.1

    def test_high_latitude(self):
        lat, lon = _decode_coord("6521384")
        assert lat == 65.2
        assert lon == -138.4

    def test_low_latitude(self):
        lat, lon = _decode_coord("3500900")
        assert lat == 35.0
        assert lon == -90.0

    def test_zero_longitude_offset(self):
        lat, lon = _decode_coord("4500915")
        assert lat == 45.0
        assert lon == -91.5


class TestParseBulletin:
    def test_valid_time(self):
        result = parse_bulletin(SAMPLE_BULLETIN)
        assert result.valid_time == "261500Z"

    def test_highs(self):
        result = parse_bulletin(SAMPLE_BULLETIN)
        highs = [c for c in result.pressure_centers if c.type == "high"]
        assert len(highs) == 2
        assert highs[0].pressure_mb == 1033
        assert highs[0].lat == 41.5
        assert highs[0].lon == -133.8
        assert highs[1].pressure_mb == 1038

    def test_lows(self):
        result = parse_bulletin(SAMPLE_BULLETIN)
        lows = [c for c in result.pressure_centers if c.type == "low"]
        assert len(lows) == 2
        assert lows[0].pressure_mb == 1007
        assert lows[0].lat == 45.0
        assert lows[0].lon == -91.5
        assert lows[1].pressure_mb == 1003

    def test_cold_front(self):
        result = parse_bulletin(SAMPLE_BULLETIN)
        cold = [f for f in result.fronts if f.type == "cold"]
        assert len(cold) == 2
        assert cold[0].strength == "standard"
        assert len(cold[0].coords) == 4
        assert cold[0].coords[0] == (43.5, -83.6)

    def test_weak_cold_front(self):
        result = parse_bulletin(SAMPLE_BULLETIN)
        cold = [f for f in result.fronts if f.type == "cold"]
        weak = [f for f in cold if f.strength == "weak"]
        assert len(weak) == 1
        assert len(weak[0].coords) == 3
        assert weak[0].coords[0] == (35.0, -90.0)

    def test_strong_warm_front(self):
        result = parse_bulletin(SAMPLE_BULLETIN)
        warm = [f for f in result.fronts if f.type == "warm"]
        strong = [f for f in warm if f.strength == "strong"]
        assert len(strong) == 1
        assert len(strong[0].coords) == 3
        assert strong[0].coords[0] == (42.0, -90.0)

    def test_dryline(self):
        result = parse_bulletin(SAMPLE_BULLETIN)
        dryln = [f for f in result.fronts if f.type == "dryline"]
        assert len(dryln) == 1
        assert len(dryln[0].coords) == 3
        assert dryln[0].strength == "standard"

    def test_warm_front(self):
        result = parse_bulletin(SAMPLE_BULLETIN)
        warm = [f for f in result.fronts if f.type == "warm"]
        assert len(warm) == 2
        standard = [f for f in warm if f.strength == "standard"]
        assert len(standard) == 1
        assert len(standard[0].coords) == 3

    def test_stationary_front(self):
        result = parse_bulletin(SAMPLE_BULLETIN)
        stnry = [f for f in result.fronts if f.type == "stationary"]
        assert len(stnry) == 1
        assert len(stnry[0].coords) == 4

    def test_occluded_front(self):
        result = parse_bulletin(SAMPLE_BULLETIN)
        ocfnt = [f for f in result.fronts if f.type == "occluded"]
        assert len(ocfnt) == 1
        assert len(ocfnt[0].coords) == 3

    def test_trough(self):
        result = parse_bulletin(SAMPLE_BULLETIN)
        trof = [f for f in result.fronts if f.type == "trough"]
        assert len(trof) == 1
        assert len(trof[0].coords) == 3

    def test_empty_bulletin(self):
        result = parse_bulletin("")
        assert result.valid_time is None
        assert result.fronts == []
        assert result.pressure_centers == []

    def test_missing_valid_line(self):
        result = parse_bulletin("HIGHS 1033 4151338\nLOWS 1007 4500915\n")
        assert result.valid_time is None
        assert len(result.pressure_centers) == 2

    def test_front_counts(self):
        result = parse_bulletin(SAMPLE_BULLETIN)
        # 2 cold (standard + weak), 2 warm (standard + strong), 1 stationary,
        # 1 occluded, 1 trough, 1 dryline
        assert len(result.fronts) == 8

    def test_continuation_lines(self):
        text = """\
VALID 271800Z
HIGHS 1020 2880861 1042 5051086 1041 4851059 1036 6491386 1024 6420449 1014
6860627 1031 4221356 1033 4631272
LOWS 1006 3451016 1009 3870857
STNRY 3451015 3431034 3511048 3671057 3891062 3851078 3701096 3671134 3661165
3751193 3951215
"""
        result = parse_bulletin(text)
        highs = [c for c in result.pressure_centers if c.type == "high"]
        assert len(highs) == 8
        assert highs[-1].pressure_mb == 1033
        lows = [c for c in result.pressure_centers if c.type == "low"]
        assert len(lows) == 2
        stnry = [f for f in result.fronts if f.type == "stationary"]
        assert len(stnry) == 1
        assert len(stnry[0].coords) == 11


@pytest.fixture
def codsus_client():
    return CODSUSClient()


@respx.mock
async def test_fetch_latest(codsus_client):
    respx.get(f"{IEM_BASE}/api/1/nws/afos/list.json").mock(
        return_value=httpx.Response(200, json=SAMPLE_LIST_RESPONSE),
    )
    respx.get(f"{IEM_BASE}/api/1/nwstext/202603261500-KWBC-ASUS02-CODSUS").mock(
        return_value=httpx.Response(200, text=SAMPLE_BULLETIN),
    )

    result = await codsus_client.get_analysis()

    assert isinstance(result, SurfaceAnalysis)
    assert result.valid_time == "261500Z"
    assert len(result.fronts) == 8
    assert len(result.pressure_centers) == 4


@respx.mock
async def test_picks_asus02_over_asus01(codsus_client):
    list_data = {
        "data": [
            {"product_id": "202603261500-KWBC-ASUS01-CODSUS"},
            {"product_id": "202603261500-KWBC-ASUS02-CODSUS"},
        ],
    }
    respx.get(f"{IEM_BASE}/api/1/nws/afos/list.json").mock(
        return_value=httpx.Response(200, json=list_data),
    )
    # ASUS01 text has ASUS01 header — should be skipped
    respx.get(f"{IEM_BASE}/api/1/nwstext/202603261500-KWBC-ASUS01-CODSUS").mock(
        return_value=httpx.Response(200, text=SAMPLE_ASUS01_TEXT),
    )
    route = respx.get(f"{IEM_BASE}/api/1/nwstext/202603261500-KWBC-ASUS02-CODSUS").mock(
        return_value=httpx.Response(200, text=SAMPLE_BULLETIN),
    )

    result = await codsus_client.get_analysis()
    assert route.call_count == 1
    assert result.valid_time == "261500Z"


@respx.mock
async def test_no_asus02_raises(codsus_client):
    list_data = {"data": [{"product_id": "202603261500-KWBC-ASUS01-CODSUS"}]}
    respx.get(f"{IEM_BASE}/api/1/nws/afos/list.json").mock(
        return_value=httpx.Response(200, json=list_data),
    )
    # bulletin text has ASUS01 header — no real ASUS02 available
    respx.get(f"{IEM_BASE}/api/1/nwstext/202603261500-KWBC-ASUS01-CODSUS").mock(
        return_value=httpx.Response(200, text=SAMPLE_ASUS01_TEXT),
    )

    with pytest.raises(ValueError, match="no ASUS02 bulletin found"):
        await codsus_client._fetch_latest()


@respx.mock
async def test_mislabeled_asus02_skipped(codsus_client):
    """IEM sometimes labels ASUS01 content with an ASUS02 product_id."""
    list_data = {
        "data": [
            {"product_id": "202603261500-KWBC-ASUS02-CODSUS"},
            {"product_id": "202603261200-KWBC-ASUS01-CODSUS"},
        ],
    }
    respx.get(f"{IEM_BASE}/api/1/nws/afos/list.json").mock(
        return_value=httpx.Response(200, json=list_data),
    )
    # first entry labeled ASUS02 but content is actually ASUS01
    respx.get(f"{IEM_BASE}/api/1/nwstext/202603261500-KWBC-ASUS02-CODSUS").mock(
        return_value=httpx.Response(200, text=SAMPLE_ASUS01_TEXT),
    )
    # second entry is actually ASUS02
    respx.get(f"{IEM_BASE}/api/1/nwstext/202603261200-KWBC-ASUS01-CODSUS").mock(
        return_value=httpx.Response(200, text=SAMPLE_BULLETIN),
    )

    result = await codsus_client.get_analysis()
    assert result.valid_time == "261500Z"
    assert len(result.fronts) == 8


@respx.mock
async def test_caching(codsus_client):
    respx.get(f"{IEM_BASE}/api/1/nws/afos/list.json").mock(
        return_value=httpx.Response(200, json=SAMPLE_LIST_RESPONSE),
    )
    route = respx.get(f"{IEM_BASE}/api/1/nwstext/202603261500-KWBC-ASUS02-CODSUS").mock(
        return_value=httpx.Response(200, text=SAMPLE_BULLETIN),
    )

    await codsus_client.get_analysis()
    await codsus_client.get_analysis()

    assert route.call_count == 1


@respx.mock
async def test_stale_fallback(codsus_client):
    analysis = parse_bulletin(SAMPLE_BULLETIN)
    await codsus_client._cache.set("codsus_latest", analysis, 0.01)
    await asyncio.sleep(0.02)

    respx.get(f"{IEM_BASE}/api/1/nws/afos/list.json").mock(
        return_value=httpx.Response(500),
    )

    result = await codsus_client.get_analysis()
    assert result.valid_time == "261500Z"


@respx.mock
async def test_empty_listing_raises(codsus_client):
    respx.get(f"{IEM_BASE}/api/1/nws/afos/list.json").mock(
        return_value=httpx.Response(200, json={"data": []}),
    )

    with pytest.raises(ValueError, match="no ASUS02 bulletin found"):
        await codsus_client._fetch_latest()

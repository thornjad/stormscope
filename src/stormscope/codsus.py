"""WPC Coded Surface Frontal Positions (CODSUS) parser and client.

Fetches the ASUS02 high-resolution coded surface bulletin from IEM and parses
it into structured front segments and pressure centers. This is the actual
hand-analyzed surface analysis issued every 3 hours by WPC.
"""

import logging
import re
from dataclasses import dataclass, field

from stormscope.base_client import BaseAPIClient
from stormscope.config import config
from stormscope.iem import IEM_BASE

logger = logging.getLogger(__name__)
_TTL = 2700  # 45 min

_FRONT_KEYWORDS: dict[str, str] = {
    "COLD": "cold",
    "WARM": "warm",
    "STNRY": "stationary",
    "OCFNT": "occluded",
    "TROF": "trough",
    "DRYLN": "dryline",
}

_STRENGTH_QUALIFIERS = {"WK": "weak", "STG": "strong"}

# ASUS02 7-digit coordinate: 3 digits lat*10, 4 digits lon*10
_COORD_RE = re.compile(r"(?<!\d)\d{7}(?!\d)")
# pressure value followed by coordinate
_PRESSURE_RE = re.compile(r"(?<!\d)(\d{3,4})\s+(\d{7})(?!\d)")


@dataclass
class Front:
    type: str
    strength: str  # "standard", "weak", or "strong"
    coords: list[tuple[float, float]]  # [(lat, lon), ...]


@dataclass
class PressureCenter:
    type: str  # "high" or "low"
    pressure_mb: int
    lat: float
    lon: float


@dataclass
class SurfaceAnalysis:
    valid_time: str | None
    fronts: list[Front] = field(default_factory=list)
    pressure_centers: list[PressureCenter] = field(default_factory=list)


def _decode_coord(token: str) -> tuple[float, float]:
    """decode a 7-digit ASUS02 coordinate to (lat, lon).

    Format: first 3 digits = lat * 10, last 4 digits = lon * 10.
    Longitude is always negated (west) — CODSUS bulletins cover North America only.
    """
    lat = int(token[:3]) / 10.0
    lon = -(int(token[3:]) / 10.0)
    return lat, lon


def _parse_valid_time(text: str) -> str | None:
    m = re.search(r"VALID\s+(\d{6})Z?", text)
    if m:
        return m.group(1) + "Z"
    return None


def _parse_pressure_line(line: str, center_type: str) -> list[PressureCenter]:
    """parse a HIGHS or LOWS line into pressure centers."""
    centers = []
    for m in _PRESSURE_RE.finditer(line):
        pressure = int(m.group(1))
        lat, lon = _decode_coord(m.group(2))
        centers.append(PressureCenter(type=center_type, pressure_mb=pressure, lat=lat, lon=lon))
    return centers


def _parse_front_line(line: str, front_type: str) -> Front | None:
    """parse a single front line into a Front with coordinates."""
    # check for strength qualifier after the keyword
    tokens = line.split()
    strength = "standard"
    if tokens and tokens[0] in _STRENGTH_QUALIFIERS:
        strength = _STRENGTH_QUALIFIERS[tokens[0]]

    coords = [_decode_coord(m.group()) for m in _COORD_RE.finditer(line)]
    if not coords:
        return None
    return Front(type=front_type, strength=strength, coords=coords)


def parse_bulletin(text: str) -> SurfaceAnalysis:
    """parse an ASUS02 coded surface bulletin into structured data."""
    valid_time = _parse_valid_time(text)
    fronts: list[Front] = []
    pressure_centers: list[PressureCenter] = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        if line.startswith("HIGHS"):
            pressure_centers.extend(_parse_pressure_line(line[5:], "high"))
            continue
        if line.startswith("LOWS"):
            pressure_centers.extend(_parse_pressure_line(line[4:], "low"))
            continue

        for keyword, front_type in _FRONT_KEYWORDS.items():
            if line.startswith(keyword):
                remainder = line[len(keyword):].strip()
                front = _parse_front_line(remainder, front_type)
                if front:
                    fronts.append(front)
                break

    return SurfaceAnalysis(valid_time=valid_time, fronts=fronts, pressure_centers=pressure_centers)


class CODSUSClient(BaseAPIClient):
    def __init__(self):
        super().__init__(
            headers={"User-Agent": config.user_agent},
            timeout=15.0,
        )

    async def _fetch_latest(self) -> SurfaceAnalysis:
        client = await self._get_client()

        # list recent CODSUS bulletins
        list_resp = await client.get(
            f"{IEM_BASE}/api/1/nws/afos/list.json",
            params={"pil": "CODSUS"},
        )
        list_resp.raise_for_status()
        entries = list_resp.json().get("data", [])

        # find latest ASUS02 bulletin
        product_id = None
        for entry in entries:
            pid = entry.get("product_id", "")
            if "ASUS02" in pid:
                product_id = pid
                break

        if product_id is None:
            raise ValueError("no ASUS02 bulletin found in CODSUS listing")

        # fetch the bulletin text
        text_resp = await client.get(f"{IEM_BASE}/api/1/nwstext/{product_id}")
        text_resp.raise_for_status()
        bulletin_text = text_resp.text

        return parse_bulletin(bulletin_text)

    async def get_analysis(self) -> SurfaceAnalysis:
        return await self._cache.get_or_fetch(
            "codsus_latest", _TTL, self._fetch_latest,
        )

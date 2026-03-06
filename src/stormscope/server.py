"""stormscope MCP server."""

from contextlib import asynccontextmanager

from fastmcp import FastMCP

from stormscope import tools
from stormscope.config import config


@asynccontextmanager
async def _lifespan(app):
    yield
    await tools.shutdown()


mcp = FastMCP(
    "stormscope",
    lifespan=_lifespan,
    instructions=(
        "You have access to real-time US weather data via the stormscope tools. "
        "At the start of each conversation, if a primary location is configured, "
        "check for active weather alerts using get_alerts. If any of the following "
        "are active, immediately notify the user:\n"
        "- Tornado Warning (take shelter immediately)\n"
        "- Severe Thunderstorm Warning (damaging winds/hail possible)\n"
        "- Flash Flood Warning or Flash Flood Emergency (avoid flood areas)\n"
        "- Extreme Wind Warning\n"
        "- Tsunami Warning\n"
        "- TORNADO EMERGENCY (catastrophic, life-threatening situation)\n\n"
        "For PDS (Particularly Dangerous Situation) watches, emphasize the "
        "elevated threat level. For other alerts (watches, advisories), mention "
        "them when contextually relevant but do not interrupt the user's workflow.\n\n"
        "When the SPC outlook shows ENH or higher risk, proactively fetch "
        "probabilistic tornado/wind/hail outlooks and the national outlook to "
        "provide full context. When MDT or HIGH risk is present nationally, "
        "mention it even if the user's location is not directly affected.\n\n"
        "Use get_briefing for general weather requests. Use specific tools "
        "(get_conditions, get_forecast, get_alerts, get_spc_outlook, get_radar) "
        "when the user asks for targeted data."
    ),
)


def _resolve_location(
    latitude: float | None, longitude: float | None,
) -> tuple[float, float]:
    lat = latitude if latitude is not None else config.primary_latitude
    lon = longitude if longitude is not None else config.primary_longitude
    if lat is None or lon is None:
        raise ValueError(
            "no location provided and no primary location configured. "
            "Set PRIMARY_LATITUDE and PRIMARY_LONGITUDE environment variables "
            "or pass latitude and longitude explicitly."
        )
    return lat, lon


@mcp.tool()
async def get_conditions(
    latitude: float | None = None,
    longitude: float | None = None,
    detail: str = "standard",
) -> dict:
    """Get current weather conditions for a US location.

    Use when: "What's the weather right now?", "How hot is it?", "Is it windy?"

    detail="standard": temperature, feels-like, humidity, wind, sky, visibility, pressure.
    detail="full": adds dewpoint, cloud layers, present weather, raw METAR.

    Omit lat/lon to use configured primary location.
    """
    try:
        lat, lon = _resolve_location(latitude, longitude)
    except ValueError as exc:
        return {"error": str(exc)}
    return await tools.get_conditions(lat, lon, detail)


@mcp.tool()
async def get_forecast(
    latitude: float | None = None,
    longitude: float | None = None,
    mode: str = "daily",
    days: int = 7,
    hours: int = 24,
) -> dict:
    """Get forecast for a US location.

    Use when: "What's the forecast?", "Will it rain?", "Weather this week?"

    mode="daily": 12-hour day/night periods with narrative forecasts (default).
    mode="hourly": hour-by-hour temperature, precip chance, wind.
    mode="raw": gridpoint time-value series for temperature, dewpoint, wind, precip, sky cover.

    days (1-7) controls daily mode. hours (1-48) controls hourly mode.
    Omit lat/lon to use configured primary location.
    """
    try:
        lat, lon = _resolve_location(latitude, longitude)
    except ValueError as exc:
        return {"error": str(exc)}
    return await tools.get_forecast(lat, lon, mode, days, hours)


@mcp.tool()
async def get_alerts(
    latitude: float | None = None,
    longitude: float | None = None,
    severity_filter: str | None = None,
    detail: str = "standard",
) -> dict:
    """Get active weather alerts for a US location.

    Use proactively at conversation start. Also: "Any warnings?", "Is it safe to travel?"

    severity_filter: "Extreme", "Severe", "Moderate", or "Minor" to filter.
    detail="standard": event, severity, headline, description, instructions.
    detail="full": adds VTEC codes, polygon geometry, areaDesc, sender.

    Omit lat/lon to use configured primary location.
    """
    try:
        lat, lon = _resolve_location(latitude, longitude)
    except ValueError as exc:
        return {"error": str(exc)}
    return await tools.get_alerts(lat, lon, severity_filter, detail)


@mcp.tool()
async def get_spc_outlook(
    latitude: float | None = None,
    longitude: float | None = None,
    outlook_type: str = "categorical",
    day: int = 1,
) -> dict:
    """Check SPC severe weather outlook for a US location.

    Use when: "Severe weather risk?", "Storm outlook?", "Should I worry about storms?"

    outlook_type="categorical": risk level (NONE/TSTM/MRGL/SLGT/ENH/MDT/HIGH).
    outlook_type="tornado"/"wind"/"hail": probabilistic hazard percentage + significant flag.

    day: 1=today, 2=tomorrow, 3=day after.
    Omit lat/lon to use configured primary location.
    """
    try:
        lat, lon = _resolve_location(latitude, longitude)
    except ValueError as exc:
        return {"error": str(exc)}
    return await tools.get_spc_outlook(lat, lon, outlook_type, day)


@mcp.tool()
async def get_national_outlook(day: int = 1) -> dict:
    """Get CONUS-wide SPC severe weather risk areas.

    Use when: "Any severe weather in the US?", "National storm outlook?"

    Returns all active risk areas with human-readable region descriptions
    (e.g. "central Oklahoma", "northern Texas"). No lat/lon needed.

    day: 1=today, 2=tomorrow, 3=day after.
    """
    return await tools.get_national_outlook(day)


@mcp.tool()
async def get_radar(
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict:
    """Get NEXRAD radar info with textual weather summary and clickable links.

    Use when: "Show me radar", "What does radar look like?", "Radar imagery?"

    Returns a textual summary of current precipitation and near-term outlook
    (useful when images can't be displayed), plus clickable links to radar
    imagery the user can open in a browser. Also includes station ID, available
    products, and latest scan time.

    Omit lat/lon to use configured primary location.
    """
    try:
        lat, lon = _resolve_location(latitude, longitude)
    except ValueError as exc:
        return {"error": str(exc)}
    return await tools.get_radar(lat, lon)


@mcp.tool()
async def get_briefing(
    latitude: float | None = None,
    longitude: float | None = None,
    detail: str = "standard",
) -> dict:
    """Get a comprehensive weather briefing for a US location.

    The default tool for "What's the weather?" — combines conditions, forecast,
    alerts, and SPC outlook.

    detail="standard": current conditions + today/tonight forecast + alerts + categorical SPC.
    detail="full": adds probabilistic outlooks (when MRGL+), national outlook,
    radar, and day 2-3 SPC forecasts.

    Omit lat/lon to use configured primary location.
    """
    try:
        lat, lon = _resolve_location(latitude, longitude)
    except ValueError as exc:
        return {"error": str(exc)}
    return await tools.get_briefing(lat, lon, detail)


def main():
    mcp.run()


if __name__ == "__main__":
    main()

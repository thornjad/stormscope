# stormscope

Real-time US weather data for AI assistants via MCP. Uses the free NWS API, NOAA Storm Prediction Center data, and Iowa Environmental Mesonet radar.

US locations only. Covers all 50 states, DC, and US territories (Puerto Rico, Guam, USVI, American Samoa). Requests for non-US locations return a clear error. The SPC national outlook covers the contiguous US only.

## What it does

Most tools support a `detail` parameter: **standard** gives a clean summary, **full** adds the technical depth (METAR, VTEC codes, polygon geometry, probabilistic outlooks).

- Current conditions: temperature, wind, humidity, sky, pressure
- Forecast in daily narrative periods, hourly, or raw gridpoint time-value series
- Active weather alerts with severity filtering
- SPC severe weather outlook, both categorical risk and probabilistic tornado/wind/hail
- National severe outlook with human-readable region descriptions
- NEXRAD radar station metadata and imagery URLs
- Combined briefing that pulls everything together and adapts to the situation

## Installation

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
claude mcp add stormscope -- uvx --from git+https://github.com/thornjad/stormscope stormscope
```

Or add to your Claude Code MCP config:

```json
{
  "mcpServers": {
    "stormscope": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/thornjad/stormscope", "stormscope"],
      "env": {
        "PRIMARY_LATITUDE": "44.9778",
        "PRIMARY_LONGITUDE": "-93.2650"
      }
    }
  }
}
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PRIMARY_LATITUDE` | none | Default latitude when coordinates aren't passed explicitly |
| `PRIMARY_LONGITUDE` | none | Default longitude when coordinates aren't passed explicitly |
| `UNITS` | `us` | Unit system (`us` or `si`) |

All location-aware tools accept optional `latitude` and `longitude` parameters. When omitted, they fall back to the primary location. If neither is available, the tool returns an error explaining what to set.

## Tools

| Tool | Description | Key params |
|------|-------------|------------|
| `get_conditions` | Current conditions at a station | `detail`: standard or full |
| `get_forecast` | Forecast in multiple formats | `mode`: daily, hourly, or raw; `days`; `hours` |
| `get_alerts` | Active weather alerts | `severity_filter`; `detail`: standard or full |
| `get_spc_outlook` | SPC outlook for a point | `outlook_type`: categorical, tornado, wind, or hail; `day`: 1-3 |
| `get_national_outlook` | CONUS-wide risk areas (no lat/lon) | `day`: 1-3 |
| `get_radar` | NEXRAD radar metadata and imagery URLs | |
| `get_briefing` | Combined briefing, the default for general weather questions | `detail`: standard or full |

All location-aware tools accept optional `latitude`/`longitude`, falling back to `PRIMARY_LATITUDE`/`PRIMARY_LONGITUDE`.

### Example conversation

These examples show how an AI assistant might present stormscope data. The tools return structured JSON, and the assistant formats it for the user.

**"What's the weather?"** (uses `get_briefing`):

```
Currently 72F and Mostly Sunny in Minneapolis, MN.
Feels like 72F. Wind SW 8 mph. Humidity 45%.
Today: High 78F, increasing clouds, chance of PM thunderstorms.
Tonight: Low 58F, scattered thunderstorms likely.
Severe Weather: Marginal Risk (MRGL) - isolated severe storms possible.
Alerts: None active.
```

**"Give me the full picture"** (uses `get_briefing detail=full`):

```
...plus dewpoint 50F, cloud layers FEW at 3000m, METAR: KMSP 041200Z...
Probabilistic: 5% tornado (significant), 15% wind, 15% hail
National: SLGT risk in central Oklahoma, MRGL in northern Texas
Radar: KMPX, latest scan 12:00Z, N0B/N0S available
Day 2: TSTM, Day 3: NONE
```

## Skill suggestions

Create `.claude/skills/` skills for common patterns:

- **Morning briefing**: `get_briefing detail=full` for a full picture to start the day
- **Quick check**: `get_conditions` for just current conditions
- **Evening review**: `get_forecast mode=daily days=2` for tonight and tomorrow
- **Chase prep**: `get_spc_outlook outlook_type=tornado` + `get_radar` + `get_alerts detail=full`

## Disclaimer

This application is for informational and educational purposes only. It is not intended for use in life-threatening weather conditions or emergency situations, and should not be relied on as a sole source of weather information. Do not rely on this application for critical weather decisions. Always consult official weather services and emergency broadcasts during severe weather. This application may not provide real-time or accurate weather information. The authors shall not be held liable in the event of injury, death, or property damage resulting from reliance on this software. See the included [license](./LICENSE) for specific language limiting liability.

## Development

```bash
git clone https://github.com/thornjad/stormscope.git
cd stormscope
uv sync --group dev
uv run python -m pytest
```

## License

ISC

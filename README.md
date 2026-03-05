# stormscope

Real-time US weather data for AI assistants via MCP. Uses the free NWS API, NOAA Storm Prediction Center data, and Iowa Environmental Mesonet radar -- no API keys, no rate limits, no accounts.

## What it does

- Current conditions with standard or full detail (METAR, cloud layers, dewpoint)
- Forecast in daily, hourly, or raw gridpoint modes
- Active weather alerts with optional VTEC codes and polygon geometry
- SPC severe weather outlook -- categorical risk or probabilistic tornado/wind/hail
- CONUS-wide national severe outlook with region descriptions
- NEXRAD radar station metadata and imagery URLs
- Combined briefing that adapts detail level to the weather situation

A `detail` parameter on shared tools lets casual users get simple output while enthusiasts get the full picture.

## Configuration

```bash
export PRIMARY_LATITUDE=44.9778
export PRIMARY_LONGITUDE=-93.2650
```

| Variable | Default | Description |
|----------|---------|-------------|
| `PRIMARY_LATITUDE` | -- | Primary location latitude |
| `PRIMARY_LONGITUDE` | -- | Primary location longitude |
| `UNITS` | `us` | Unit system (`us` or `si`) |

All location-aware tools accept optional `latitude` and `longitude` parameters. When omitted, they fall back to the configured primary location. If no primary location is set and no coordinates are provided, the tool returns an error.

## Claude Code integration

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

## Tools

| Tool | Params | Description |
|------|--------|-------------|
| `get_conditions` | `detail` (standard/full) | Current conditions. Full adds dewpoint, cloud layers, present weather, raw METAR |
| `get_forecast` | `mode` (daily/hourly/raw), `days`, `hours` | Daily 12h periods, hourly, or raw gridpoint time-value series |
| `get_alerts` | `severity_filter`, `detail` (standard/full) | Active alerts. Full adds VTEC, polygon geometry, areaDesc |
| `get_spc_outlook` | `outlook_type` (categorical/tornado/wind/hail), `day` | Categorical risk level or probabilistic hazard probability |
| `get_national_outlook` | `day` | CONUS-wide risk areas with region descriptions (no lat/lon needed) |
| `get_radar` | -- | NEXRAD station metadata and imagery URLs via IEM |
| `get_briefing` | `detail` (standard/full) | Combined briefing. Full adds probabilistic (when MRGL+), national, radar, day 2-3 |

All location-aware tools accept optional `latitude`/`longitude`, falling back to `PRIMARY_LATITUDE`/`PRIMARY_LONGITUDE`.

### Example output

**Standard** (`get_briefing`):

```
Currently 72°F and Mostly Sunny in Minneapolis, MN.
Feels like 72°F. Wind SW 8 mph. Humidity 45%.
Today: High 78°F, increasing clouds, chance of PM thunderstorms.
Tonight: Low 58°F, scattered thunderstorms likely.
Severe Weather: Marginal Risk (MRGL) - isolated severe storms possible.
Alerts: None active.
```

**Full detail** (`get_briefing detail=full`):

```
...plus dewpoint 50°F, cloud layers FEW at 3000m, METAR: KMSP 041200Z...
Probabilistic: 5% tornado (significant), 15% wind, 15% hail
National: SLGT risk in central Oklahoma, MRGL in northern Texas
Radar: KMPX, latest scan 12:00Z, N0B/N0S available
Day 2: TSTM, Day 3: NONE
```

## Skill suggestions

Create `.claude/skills/` skills for common patterns:

- **Morning briefing**: `get_briefing detail=full` -- full picture to start the day
- **Quick check**: `get_conditions` -- just current conditions
- **Evening review**: `get_forecast mode=daily days=2` -- tonight and tomorrow
- **Chase prep**: `get_spc_outlook outlook_type=tornado` + `get_radar` + `get_alerts detail=full`

## Coverage

US locations only. The NWS API covers the 50 states, DC, and US territories. Requests for non-US locations return a clear error message.

## Disclaimer

This application is for informational and educational purposes only. It is not intended for use in life-threatening weather conditions or emergency situations, and should not be relied on as a sole source of weather information. Do not rely on this application for critical weather decisions. Always consult official weather services and emergency broadcasts during severe weather. This application may not provide real-time or accurate weather information. The authors shall not be held liable in the event of injury, death, or property damage resulting from reliance on this software. See the included [license](./LICENSE) for specific language limiting liability.

## License

ISC

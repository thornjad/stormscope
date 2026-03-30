# StormScope

Real-time US weather data for AI assistants via MCP. Uses the NWS API, NOAA Storm Prediction Center data, NOAA Weather Prediction Center surface analysis, Iowa Environmental Mesonet radar, and Open-Meteo pressure-level model data. Optionally uses data from your Tempest personal weather station.

**US locations only**. Covers all 50 states, DC, and US territories (Puerto Rico, Guam, USVI, American Samoa). Requests for non-US locations return a clear error. The SPC national outlook covers the contiguous US only.

## What it does

Most tools support a `detail` parameter: **standard** gives a clean summary, **full** adds the technical depth (METAR, VTEC codes, polygon geometry, probabilistic outlooks).

- Current conditions: temperature, wind, humidity, sky, pressure
- Forecast in daily narrative periods, hourly, or raw gridpoint time-value series
- Active weather alerts with severity filtering
- SPC severe weather outlook, both categorical risk and probabilistic tornado/wind/hail
- National severe outlook with human-readable region descriptions
- NEXRAD radar station metadata and imagery URLs
- 500mb upper-air analysis: geopotential heights, temperature, wind, and derived vorticity (synoptic-scale resolution from a 5-point finite-difference grid — useful for identifying troughs, ridges, and jet stream patterns, but not mesoscale features)
- Surface analysis: fronts, pressure centers (highs/lows), and warm/cold sector detection relative to the nearest cold front
- Combined briefing that pulls everything together and adapts to the situation

## Installation

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
claude mcp add --scope user stormscope -- uvx --from git+https://github.com/thornjad/stormscope stormscope
```

Or add to your Claude Code MCP config:

```json
{
  "mcpServers": {
    "stormscope": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/thornjad/stormscope", "stormscope"],
      "env": {
        "PRIMARY_LATITUDE": "YOUR_LATITUDE",
        "PRIMARY_LONGITUDE": "YOUR_LONGITUDE"
      }
    }
  }
}
```

## Configuration

| Variable                       | Default | Description                                                                            |
|--------------------------------|---------|----------------------------------------------------------------------------------------|
| `PRIMARY_LATITUDE`             | none    | Default latitude when coordinates aren't passed explicitly                             |
| `PRIMARY_LONGITUDE`            | none    | Default longitude when coordinates aren't passed explicitly                            |
| `UNITS`                        | `us`    | Unit system (`us` or `si`)                                                             |
| `ENABLE_CORELOCATION`          | `false` | Set to `true` to enable macOS CoreLocation (requires Xcode Command Line Tools)         |
| `DISABLE_AUTO_GEOLOCATION`     | `false` | Set to `true` to disable CoreLocation and IP geolocation                               |
| `TEMPEST_TOKEN`                | none    | Tempest Personal Access Token — enables Tempest station integration                    |
| `TEMPEST_STATION_ID`           | none    | Explicit station ID to use (optional, see [Tempest station](#tempest-weather-station)) |
| `TEMPEST_STATION_NAME`         | none    | Station name to match instead of ID (optional)                                         |
| `USE_TEMPEST_STATION_GEOLOCATION` | `false` | Use Tempest station coordinates as the primary location                                |

### Location detection

All location-aware tools accept optional `latitude` and `longitude` parameters. When omitted, the server resolves location through a fallback chain:

1. **Explicit `latitude`/`longitude` params** — the AI can pass coordinates for any location
2. **Tempest station location** (opt-in) — set `USE_TEMPEST_STATION_GEOLOCATION=true` with a configured station to use its coordinates
3. **`PRIMARY_LATITUDE`/`PRIMARY_LONGITUDE` env vars** — precise, recommended for your home location
4. **macOS CoreLocation** (opt-in) — set `ENABLE_CORELOCATION=true`, requires Xcode Command Line Tools, ~100m WiFi-based accuracy, prompts for location permission on first use. Compiles a small Swift helper into `~/Library/Application Support/stormscope/`
5. **IP geolocation** via [ipinfo.io](https://ipinfo.io) — automatic, city-level accuracy, one request per session

Setting `DISABLE_AUTO_GEOLOCATION=true` disables both CoreLocation and IP geolocation (tiers 4 and 5). With auto-geolocation disabled and no env vars or explicit params, tools return an error.

## Tempest personal weather station

If you have a [Tempest](https://tempest.earth/tempest-home-weather-system/) personal weather station, StormScope can enrich NWS data with hyper-local sensor readings that NWS cannot provide: solar radiation, UV index, lightning strike counts, air density, and wet bulb temperature. Tempest also supplies sunrise/sunset times in its forecast, which are added to `get_forecast` output.

**Tempest data supplements NWS, it doesn't replace it.** NWS provides authoritative alert text, detailed narrative forecasts, and broad coverage. Tempest provides hyper-local precision at your exact station location. When a Tempest station is within range, StormScope uses Tempest values for temperature, feels-like, humidity, wind, and pressure, and sets `data_source: "tempest"` in the response.

If the Tempest API is unavailable, all tools fall back to NWS data without error.

### Setup

1. Get a Personal Access Token from the [Tempest developer portal](https://tempest.earth/tempest-home-weather-system/).
2. Find your station ID from the Tempest app or API (Settings → Stations, or from the URL at `tempestwx.com/station/<id>`).
3. Add to your MCP environment:

```json
{
  "TEMPEST_TOKEN": "your-token-here",
  "TEMPEST_STATION_ID": "your-station-id"
}
```

### Station resolution

When `TEMPEST_STATION_ID` is not set, StormScope auto-discovers the nearest station associated with your token. If the nearest station is more than 5 miles from the request coordinates, it is not used (to avoid attaching irrelevant data to a distant location). You can also identify a station by name with `TEMPEST_STATION_NAME` (matched case-insensitively against the station's `name` and `public_name` fields).

| Variable                       | Purpose                                                                                                                              |
|--------------------------------|--------------------------------------------------------------------------------------------------------------------------------------|
| `TEMPEST_TOKEN`                | Required. Enables all Tempest functionality.                                                                                         |
| `TEMPEST_STATION_ID`           | Use a specific station by numeric ID.                                                                                                |
| `TEMPEST_STATION_NAME`         | Use a specific station by name.                                                                                                      |
| `USE_TEMPEST_STATION_GEOLOCATION` | Set to `true` to use the station's GPS coordinates as the primary location. Requires `TEMPEST_STATION_ID` or `TEMPEST_STATION_NAME`. |
|                                |                                                                                                                                      |

## Tools

| Tool                   | Description                                                      | Key params                                                                         |
|------------------------|------------------------------------------------------------------|------------------------------------------------------------------------------------|
| `get_conditions`       | Current conditions at a station                                  | `detail`: standard or full                                                         |
| `get_forecast`         | Forecast in multiple formats                                     | `mode`: daily, hourly, or raw; `days` (1-7, default 7); `hours` (1-48, default 24) |
| `get_alerts`           | Active weather alerts                                            | `severity_filter`: Extreme, Severe, Moderate, or Minor; `detail`: standard or full |
| `get_spc_outlook`      | SPC outlook for a point                                          | `outlook_type`: categorical, tornado, wind, or hail; `day`: 1-3                    |
| `get_national_outlook` | CONUS-wide risk areas (no lat/lon)                               | `day`: 1-3                                                                         |
| `get_radar`            | NEXRAD radar with textual summary and clickable links            |                                                                                    |
| `get_upper_air`        | 500mb heights, temperature, wind, derived vorticity (Open-Meteo) |                                                                                    |
| `get_surface_analysis` | Fronts, pressure centers, warm/cold sector detection (WPC)       | `day`: 1-3; `detail`: standard or full                                             |
| `get_briefing`         | Combined briefing, the default for general weather questions     | `detail`: standard or full                                                         |

All location-aware tools accept optional `latitude`/`longitude`, falling back to the configured location (see [Location detection](#location-detection)).

Upper-air data provided by [Open-Meteo](https://open-meteo.com/) under CC-BY 4.0. Vorticity is derived from model wind fields at ~110km grid spacing — this captures synoptic-scale features (shortwave troughs, jet maxima) but not mesoscale detail.

### Example conversation

These examples show how an AI assistant might present StormScope data. The tools return structured JSON, and the assistant formats it for the user.

**"What's the weather?"** (uses `get_briefing`):

```
Currently 72F and Mostly Sunny in Minneapolis, MN.
Feels like 72F. Wind SW 8 mph. Humidity 45%.
Today: High 78F, increasing clouds, chance of PM thunderstorms.
Tonight: Low 58F, scattered thunderstorms likely.
Severe Weather: Marginal Risk (MRGL) - isolated severe storms possible.
Alerts: None active.
```

**"What's the severe weather outlook?"** (uses `get_briefing detail=full`):

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
- **Chase prep**: `get_spc_outlook outlook_type=tornado` + `get_surface_analysis` + `get_upper_air` + `get_radar` + `get_alerts detail=full`

## Data sources

StormScope aggregates data from several upstream services. None of these services require authentication or API keys.

**National Weather Service (NWS)** — [api.weather.gov](https://api.weather.gov) ([terms](https://www.weather.gov/disclaimer))
Conditions, forecasts, alerts, and gridpoint data. NWS data is produced by the US federal government and is in the public domain under [17 U.S.C. § 105](https://www.law.cornell.edu/uscode/text/17/105). Use of NWS data does not imply NOAA or NWS endorsement of this project.

**NOAA Storm Prediction Center (SPC)** — [spc.noaa.gov](https://www.spc.noaa.gov) ([terms](https://www.weather.gov/disclaimer))
Categorical and probabilistic severe weather outlooks (days 1-3). SPC data is US government public domain under the same statute as NWS.

**NOAA Weather Prediction Center (WPC)** — [mapservices.weather.noaa.gov](https://mapservices.weather.noaa.gov/vector/rest/services/outlooks/natl_fcst_wx_chart/MapServer)
Surface analysis charts with fronts and pressure centers (days 1-3). WPC data is US government public domain under the same statute as NWS. Analysis charts are updated approximately 4 times per day. No pressure values are provided for H/L centers.

**Iowa Environmental Mesonet (IEM)** — [mesonet.agron.iastate.edu](https://mesonet.agron.iastate.edu) ([disclaimer](https://mesonet.agron.iastate.edu/disclaimer.php))
NEXRAD radar station metadata and imagery. IEM data is in the public domain and may be used freely by anyone for any lawful purpose. Data provided by the Iowa Environmental Mesonet of Iowa State University.

**Open-Meteo** — [open-meteo.com](https://open-meteo.com) ([terms](https://open-meteo.com/en/terms))
500mb upper-air pressure-level data (geopotential heights, temperature, wind). Provided under [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/). StormScope uses the free non-commercial tier and does not support paid Open-Meteo subscriptions.

**ipinfo.io** — [ipinfo.io](https://ipinfo.io) ([terms](https://ipinfo.io/terms-of-service))
IP-based geolocation, used only as a last-resort fallback when no coordinates are configured and CoreLocation is unavailable. One request per server session. StormScope uses the free tier of this service and does not resell or redistribute the geolocation data. Set `DISABLE_AUTO_GEOLOCATION=true` to prevent this request entirely.

All upstream services provide data without warranty of accuracy or availability. StormScope caches responses to reduce request volume but cannot guarantee data freshness. Users of StormScope are responsible for complying with each service's terms of use. The authors of StormScope are not liable for how others use this software or the upstream APIs it connects to.

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

[ISC](./LICENSE)

---

Found this useful? [Buy me a coffee!](https://buymeacoffee.com/jademichaelthornton)

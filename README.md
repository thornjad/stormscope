# StormScope

StormScope is an MCP server that gives AI assistants live US weather data. Ask your assistant for current conditions, a forecast, severe weather outlooks, radar, upper-air analysis, fronts, or a sounding, and it pulls the answer from the National Weather Service, NOAA, the Iowa Environmental Mesonet, and Open-Meteo. If you own a Tempest personal weather station, StormScope can also use your station's readings.

Coverage is limited to US locations, meaning the 50 states and DC as well as the territories (Puerto Rico, Guam, USVI, American Samoa). Requests for anywhere else return an error that says so, with one exception, since the upper-air tool reads global model data and works at any location. The SPC national outlook covers the contiguous US only.

## Quick start

You need Python 3.11 or newer and [uv](https://docs.astral.sh/uv/). Register the server with Claude Code, swapping in your own coordinates:

```bash
claude mcp add --scope user \
  --env PRIMARY_LATITUDE=44.98 \
  --env PRIMARY_LONGITUDE=-93.27 \
  stormscope -- uvx --from git+https://github.com/thornjad/stormscope stormscope
```

Start a new session and ask "What's the weather?" The assistant calls `get_briefing` and answers for your coordinates.

If you would rather edit your MCP config by hand, or your client is something other than Claude Code, the same server definition looks like this. Any client that can launch a stdio MCP server will work.

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

The coordinates are optional, and without them StormScope guesses your location from your IP address, which is only accurate to the city. See [Location detection](#location-detection) for the other options.

## What it does

Most tools take a `detail` parameter. **Standard** returns the summary fields, and **full** adds raw and technical data such as METAR, VTEC codes, polygon geometry, and probabilistic outlooks.

- Current conditions, including temperature, wind, humidity, sky, and pressure
- Forecasts as daily narrative periods, hourly rows, or raw gridpoint time series
- Active weather alerts, with an optional severity filter
- SPC severe weather outlooks, both categorical risk and probabilistic tornado, wind, and hail
- A national severe outlook with region descriptions written for people
- NEXRAD radar station metadata and imagery URLs
- 500mb upper-air analysis with geopotential heights, temperature, wind, and derived vorticity
- Soundings, either the latest observed radiosonde from the nearest launch site (with its distance and direction from you) or a model profile at your exact location, with CAPE/CIN, LCL, freezing level, lapse rates, precipitable water, bulk shear, storm-relative helicity, and temperature inversions
- Surface analysis of fronts and pressure centers (highs and lows), with warm or cold sector detection relative to the nearest cold front
- A combined briefing of conditions, forecast, alerts, and the SPC outlook, with probabilistic outlooks, radar, and the national picture added at `detail=full`

## Tools

| Tool                   | Description                                                      | Key params                                                                         |
|------------------------|------------------------------------------------------------------|------------------------------------------------------------------------------------|
| `get_briefing`         | Combined briefing, the default for general weather questions     | `detail`: standard or full                                                         |
| `get_conditions`       | Current conditions at a station                                  | `detail`: standard or full                                                         |
| `get_forecast`         | Forecast in multiple formats                                     | `mode`: daily, hourly, or raw; `days` (1-7, default 7); `hours` (1-48, default 24) |
| `get_alerts`           | Active weather alerts                                            | `severity_filter`: Extreme, Severe, Moderate, or Minor; `detail`: standard or full |
| `get_spc_outlook`      | SPC outlook for a point                                          | `outlook_type`: categorical, tornado, wind, or hail; `day`: 1-3                    |
| `get_national_outlook` | CONUS-wide risk areas (no lat/lon)                               | `day`: 1-3                                                                         |
| `get_radar`            | NEXRAD radar with textual summary and clickable links            |                                                                                    |
| `get_upper_air`        | 500mb heights, temperature, wind, derived vorticity (Open-Meteo) |                                                                                    |
| `get_sounding`         | Observed radiosonde or model sounding with CAPE, shear, SRH      | `source`: observed or model; `station`; `hours_ahead`: 0-48; `detail`              |
| `get_surface_analysis` | Fronts, pressure centers, warm/cold sector detection (WPC)       | `day`: 1-3; `detail`: standard or full                                             |

Every tool except `get_national_outlook` accepts optional `latitude` and `longitude` parameters and falls back to your configured location when they are omitted. All tools also take an optional `units` override, either a base system (`us` or `si`) or a base with field overrides such as `us,pressure:mb,wind:kt`.

### Notes on upper-air data

Upper-air data comes from [Open-Meteo](https://open-meteo.com/) under CC-BY 4.0. Vorticity is derived from model wind fields at roughly 110 km grid spacing, so it captures synoptic-scale features such as shortwave troughs and jet maxima but misses mesoscale detail.

### Notes on soundings

Observed soundings come from the NWS radiosonde network via IEM. Balloons launch around 00Z and 12Z from about 85 US sites, so the nearest site can be hundreds of kilometers away and up to 12 hours old. With `source=observed`, `get_sounding` reports the site's distance and bearing from you and adds a note when the site is far or the data is old. Use `source=model` for a profile at your exact location or at a forecast hour (up to 48).

Both sources report surface-based CAPE/CIN, LCL/LFC/EL, freezing level, lapse rates, precipitable water, 0-1 and 0-6 km bulk shear, 0-1 and 0-3 km storm-relative helicity, and temperature inversions below about 5 km. The index calculations use [MetPy](https://unidata.github.io/MetPy/).

## Example conversations

The tools return structured JSON and your assistant turns it into prose, roughly like this.

**"What's the weather?"** calls `get_briefing`:

```
Currently 72F and Mostly Sunny in Minneapolis, MN.
Feels like 72F. Wind SW 8 mph. Humidity 45%.
Today: High 78F, increasing clouds, chance of PM thunderstorms.
Tonight: Low 58F, scattered thunderstorms likely.
Severe Weather: Marginal Risk (MRGL) - isolated severe storms possible.
Alerts: None active.
```

**"What's the severe weather outlook?"** calls `get_briefing` with `detail=full`:

```
...plus dewpoint 50F, cloud layers FEW at 3000m, METAR: KMSP 041200Z...
Probabilistic: 5% tornado (significant), 15% wind, 15% hail
National: SLGT risk in central Oklahoma, MRGL in northern Texas
Radar: KMPX, latest scan 12:00Z, N0B/N0S available
Day 2: TSTM, Day 3: NONE
```

## Configuration

Set these as environment variables in your MCP server definition.

| Variable                          | Default | Description                                                                                          |
|-----------------------------------|---------|------------------------------------------------------------------------------------------------------|
| `PRIMARY_LATITUDE`                | none    | Default latitude when coordinates aren't passed explicitly                                           |
| `PRIMARY_LONGITUDE`               | none    | Default longitude when coordinates aren't passed explicitly                                          |
| `UNITS`                           | `us`    | Unit system, `us` or `si`                                                                            |
| `ENABLE_CORELOCATION`             | `false` | Set to `true` to use macOS CoreLocation (needs Xcode Command Line Tools)                             |
| `DISABLE_AUTO_GEOLOCATION`        | `false` | Set to `true` to turn off both CoreLocation and IP geolocation                                       |
| `TEMPEST_TOKEN`                   | none    | Tempest Personal Access Token, which turns on the Tempest integration                                |
| `TEMPEST_STATION_ID`              | none    | Numeric ID of the station to use (optional, see [Tempest](#tempest-personal-weather-station))        |
| `TEMPEST_STATION_NAME`            | none    | Name of the station to use instead of an ID (optional)                                               |
| `USE_TEMPEST_STATION_GEOLOCATION` | `false` | Set to `true` to use the station's coordinates as your primary location (needs a station ID or name) |

### Location detection

Every location-aware tool resolves its location in this order and uses the first match.

1. **Explicit `latitude` and `longitude` parameters.** The assistant can pass coordinates for any place you ask about.
2. **Tempest station location** (opt-in). Set `USE_TEMPEST_STATION_GEOLOCATION=true` with a configured station to use its coordinates.
3. **`PRIMARY_LATITUDE` and `PRIMARY_LONGITUDE`.** These are precise and the best choice for your home location.
4. **macOS CoreLocation** (opt-in). Set `ENABLE_CORELOCATION=true` to get roughly 100 m WiFi-based accuracy. This needs Xcode Command Line Tools, compiles a small Swift helper into `~/Library/Application Support/stormscope/`, and prompts for location permission on first use.
5. **IP geolocation** through [ipinfo.io](https://ipinfo.io). It runs automatically at city-level accuracy, with one request per session.

`DISABLE_AUTO_GEOLOCATION=true` removes options 4 and 5, so if you configured no coordinates and the assistant passes none, tools return an error.

## Tempest personal weather station

A [Tempest](https://tempest.earth/tempest-home-weather-system/) station measures things NWS cannot, so StormScope adds its solar radiation, UV index, lightning strike counts, air density, and wet bulb temperature to the NWS data. The station's sunrise and sunset times also show up in `get_forecast`.

NWS still supplies alert text and narrative forecasts, and it is the only source with national coverage, while Tempest adds precision at your exact location. When a station is in range, StormScope takes temperature, feels-like, humidity, wind, and pressure from it and sets `data_source: "tempest"` in the response. If the Tempest API is down, every tool falls back to NWS data without an error.

### Setup

1. Create a Personal Access Token at [tempestwx.com/settings/tokens](https://tempestwx.com/settings/tokens).
2. Find your station ID in the Tempest app under Settings and then Stations, or in the URL `tempestwx.com/station/<id>`.
3. Add both to the `env` block of your MCP server definition, or pass them as `--env` flags to `claude mcp add`.

```json
{
  "TEMPEST_TOKEN": "your-token-here",
  "TEMPEST_STATION_ID": "your-station-id"
}
```

### Which station gets used

`TEMPEST_TOKEN` is the only required variable. Without `TEMPEST_STATION_ID`, StormScope finds the nearest station on your account, and it can match a station by name instead if you set `TEMPEST_STATION_NAME` (compared case-insensitively against the station's `name` and `public_name`). A station more than 5 miles from the requested coordinates is ignored so that distant readings never get attached to the wrong place.

## Using from scripts

The tools also work without an AI assistant or a running server. FastMCP's in-memory client talks to the server object directly, so the script runs its calls and exits.

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["stormscope @ git+https://github.com/thornjad/stormscope"]
# ///
import asyncio

from fastmcp import Client

from stormscope.server import mcp


async def main():
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_conditions", {"latitude": 44.98, "longitude": -93.27}
        )
        print(result.data)


asyncio.run(main())
```

Run it with `uv run script.py`, and `uv` installs the dependencies into a cached environment on first run. Inside a checkout, `uv run python script.py` works the same way with the dependency block removed.

`call_tool` accepts any tool name from the [Tools](#tools) table with the same parameters, and `result.data` is the dict the tool returns. Configuration comes from the environment as usual (see [Configuration](#configuration)).

Each run starts a fresh process, so the response cache begins empty and importing MetPy adds around a second of startup. A script that makes several calls should keep them inside one `async with` block to share the cache. For a one-off call from a shell in a checkout, `fastmcp call path/to/server.py get_alerts latitude=44.98 longitude=-93.27 --json` also works.

## Ideas for Claude Code skills

If you use Claude Code, you can create skills in `.claude/skills/` for the common patterns. Some ideas follow.

- **Morning briefing** runs `get_briefing detail=full` for the whole picture at the start of the day.
- **Quick check** runs `get_conditions` for current conditions only.
- **Evening review** runs `get_forecast mode=daily days=2` for tonight and tomorrow.
- **Chase prep** chains `get_spc_outlook outlook_type=tornado`, `get_surface_analysis`, `get_upper_air`, `get_sounding`, `get_radar`, and `get_alerts detail=full`.

## Data sources

StormScope combines several upstream services, and none of them need an API key. Responses are cached to keep request volume low, so data can lag slightly behind the source.

- **National Weather Service (NWS)** ([api.weather.gov](https://api.weather.gov), [terms](https://www.weather.gov/disclaimer)) supplies conditions, forecasts, alerts, and gridpoint data. It is produced by the US federal government and is public domain under [17 U.S.C. § 105](https://www.law.cornell.edu/uscode/text/17/105). Using NWS data does not imply NOAA or NWS endorsement of this project.
- **NOAA Storm Prediction Center (SPC)** ([spc.noaa.gov](https://www.spc.noaa.gov), [terms](https://www.weather.gov/disclaimer)) supplies categorical and probabilistic severe weather outlooks for days 1 to 3. It is public domain under the same statute as NWS.
- **NOAA Weather Prediction Center (WPC)** ([mapservices.weather.noaa.gov](https://mapservices.weather.noaa.gov/vector/rest/services/outlooks/natl_fcst_wx_chart/MapServer)) supplies surface analysis charts with fronts and pressure centers for days 1 to 3. It is public domain under the same statute as NWS. Charts update about four times a day, and the high and low centers carry no pressure values.
- **Iowa Environmental Mesonet (IEM)** ([mesonet.agron.iastate.edu](https://mesonet.agron.iastate.edu), [disclaimer](https://mesonet.agron.iastate.edu/disclaimer.php)) supplies NEXRAD radar station metadata and imagery, along with radiosonde (weather balloon) soundings from the NWS upper-air network. IEM data is public domain and free for any lawful purpose. Data provided by the Iowa Environmental Mesonet of Iowa State University.
- **Open-Meteo** ([open-meteo.com](https://open-meteo.com), [terms](https://open-meteo.com/en/terms)) supplies 500mb pressure-level data (geopotential heights, temperature, wind) and model soundings under [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/). StormScope uses the free non-commercial tier and does not support paid subscriptions.
- **ipinfo.io** ([ipinfo.io](https://ipinfo.io), [terms](https://ipinfo.io/terms-of-service)) supplies IP-based geolocation as a last resort when no coordinates are configured and CoreLocation is unavailable. StormScope makes one request per server session on the free tier and does not resell or redistribute the results. Set `DISABLE_AUTO_GEOLOCATION=true` to prevent the request entirely.

All upstream services provide data without warranty of accuracy or availability. You are responsible for following each service's terms of use, and the authors of StormScope are not liable for how others use this software or the upstream APIs it connects to.

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

If StormScope is useful to you, you can [buy me a coffee](https://buymeacoffee.com/jademichaelthornton).

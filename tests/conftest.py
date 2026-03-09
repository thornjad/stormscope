"""Shared test fixtures and mock data."""

import pytest


MINNEAPOLIS_LAT = 44.9778
MINNEAPOLIS_LON = -93.2650

MOCK_POINTS_RESPONSE = {
    "properties": {
        "gridId": "MPX",
        "gridX": 107,
        "gridY": 69,
        "observationStations": "https://api.weather.gov/gridpoints/MPX/107,69/stations",
        "forecast": "https://api.weather.gov/gridpoints/MPX/107,69/forecast",
        "forecastHourly": "https://api.weather.gov/gridpoints/MPX/107,69/forecast/hourly",
        "radarStation": "KMPX",
        "relativeLocation": {
            "properties": {
                "city": "Minneapolis",
                "state": "MN",
            }
        },
    }
}

MOCK_STATIONS_RESPONSE = {
    "features": [
        {
            "properties": {
                "stationIdentifier": "KMSP",
                "name": "Minneapolis-St Paul International Airport",
            }
        }
    ]
}

MOCK_OBSERVATION_RESPONSE = {
    "properties": {
        "timestamp": "2026-03-04T12:00:00+00:00",
        "textDescription": "Mostly Sunny",
        "temperature": {"value": 22.2, "unitCode": "wmoUnit:degC"},
        "dewpoint": {"value": 10.0, "unitCode": "wmoUnit:degC"},
        "relativeHumidity": {"value": 45.0, "unitCode": "wmoUnit:percent"},
        "windSpeed": {"value": 3.6, "unitCode": "wmoUnit:km_h-1"},
        "windDirection": {"value": 225, "unitCode": "wmoUnit:degree_(angle)"},
        "windGust": {"value": None, "unitCode": "wmoUnit:km_h-1"},
        "barometricPressure": {"value": 101325, "unitCode": "wmoUnit:Pa"},
        "visibility": {"value": 16093, "unitCode": "wmoUnit:m"},
        "heatIndex": {"value": None, "unitCode": "wmoUnit:degC"},
        "windChill": {"value": None, "unitCode": "wmoUnit:degC"},
        "cloudLayers": [
            {"base": {"value": 3000, "unitCode": "wmoUnit:m"}, "amount": "FEW"},
        ],
        "presentWeather": [],
        "rawMessage": "KMSP 041200Z 22502KT 10SM FEW100 22/10 A2992",
    }
}

MOCK_FORECAST_RESPONSE = {
    "properties": {
        "periods": [
            {
                "number": 1,
                "name": "Today",
                "startTime": "2026-03-04T06:00:00-06:00",
                "endTime": "2026-03-04T18:00:00-06:00",
                "isDaytime": True,
                "temperature": 78,
                "temperatureUnit": "F",
                "windSpeed": "10 mph",
                "windDirection": "SW",
                "shortForecast": "Mostly Sunny",
                "detailedForecast": "Mostly sunny, with a high near 78.",
            },
            {
                "number": 2,
                "name": "Tonight",
                "startTime": "2026-03-04T18:00:00-06:00",
                "endTime": "2026-03-05T06:00:00-06:00",
                "isDaytime": False,
                "temperature": 58,
                "temperatureUnit": "F",
                "windSpeed": "5 mph",
                "windDirection": "N",
                "shortForecast": "Partly Cloudy",
                "detailedForecast": "Partly cloudy, with a low around 58.",
            },
        ]
    }
}

MOCK_HOURLY_FORECAST_RESPONSE = {
    "properties": {
        "periods": [
            {
                "number": i + 1,
                "startTime": f"2026-03-04T{12 + i:02d}:00:00-06:00",
                "temperature": 72 + i,
                "temperatureUnit": "F",
                "windSpeed": "8 mph",
                "windDirection": "SW",
                "shortForecast": "Mostly Sunny",
                "probabilityOfPrecipitation": {"value": 10},
            }
            for i in range(6)
        ]
    }
}

MOCK_GRIDPOINT_RESPONSE = {
    "properties": {
        "temperature": {
            "uom": "wmoUnit:degC",
            "values": [{"validTime": "2026-03-04T12:00:00+00:00/PT1H", "value": 22.2}],
        },
        "dewpoint": {
            "uom": "wmoUnit:degC",
            "values": [{"validTime": "2026-03-04T12:00:00+00:00/PT1H", "value": 10.0}],
        },
        "windSpeed": {
            "uom": "wmoUnit:km_h-1",
            "values": [{"validTime": "2026-03-04T12:00:00+00:00/PT1H", "value": 15}],
        },
        "elevation": {"value": 255, "unitCode": "wmoUnit:m"},
        "updateTime": "2026-03-04T12:00:00+00:00",
    }
}

MOCK_ALERTS_RESPONSE = {
    "features": [
        {
            "properties": {
                "id": "alert-1",
                "event": "Heat Advisory",
                "severity": "Moderate",
                "urgency": "Expected",
                "certainty": "Likely",
                "headline": "Heat Advisory until 8 PM CDT",
                "description": "Hot temperatures expected.",
                "instruction": "Drink plenty of fluids.",
                "effective": "2026-03-04T12:00:00-06:00",
                "expires": "2026-03-04T20:00:00-06:00",
                "onset": "2026-03-04T12:00:00-06:00",
                "ends": "2026-03-04T20:00:00-06:00",
                "senderName": "NWS Minneapolis MN",
                "areaDesc": "Hennepin, MN",
                "geocode": {"UGC": ["MNC053"]},
                "parameters": {"VTEC": ["/O.NEW.KMPX.HT.Y.0001.260304T1700Z-260305T0100Z/"]},
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-93.5, 44.8], [-93.0, 44.8], [-93.0, 45.2], [-93.5, 45.2], [-93.5, 44.8]]],
            },
        }
    ]
}

MOCK_SPC_OUTLOOK = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "DN": 2,
                "LABEL": "TSTM",
                "LABEL2": "Thunderstorm",
                "stroke": "#55BB55",
                "fill": "#C1E9C1",
                "VALID": "202603041200",
                "EXPIRE": "202603051200",
                "ISSUE": "202603040600",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-95.0, 43.0],
                    [-91.0, 43.0],
                    [-91.0, 47.0],
                    [-95.0, 47.0],
                    [-95.0, 43.0],
                ]],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "DN": 3,
                "LABEL": "MRGL",
                "LABEL2": "Marginal Risk",
                "stroke": "#005500",
                "fill": "#66A366",
                "VALID": "202603041200",
                "EXPIRE": "202603051200",
                "ISSUE": "202603040600",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-94.0, 44.0],
                    [-92.0, 44.0],
                    [-92.0, 46.0],
                    [-94.0, 46.0],
                    [-94.0, 44.0],
                ]],
            },
        },
    ],
}

MOCK_PROB_OUTLOOK = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "LABEL": "5",
                "VALID": "202603041200",
                "EXPIRE": "202603051200",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-94.0, 44.0],
                    [-92.0, 44.0],
                    [-92.0, 46.0],
                    [-94.0, 46.0],
                    [-94.0, 44.0],
                ]],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "LABEL": "SIGN",
                "VALID": "202603041200",
                "EXPIRE": "202603051200",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-94.0, 44.0],
                    [-92.0, 44.0],
                    [-92.0, 46.0],
                    [-94.0, 46.0],
                    [-94.0, 44.0],
                ]],
            },
        },
    ],
}

def _make_upper_air_point(lat, lon, base_height=5520.0, base_speed=20.0, direction=250.0):
    return {
        "latitude": lat,
        "longitude": lon,
        "hourly": {
            "time": [f"2026-03-09T{h:02d}:00" for h in range(12)],
            "geopotential_height_500hPa": [base_height + i for i in range(12)],
            "temperature_500hPa": [-22.0 + i * 0.1 for i in range(12)],
            "wind_speed_500hPa": [base_speed + i * 0.5 for i in range(12)],
            "wind_direction_500hPa": [direction] * 12,
        },
    }


MOCK_UPPER_AIR_RAW = {
    "center": _make_upper_air_point(44.98, -93.27),
    "north": _make_upper_air_point(45.98, -93.27, base_speed=22.0),
    "south": _make_upper_air_point(43.98, -93.27, base_speed=18.0),
    "east": _make_upper_air_point(44.98, -92.27, base_speed=21.0, direction=240.0),
    "west": _make_upper_air_point(44.98, -94.27, base_speed=19.0, direction=260.0),
}

# cold front running NW-SE through Minneapolis area, warm front to the south
MOCK_WPC_FRONTS = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"feat": "Cold Front Valid"},
            "geometry": {
                "type": "MultiLineString",
                "coordinates": [
                    [
                        [-95.0, 47.0],
                        [-94.0, 46.0],
                        [-93.0, 45.0],
                        [-92.0, 44.0],
                    ],
                ],
            },
        },
        {
            "type": "Feature",
            "properties": {"feat": "Warm Front Valid"},
            "geometry": {
                "type": "MultiLineString",
                "coordinates": [
                    [
                        [-95.0, 43.0],
                        [-93.0, 43.5],
                        [-91.0, 44.0],
                    ],
                ],
            },
        },
    ],
}

# low to the NW, high to the SE — realistic warm sector setup
MOCK_WPC_PRESSURE_CENTERS = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"feat": "Low Valid"},
            "geometry": {
                "type": "Point",
                "coordinates": [-96.0, 48.0],
            },
        },
        {
            "type": "Feature",
            "properties": {"feat": "High Valid"},
            "geometry": {
                "type": "Point",
                "coordinates": [-88.0, 40.0],
            },
        },
    ],
}

MOCK_RADAR_RESPONSE = {
    "station_id": "KMPX",
    "available_products": ["N0B", "N0S"],
    "latest_scan_time": "2026-03-04T12:00:00Z",
    "imagery_urls": {
        "composite_url": "https://mesonet.agron.iastate.edu/data/gis/images/4326/USCOMP/n0r_0.png",
        "site_url": "https://mesonet.agron.iastate.edu/data/gis/images/4326/ridge/MPX/N0B/",
        "tile_url_template": "https://mesonet.agron.iastate.edu/cache/tile.py/1.0.0/ridge::MPX-N0B-0/{z}/{x}/{y}.png",
    },
}

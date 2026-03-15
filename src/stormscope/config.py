"""Environment-based configuration."""

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_VALID_UNITS = {"us", "si"}


def _build_user_agent() -> str:
    return "(stormscope, https://github.com/thornjad/stormscope)"


def _parse_coord(name: str) -> float | None:
    raw = os.environ.get(name)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        logger.warning("invalid %s value %r, ignoring", name, raw)
        return None


def _parse_int(name: str) -> int | None:
    raw = os.environ.get(name)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        logger.warning("invalid %s value %r, ignoring", name, raw)
        return None


@dataclass(frozen=True)
class Config:
    primary_latitude: float | None
    primary_longitude: float | None
    units: str
    user_agent: str
    disable_auto_geolocation: bool
    enable_corelocation: bool
    tempest_token: str | None
    tempest_station_id: int | None
    tempest_station_name: str | None
    tempest_use_station_location: bool

    @property
    def tempest_enabled(self) -> bool:
        return self.tempest_token is not None

    @classmethod
    def from_env(cls) -> "Config":
        units = os.environ.get("UNITS", "us").lower()
        if units not in _VALID_UNITS:
            logger.warning("unrecognized UNITS value %r, defaulting to 'us'", units)
            units = "us"

        disable_geo = os.environ.get(
            "DISABLE_AUTO_GEOLOCATION", ""
        ).lower() in ("true", "1", "yes")

        enable_cl = os.environ.get(
            "ENABLE_CORELOCATION", ""
        ).lower() in ("true", "1", "yes")

        tempest_token = os.environ.get("TEMPEST_TOKEN") or None
        tempest_station_id = _parse_int("TEMPEST_STATION_ID")
        tempest_station_name = os.environ.get("TEMPEST_STATION_NAME") or None

        tempest_use_station_location = os.environ.get(
            "TEMPEST_USE_STATION_LOCATION", ""
        ).lower() in ("true", "1", "yes")

        if tempest_use_station_location and tempest_station_id is None and tempest_station_name is None:
            logger.warning(
                "TEMPEST_USE_STATION_LOCATION requires TEMPEST_STATION_ID or "
                "TEMPEST_STATION_NAME; disabling station location override"
            )
            tempest_use_station_location = False

        return cls(
            primary_latitude=_parse_coord("PRIMARY_LATITUDE"),
            primary_longitude=_parse_coord("PRIMARY_LONGITUDE"),
            units=units,
            user_agent=_build_user_agent(),
            disable_auto_geolocation=disable_geo,
            enable_corelocation=enable_cl,
            tempest_token=tempest_token,
            tempest_station_id=tempest_station_id,
            tempest_station_name=tempest_station_name,
            tempest_use_station_location=tempest_use_station_location,
        )


config = Config.from_env()

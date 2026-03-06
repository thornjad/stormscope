"""Tests for configuration."""

import os
from unittest.mock import patch

from stormscope.config import Config


class TestFromEnv:
    @patch.dict(os.environ, {"PRIMARY_LATITUDE": "44.9778", "PRIMARY_LONGITUDE": "-93.2650"}, clear=False)
    def test_parses_coordinates(self):
        cfg = Config.from_env()
        assert cfg.primary_latitude == 44.9778
        assert cfg.primary_longitude == -93.2650

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_coordinates(self):
        cfg = Config.from_env()
        assert cfg.primary_latitude is None
        assert cfg.primary_longitude is None

    @patch.dict(os.environ, {"PRIMARY_LATITUDE": "not_a_number"}, clear=True)
    def test_invalid_latitude_ignored(self):
        cfg = Config.from_env()
        assert cfg.primary_latitude is None

    @patch.dict(os.environ, {"PRIMARY_LATITUDE": "44.9", "PRIMARY_LONGITUDE": "bad"}, clear=True)
    def test_partial_invalid_coordinates(self):
        cfg = Config.from_env()
        assert cfg.primary_latitude == 44.9
        assert cfg.primary_longitude is None

    @patch.dict(os.environ, {"UNITS": "si"}, clear=True)
    def test_si_units(self):
        cfg = Config.from_env()
        assert cfg.units == "si"

    @patch.dict(os.environ, {"UNITS": "metric"}, clear=True)
    def test_invalid_units_defaults_to_us(self):
        cfg = Config.from_env()
        assert cfg.units == "us"

    @patch.dict(os.environ, {}, clear=True)
    def test_default_units(self):
        cfg = Config.from_env()
        assert cfg.units == "us"

    def test_user_agent_format(self):
        cfg = Config.from_env()
        assert "stormscope/" in cfg.user_agent
        assert "github.com/thornjad/stormscope" in cfg.user_agent

    @patch.dict(os.environ, {}, clear=True)
    def test_disable_auto_geolocation_default(self):
        cfg = Config.from_env()
        assert cfg.disable_auto_geolocation is False

    @patch.dict(os.environ, {"DISABLE_AUTO_GEOLOCATION": "true"}, clear=True)
    def test_disable_auto_geolocation_true(self):
        cfg = Config.from_env()
        assert cfg.disable_auto_geolocation is True

    @patch.dict(os.environ, {"DISABLE_AUTO_GEOLOCATION": "1"}, clear=True)
    def test_disable_auto_geolocation_one(self):
        cfg = Config.from_env()
        assert cfg.disable_auto_geolocation is True

    @patch.dict(os.environ, {"DISABLE_AUTO_GEOLOCATION": "YES"}, clear=True)
    def test_disable_auto_geolocation_yes(self):
        cfg = Config.from_env()
        assert cfg.disable_auto_geolocation is True

    @patch.dict(os.environ, {"DISABLE_AUTO_GEOLOCATION": "false"}, clear=True)
    def test_disable_auto_geolocation_false(self):
        cfg = Config.from_env()
        assert cfg.disable_auto_geolocation is False

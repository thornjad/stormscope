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
        assert "stormscope," in cfg.user_agent
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

    @patch.dict(os.environ, {}, clear=True)
    def test_enable_corelocation_default(self):
        cfg = Config.from_env()
        assert cfg.enable_corelocation is False

    @patch.dict(os.environ, {"ENABLE_CORELOCATION": "true"}, clear=True)
    def test_enable_corelocation_true(self):
        cfg = Config.from_env()
        assert cfg.enable_corelocation is True

    @patch.dict(os.environ, {"ENABLE_CORELOCATION": "1"}, clear=True)
    def test_enable_corelocation_one(self):
        cfg = Config.from_env()
        assert cfg.enable_corelocation is True

    @patch.dict(os.environ, {"ENABLE_CORELOCATION": "YES"}, clear=True)
    def test_enable_corelocation_yes(self):
        cfg = Config.from_env()
        assert cfg.enable_corelocation is True

    @patch.dict(os.environ, {"ENABLE_CORELOCATION": "false"}, clear=True)
    def test_enable_corelocation_false(self):
        cfg = Config.from_env()
        assert cfg.enable_corelocation is False


class TestTempestConfig:
    @patch.dict(os.environ, {}, clear=True)
    def test_tempest_disabled_by_default(self):
        cfg = Config.from_env()
        assert cfg.tempest_token is None
        assert cfg.tempest_enabled is False

    @patch.dict(os.environ, {"TEMPEST_TOKEN": "abc123"}, clear=True)
    def test_tempest_token_from_env(self):
        cfg = Config.from_env()
        assert cfg.tempest_token == "abc123"
        assert cfg.tempest_enabled is True

    @patch.dict(os.environ, {"TEMPEST_TOKEN": "tok", "TEMPEST_STATION_ID": "12345"}, clear=True)
    def test_tempest_station_id_parsing(self):
        cfg = Config.from_env()
        assert cfg.tempest_station_id == 12345

    @patch.dict(os.environ, {"TEMPEST_TOKEN": "tok", "TEMPEST_STATION_ID": "bad"}, clear=True)
    def test_tempest_station_id_invalid_ignored(self):
        cfg = Config.from_env()
        assert cfg.tempest_station_id is None

    @patch.dict(os.environ, {"TEMPEST_TOKEN": "tok", "TEMPEST_STATION_NAME": "Holz Lake"}, clear=True)
    def test_tempest_station_name_from_env(self):
        cfg = Config.from_env()
        assert cfg.tempest_station_name == "Holz Lake"

    @patch.dict(
        os.environ,
        {"TEMPEST_TOKEN": "tok", "USE_TEMPEST_STATION_GEOLOCATION": "true", "TEMPEST_STATION_ID": "12345"},
        clear=True,
    )
    def test_use_tempest_station_geolocation_with_id(self):
        cfg = Config.from_env()
        assert cfg.use_tempest_station_geolocation is True

    @patch.dict(
        os.environ,
        {"TEMPEST_TOKEN": "tok", "USE_TEMPEST_STATION_GEOLOCATION": "true"},
        clear=True,
    )
    def test_use_tempest_station_geolocation_without_id_warns(self):
        import logging
        with patch("stormscope.config.logger") as mock_logger:
            cfg = Config.from_env()
            assert cfg.use_tempest_station_geolocation is False
            mock_logger.warning.assert_called_once()
            assert "USE_TEMPEST_STATION_GEOLOCATION" in mock_logger.warning.call_args[0][0]

    @patch.dict(os.environ, {}, clear=True)
    def test_use_tempest_station_geolocation_default_false(self):
        cfg = Config.from_env()
        assert cfg.use_tempest_station_geolocation is False

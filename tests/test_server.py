"""Tests for server location resolution."""

from unittest.mock import patch

import pytest

from stormscope.server import _resolve_location


class TestResolveLocation:
    def test_explicit_coordinates(self):
        lat, lon = _resolve_location(44.9, -93.2)
        assert lat == 44.9
        assert lon == -93.2

    @patch("stormscope.server.config")
    def test_fallback_to_config(self, mock_config):
        mock_config.primary_latitude = 44.9
        mock_config.primary_longitude = -93.2
        lat, lon = _resolve_location(None, None)
        assert lat == 44.9
        assert lon == -93.2

    @patch("stormscope.server.config")
    def test_partial_explicit_overrides_config(self, mock_config):
        mock_config.primary_latitude = 44.9
        mock_config.primary_longitude = -93.2
        lat, lon = _resolve_location(40.0, None)
        assert lat == 40.0
        assert lon == -93.2

    @patch("stormscope.server.config")
    def test_no_location_raises(self, mock_config):
        mock_config.primary_latitude = None
        mock_config.primary_longitude = None
        with pytest.raises(ValueError, match="PRIMARY_LATITUDE"):
            _resolve_location(None, None)

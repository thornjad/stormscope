"""Tests for unit conversion helpers."""

import pytest

from stormscope.units import (
    UnitPrefs, c_to_f, degrees_to_cardinal, kmh_to_mph, m_to_ft,
    m_to_miles, mm_to_inches, ms_to_mph, pa_to_hpa, pa_to_inhg,
    parse_units,
)


class TestCToF:
    def test_freezing(self):
        assert c_to_f(0.0) == 32.0

    def test_boiling(self):
        assert c_to_f(100.0) == 212.0

    def test_body_temp(self):
        assert round(c_to_f(37.0), 1) == 98.6

    def test_negative(self):
        assert c_to_f(-40.0) == -40.0

    def test_none(self):
        assert c_to_f(None) is None


class TestKmhToMph:
    def test_known_value(self):
        assert round(kmh_to_mph(100.0), 1) == 62.1

    def test_zero(self):
        assert kmh_to_mph(0.0) == 0.0

    def test_observation_value(self):
        # 3.6 km/h from mock data
        assert round(kmh_to_mph(3.6), 1) == 2.2

    def test_none(self):
        assert kmh_to_mph(None) is None


class TestMToMiles:
    def test_known_value(self):
        assert round(m_to_miles(1609.344), 4) == 1.0

    def test_visibility(self):
        # 16093 m from mock data
        assert round(m_to_miles(16093), 1) == 10.0

    def test_zero(self):
        assert m_to_miles(0.0) == 0.0

    def test_none(self):
        assert m_to_miles(None) is None


class TestPaToInhg:
    def test_standard_pressure(self):
        assert round(pa_to_inhg(101325), 2) == 29.92

    def test_zero(self):
        assert pa_to_inhg(0.0) == 0.0

    def test_none(self):
        assert pa_to_inhg(None) is None


class TestMsToMph:
    def test_known_value(self):
        assert round(ms_to_mph(10.0), 1) == 22.4

    def test_zero(self):
        assert ms_to_mph(0.0) == 0.0

    def test_none(self):
        assert ms_to_mph(None) is None


class TestMToFt:
    def test_known_value(self):
        assert round(m_to_ft(1.0), 1) == 3.3

    def test_thousand(self):
        assert round(m_to_ft(1000.0)) == 3281

    def test_zero(self):
        assert m_to_ft(0.0) == 0.0

    def test_none(self):
        assert m_to_ft(None) is None


class TestPaToHpa:
    def test_standard_pressure(self):
        assert pa_to_hpa(101325) == 1013.25

    def test_zero(self):
        assert pa_to_hpa(0.0) == 0.0

    def test_none(self):
        assert pa_to_hpa(None) is None


class TestDegreesToCardinal:
    @pytest.mark.parametrize(
        "degrees, expected",
        [
            (0, "N"),
            (45, "NE"),
            (90, "E"),
            (135, "SE"),
            (180, "S"),
            (225, "SW"),
            (270, "W"),
            (315, "NW"),
            (360, "N"),
            (11, "N"),
            (12, "NNE"),
            (350, "N"),
        ],
    )
    def test_cardinal_directions(self, degrees, expected):
        assert degrees_to_cardinal(degrees) == expected

    def test_none(self):
        assert degrees_to_cardinal(None) is None


class TestMmToInches:
    def test_known_value(self):
        assert round(mm_to_inches(25.4), 4) == 1.0

    def test_zero(self):
        assert mm_to_inches(0.0) == 0.0

    def test_none(self):
        assert mm_to_inches(None) is None

    def test_small_value(self):
        assert round(mm_to_inches(2.5), 2) == 0.10


class TestUnitPrefsFromSystem:
    def test_us_defaults(self):
        p = UnitPrefs.from_system("us")
        assert p.temperature == "f"
        assert p.pressure == "inhg"
        assert p.wind == "mph"
        assert p.distance == "mi"
        assert p.accumulation == "in"

    def test_si_defaults(self):
        p = UnitPrefs.from_system("si")
        assert p.temperature == "c"
        assert p.pressure == "mb"
        assert p.wind == "kmh"
        assert p.distance == "km"
        assert p.accumulation == "mm"


class TestParseUnits:
    def test_none_uses_default(self):
        p = parse_units(None, "us")
        assert p.temperature == "f"

    def test_empty_uses_default(self):
        p = parse_units("", "si")
        assert p.temperature == "c"

    def test_us_string(self):
        p = parse_units("us")
        assert p.temperature == "f"
        assert p.pressure == "inhg"

    def test_si_string(self):
        p = parse_units("si")
        assert p.temperature == "c"
        assert p.pressure == "mb"

    def test_override_single_field(self):
        p = parse_units("us,pressure:mb")
        assert p.temperature == "f"
        assert p.pressure == "mb"
        assert p.wind == "mph"

    def test_override_multiple_fields(self):
        p = parse_units("us,pressure:mb,wind:kt")
        assert p.pressure == "mb"
        assert p.wind == "kt"
        assert p.temperature == "f"

    def test_si_with_override(self):
        p = parse_units("si,wind:kt,accumulation:in")
        assert p.temperature == "c"
        assert p.wind == "kt"
        assert p.accumulation == "in"

    def test_invalid_system_raises(self):
        with pytest.raises(ValueError, match="invalid unit system"):
            parse_units("metric")

    def test_invalid_override_format_raises(self):
        with pytest.raises(ValueError, match="invalid unit override"):
            parse_units("us,badformat")

    def test_unknown_field_raises(self):
        with pytest.raises(ValueError, match="unknown unit field"):
            parse_units("us,humidity:pct")

    def test_invalid_field_value_raises(self):
        with pytest.raises(ValueError, match="invalid value"):
            parse_units("us,wind:lightyears")

    def test_whitespace_tolerance(self):
        p = parse_units("us, pressure : mb")
        assert p.pressure == "mb"

    def test_case_insensitive(self):
        p = parse_units("US,Pressure:MB")
        assert p.pressure == "mb"

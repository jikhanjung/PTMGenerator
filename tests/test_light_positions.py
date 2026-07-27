"""The dome's LED geometry: polar table -> unit vectors for the .lp file."""

import math

import pytest

from core.light_positions import LED_COUNT, POLAR_LIGHT_LIST, light_vectors

pytestmark = pytest.mark.unit


def test_one_vector_per_configured_led():
    assert len(light_vectors()) == LED_COUNT == 50


def test_every_vector_is_a_unit_vector():
    for i, (x, y, z) in enumerate(light_vectors()):
        assert math.isclose(math.sqrt(x * x + y * y + z * z), 1.0, abs_tol=1e-9), f"LED {i}"


def test_z_is_cosine_of_elevation():
    for (theta, _phi), (_x, _y, z) in zip(POLAR_LIGHT_LIST, light_vectors(), strict=False):
        assert math.isclose(z, math.cos(math.radians(theta)), abs_tol=1e-9)


def test_all_leds_are_above_the_horizon():
    # The dome only carries LEDs on the upper hemisphere.
    assert all(z > 0 for _x, _y, z in light_vectors())


def test_adjustment_leaves_elevation_untouched():
    for (_x, _y, z0), (_x2, _y2, z1) in zip(light_vectors(0), light_vectors(37), strict=False):
        assert math.isclose(z0, z1, abs_tol=1e-9)


def test_adjustment_rotates_about_the_vertical_axis():
    for (x0, y0, _z0), (x1, y1, _z1) in zip(light_vectors(0), light_vectors(90), strict=False):
        # +90 degrees of azimuth maps (x, y) to (-y, x).
        assert math.isclose(x1, -y0, abs_tol=1e-9)
        assert math.isclose(y1, x0, abs_tol=1e-9)


def test_full_turn_is_identity():
    for base, turned in zip(light_vectors(0), light_vectors(360), strict=False):
        for a, b in zip(base, turned, strict=False):
            assert math.isclose(a, b, abs_tol=1e-9)


def test_led_indices_are_distinct_directions():
    # A duplicated row in the polar table would silently give two shots the
    # same light vector and skew the fit.
    assert len({tuple(pair) for pair in POLAR_LIGHT_LIST}) == LED_COUNT

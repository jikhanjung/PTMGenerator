"""Property-based tests for the dome geometry.

`light_vectors()` has invariants that hold for *any* adjustment angle, not just
the four the example-based tests happen to use. These are the invariants
PTMfitter relies on: unit length, preserved elevation, and an adjustment that is
a rotation about the vertical axis and nothing else.

If one of these ever fails, hypothesis prints the angle that broke it — which is
the part a fixed set of angles cannot give you.
"""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from core.light_positions import LED_COUNT, POLAR_LIGHT_LIST, light_vectors

pytestmark = [pytest.mark.unit, pytest.mark.property]

# The preference is an integer number of degrees; QIntValidator permits any of
# them, including negative and absurd ones, so the property has to hold there
# too rather than only over 0-359.
angles = st.integers(min_value=-3600, max_value=3600)

# Property tests run on every CI leg; a few hundred examples per property is
# plenty for pure arithmetic and keeps the suite inside its one-second budget.
brisk = settings(max_examples=200, deadline=None)


@brisk
@given(adjustment=angles)
def test_every_vector_is_a_unit_vector(adjustment):
    for index, (x, y, z) in enumerate(light_vectors(adjustment)):
        length = math.sqrt(x * x + y * y + z * z)
        assert math.isclose(length, 1.0, abs_tol=1e-9), f"LED {index} at {adjustment} degrees"


@brisk
@given(adjustment=angles)
def test_the_table_length_never_changes(adjustment):
    assert len(light_vectors(adjustment)) == LED_COUNT


@brisk
@given(adjustment=angles)
def test_elevation_is_independent_of_the_adjustment(adjustment):
    # The adjustment turns the dome; it does not tilt it.
    for (theta, _phi), (_x, _y, z) in zip(POLAR_LIGHT_LIST, light_vectors(adjustment), strict=True):
        assert math.isclose(z, math.cos(math.radians(theta)), abs_tol=1e-9)


@brisk
@given(adjustment=angles)
def test_every_led_stays_above_the_horizon(adjustment):
    # The dome only carries LEDs on the upper hemisphere. A z <= 0 would mean
    # a light below the specimen, which PTMfitter cannot fit.
    assert all(z > 0 for _x, _y, z in light_vectors(adjustment))


@brisk
@given(adjustment=angles)
def test_a_full_turn_is_the_identity(adjustment):
    for base, turned in zip(
        light_vectors(adjustment), light_vectors(adjustment + 360), strict=True
    ):
        for a, b in zip(base, turned, strict=True):
            assert math.isclose(a, b, abs_tol=1e-9)


@brisk
@given(adjustment=angles, extra=angles)
def test_an_adjustment_is_a_rotation_about_the_vertical_axis(adjustment, extra):
    # Adding `extra` degrees turns the whole table by exactly that much in the
    # xy-plane and leaves z alone. Turning by a then b therefore equals turning
    # by a+b, which is what makes the preference safe to change between runs.
    angle = math.radians(extra)
    before = light_vectors(adjustment)
    after = light_vectors(adjustment + extra)
    for (x0, y0, z0), (x1, y1, z1) in zip(before, after, strict=True):
        assert math.isclose(x1, x0 * math.cos(angle) - y0 * math.sin(angle), abs_tol=1e-9)
        assert math.isclose(y1, x0 * math.sin(angle) + y0 * math.cos(angle), abs_tol=1e-9)
        assert math.isclose(z1, z0, abs_tol=1e-9)


@brisk
@given(adjustment=angles)
def test_no_two_leds_point_the_same_way(adjustment):
    # A duplicated direction would give two shots the same light vector and
    # skew the fit, and would survive every example-based test that only counts
    # entries.
    directions = {tuple(round(c, 9) for c in vector) for vector in light_vectors(adjustment)}
    assert len(directions) == LED_COUNT

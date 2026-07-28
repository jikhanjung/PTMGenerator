"""Window geometry across the JSON boundary.

QSettings stored a QRect directly; JSON cannot, and a preferences file someone
can read is the point of the move.
"""

import pytest
from PyQt5.QtCore import QRect

from ui.geometry import to_list, to_rect

pytestmark = pytest.mark.unit

DEFAULT = QRect(100, 100, 1400, 800)


def test_a_rect_becomes_four_numbers():
    assert to_list(QRect(10, 20, 800, 600)) == [10, 20, 800, 600]


def test_four_numbers_become_a_rect():
    assert to_rect([10, 20, 800, 600], DEFAULT) == QRect(10, 20, 800, 600)


def test_it_round_trips():
    rect = QRect(3, 4, 500, 400)
    assert to_rect(to_list(rect), DEFAULT) == rect


def test_a_rect_passes_straight_through():
    """A value that never went through the file -- a default, or a preferences
    object still holding what the window put there."""
    assert to_rect(QRect(1, 2, 3, 4), DEFAULT) == QRect(1, 2, 3, 4)


@pytest.mark.parametrize(
    "value",
    [None, "not a rectangle", [1, 2, 3], [1, 2, 3, 4, 5], ["a", "b", "c", "d"], {}],
)
def test_anything_malformed_gives_the_default(value):
    """A hand-edited preferences file must not stop the window opening."""
    assert to_rect(value, DEFAULT) == DEFAULT


@pytest.mark.parametrize("size", [[0, 0, 0, 100], [0, 0, 100, 0], [0, 0, -5, 100]])
def test_an_empty_window_gives_the_default(size):
    """Restoring a zero-width window leaves nothing on screen to click."""
    assert to_rect(size, DEFAULT) == DEFAULT

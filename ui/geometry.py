"""Window geometry across the JSON boundary.

QSettings could store a QRect directly, writing it as ``@Rect(...)``; JSON
cannot, and should not — a preferences file a user can read is the point of
`core.preferences`. Geometry is stored as ``[x, y, width, height]``.

Kept in `ui/` because QRect is Qt, and `core/` imports no Qt.
"""

from PyQt5.QtCore import QRect


def to_list(rect):
    """QRect -> ``[x, y, width, height]``."""
    return [rect.x(), rect.y(), rect.width(), rect.height()]


def to_rect(value, default):
    """``[x, y, width, height]`` -> QRect, falling back to `default`.

    Anything unexpected gives the default rather than raising: a preferences
    file that has been hand-edited, or written by a version that stored
    something else, must not stop the window opening.
    """
    if isinstance(value, QRect):
        return value
    try:
        x, y, width, height = (int(part) for part in value)
    except (TypeError, ValueError):
        return default
    if width <= 0 or height <= 0:
        return default
    return QRect(x, y, width, height)

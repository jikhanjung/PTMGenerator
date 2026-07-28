"""Locating bundled files.

Icons and compiled translations sit next to the source when running from a
checkout, and inside PyInstaller's extraction directory when running from the
frozen .exe. `resource_path` papers over the difference.
"""

import os
import sys


def resource_path(relative_path):
    """Absolute path to a bundled resource, frozen or not."""
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]  # set by PyInstaller
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# Every entry must exist on disk: core/self_test.py checks them against the
# running tree, frozen or not. There was an "open_directory" entry here that no
# file ever backed — QIcon() on a missing path yields a null icon rather than
# raising, so the button rendered with no icon from the first release and
# nothing said so.
ICON = {
    "app": "icons/PTMGenerator2.png",
}


def icon_path(name):
    """Absolute path to one of the ICON entries."""
    return resource_path(ICON[name])


def translation_path(language):
    """Absolute path to a compiled .qm for `language` ("en", "ko")."""
    return resource_path(f"translations/PTMGenerator2_{language}.qm")

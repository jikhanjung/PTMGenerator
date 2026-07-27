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
        base_path = sys._MEIPASS  # set by the PyInstaller bootloader
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


ICON = {
    "app": "icons/PTMGenerator2.png",
    "open_directory": "icons/open_directory.png",
}


def icon_path(name):
    """Absolute path to one of the ICON entries."""
    return resource_path(ICON[name])


def translation_path(language):
    """Absolute path to a compiled .qm for `language` ("en", "ko")."""
    return resource_path(f"translations/PTMGenerator2_{language}.qm")

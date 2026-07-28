"""Preferences, stored as JSON.

Replaces QSettings, which put an ``.ini`` under ``%APPDATA%`` on Windows and
``~/.config`` elsewhere — two locations, neither of them the one the rest of
PaleoBytes uses. This writes a single ``preferences.json`` in
``core.paths.data_dir()``, which a user can open, read and copy between
machines.

The API is deliberately QSettings-shaped — ``value``, ``setValue``, ``sync`` —
because `core.settings` and both windows are written against it, and because a
store that behaves differently from the one it replaces is a source of bugs
that only appear on someone else's preferences file.

Two differences from QSettings, both improvements:

* **Types survive.** QSettings hands everything back as a string, which is why
  `core.settings` has to coerce; JSON keeps an int an int. The coercion stays,
  because it still has to cope with what the old ``.ini`` contained.
* **A key containing ``/`` nests.** ``WindowGeometry/MainWindow`` becomes an
  object, so the file reads as a structure rather than a flat list of paths.
"""

import configparser
import json
import os
import sys
from pathlib import Path

from core.paths import preferences_path
from version import COMPANY_NAME, PROGRAM_NAME


class Preferences:
    """A JSON-backed settings store.

    Args:
        path (str | None): Where to read and write. Defaults to
            `core.paths.preferences_path`, resolved at construction.
    """

    def __init__(self, path=None):
        self.path = path or preferences_path()
        self._values = _read(self.path)

    def value(self, key, default=None):
        node = self._values
        *parents, leaf = key.split("/")
        for part in parents:
            node = node.get(part) if isinstance(node, dict) else None
            if node is None:
                return default
        if not isinstance(node, dict) or leaf not in node:
            return default
        return node[leaf]

    def setValue(self, key, value):
        node = self._values
        *parents, leaf = key.split("/")
        for part in parents:
            child = node.get(part)
            if not isinstance(child, dict):
                child = {}
                node[part] = child
            node = child
        node[leaf] = value

    def sync(self):
        """Write the file, creating the directory if it is not there yet."""
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        # Written in full rather than patched: the file is a few hundred bytes,
        # and a whole-file write cannot leave a half-updated structure behind.
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(self._values, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")

    def as_dict(self):
        """A copy, for tests and for anything that wants to inspect the whole."""
        return json.loads(json.dumps(self._values))


def _read(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, ValueError):
        # A corrupt preferences file must not stop the application starting.
        # Defaults are all reachable from the Preferences dialog anyway.
        return {}
    return loaded if isinstance(loaded, dict) else {}


def legacy_ini_path():
    """Where QSettings kept the preferences before this module existed.

    Reproduced rather than asked of QSettings, so that `core` stays Qt-free.
    QSettings' UserScope IniFormat location is documented and stable.
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.join(str(Path.home()), "AppData", "Roaming")
        return os.path.join(base, COMPANY_NAME, PROGRAM_NAME + ".ini")
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(str(Path.home()), ".config")
    return os.path.join(base, COMPANY_NAME, PROGRAM_NAME + ".conf")


class _CaseSensitiveParser(configparser.ConfigParser):
    def optionxform(self, optionstr):
        return optionstr


def migrate_from_ini(preferences, ini_path=None):
    """Copy an old QSettings ``.ini`` into `preferences`, if there is one.

    Called once at startup so an existing installation keeps its serial port and
    its language. The ``.ini`` is left where it is: reading it again is harmless,
    and deleting a file the user did not ask us to delete is not.

    Returns:
        bool: True if anything was imported.
    """
    path = ini_path or legacy_ini_path()
    if not os.path.exists(path):
        return False

    # Keys are case-sensitive -- "Number_of_LEDs" is one -- and configparser
    # lower-cases them unless optionxform is replaced.
    parser = _CaseSensitiveParser()
    try:
        parser.read(path, encoding="utf-8")
    except (OSError, configparser.Error):
        return False

    imported = False
    for section in parser.sections():
        for key, raw in parser.items(section):
            # Qt writes unsectioned keys under [General]; everything else is a
            # real section and becomes a nested object.
            full = key if section == "General" else f"{section}/{key}"
            value = _from_ini(raw)
            # A dropped value writes nothing rather than an explicit null, which
            # would read the same but sit in the file looking like a setting.
            if value is not None and preferences.value(full) is None:
                preferences.setValue(full, value)
                imported = True
    if imported:
        preferences.sync()
    return imported


def _from_ini(raw):
    """Best-effort typing of an ini string.

    QSettings wrote everything as text, including the geometry it stored as
    ``@Rect(...)``, which nothing here can use and which is dropped rather than
    imported as a string the window would then try to unpack.
    """
    value = raw.strip()
    if value.startswith("@"):
        return None
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    for cast in (int, float):
        try:
            return cast(value)
        except ValueError:
            pass
    return value

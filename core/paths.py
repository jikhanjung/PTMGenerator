"""Where preferences and logs live.

Follows the PaleoBytes convention — see
`../PaperMeister/devlog/20260728_R02_Config_File_Location_Convention.md`, which
was written to be applied across the product family. **Configuration does not
live with data.**

Configuration, under the OS's config location with a ``PaleoBytes`` segment::

    Windows   %LOCALAPPDATA%\\PaleoBytes\\PTMGenerator2\\preferences.json
    macOS     ~/Library/Application Support/PaleoBytes/PTMGenerator2/preferences.json
    Linux     ~/.config/PaleoBytes/PTMGenerator2/preferences.json

Data, which for this application is only the log::

    ~/PaleoBytes/PTMGenerator2/logs/PTMGenerator2_20260728.log

Three reasons they are apart. Settings are machine-local state that costs
nothing to recreate, where data is not — they differ on backup, sync and
migration. Making the data location configurable would otherwise need the
settings to find the data and the data to find the settings. And a data
directory can end up on a shared drive; settings should not follow it there.

**Logs stay with the data on purpose.** Logging is set up before preferences are
read, so a log location that depended on a setting would need either a discarded
first log or a double initialisation. And when something goes wrong, one folder
to look in beats two.

Resolution is `platformdirs`, not `QStandardPaths`: this module is imported by
`core/`, which imports no Qt, and a path module that drags in a GUI toolkit
makes a headless script need one. It also matters on macOS, where the two
disagree — `platformdirs` gives ``Application Support``, which is right for JSON
an application manages itself; ``Preferences`` is the plist/defaults system.

The ``PaleoBytes`` segment is joined here rather than passed as `platformdirs`'
``appauthor``, which is honoured on Windows only — macOS and Linux convention has
no vendor directory, so it is dropped there. Joining it manually keeps the three
platforms consistent.

Both roots are resolved on every call rather than at import, so the environment
overrides can be set after the module is imported — which is what the test suite
does, and what keeps it out of the developer's real files.
"""

import datetime
import os
from pathlib import Path

import platformdirs

from version import COMPANY_NAME, PROGRAM_NAME

#: Overrides the data directory — the log. Used by the test suite.
DATA_DIR_ENV = "PTMGENERATOR2_DATA_DIR"
#: Overrides the configuration directory — preferences.json. Separate from the
#: above, because the two are separate on disk and a test may care about one.
CONFIG_DIR_ENV = "PTMGENERATOR2_CONFIG_DIR"

PREFERENCES_FILE = "preferences.json"


def config_dir():
    """Where preferences.json lives."""
    override = os.environ.get(CONFIG_DIR_ENV)
    if override:
        return str(Path(override).expanduser())
    return os.path.join(platformdirs.user_config_dir(), COMPANY_NAME, PROGRAM_NAME)


def preferences_path():
    return os.path.join(config_dir(), PREFERENCES_FILE)


def data_dir():
    """Where the application's own files go. Only the log, so far."""
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return str(Path(override).expanduser())
    return os.path.join(str(Path.home()), COMPANY_NAME, PROGRAM_NAME)


def log_dir():
    return os.path.join(data_dir(), "logs")


def log_path(when=None):
    """Where stdout is teed, for one day.

    A ``--noconsole`` build leaves no other trace, so the log is the only record
    of a capture that went wrong. One file per day: a run is appended to
    whatever the day already has, so two sessions with the same specimen stay
    together, and an old day's log is never overwritten by a new one.

    Args:
        when (datetime.date | None): The day. Defaults to today.
    """
    day = when or datetime.date.today()
    return os.path.join(log_dir(), f"{PROGRAM_NAME}_{day:%Y%m%d}.log")


def legacy_preferences_path():
    """Where an unreleased build briefly put preferences.json.

    Inside the data directory, before the configuration convention separated
    them. Never shipped in a tagged release, but a developer build wrote there,
    and copying a file under a kilobyte is cheaper than explaining why the
    settings vanished.
    """
    return os.path.join(data_dir(), PREFERENCES_FILE)


def ensure_directories():
    """Create what the application writes into. Safe to call repeatedly."""
    for directory in (config_dir(), data_dir(), log_dir()):
        os.makedirs(directory, exist_ok=True)
    return data_dir()

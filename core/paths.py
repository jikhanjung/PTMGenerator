"""Where user data lives.

Follows the PaleoBytes convention shared with Modan2, CTHarvester and
PaperMeister — on Windows, where the application actually runs, ``~`` is
``%USERPROFILE%``::

    ~/PaleoBytes/PTMGenerator2/
    ├── preferences.json
    └── logs/
        ├── PTMGenerator2_20260727.log
        └── PTMGenerator2_20260728.log

Deliberately *not* under the install directory: the installer writes to
``%LOCALAPPDATA%\\PaleoBytes\\PTMGenerator2`` and removes it again on uninstall,
so anything kept there would be thrown away with the application. Nothing here
is installed or uninstalled; the application creates it on first run.

Resolved on every call rather than at import, so a test — or a second machine
pointed at a copied directory — can redirect it with ``PTMGENERATOR2_DATA_DIR``
without having to import this module at the right moment.
"""

import datetime
import os
from pathlib import Path

from version import COMPANY_NAME, PROGRAM_NAME

#: Overrides everything below. Used by the test suite, which must never touch
#: the developer's real preferences.
DATA_DIR_ENV = "PTMGENERATOR2_DATA_DIR"


def data_dir():
    """The directory holding preferences and logs."""
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return str(Path(override).expanduser())
    return os.path.join(str(Path.home()), COMPANY_NAME, PROGRAM_NAME)


def preferences_path():
    return os.path.join(data_dir(), "preferences.json")


def log_dir():
    return os.path.join(data_dir(), "logs")


def log_path(when=None):
    """Where stdout is teed, for one day.

    A ``--noconsole`` build leaves no other trace, so the log is the only record
    of a capture that went wrong. One file per day rather than one per run: a
    run is appended to whatever the day already has, so two sessions with the
    same specimen stay together, and an old day's log is never overwritten by a
    new one.

    Args:
        when (datetime.date | None): The day. Defaults to today.
    """
    day = when or datetime.date.today()
    return os.path.join(log_dir(), f"{PROGRAM_NAME}_{day:%Y%m%d}.log")


def ensure_directories():
    """Create what the application writes into. Safe to call repeatedly."""
    for directory in (data_dir(), log_dir()):
        os.makedirs(directory, exist_ok=True)
    return data_dir()

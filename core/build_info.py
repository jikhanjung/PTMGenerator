"""Which build this is, not just which version.

`version.py` says what was released. This says which build of it the user is
actually running — the build number, when it was built, and the commit it came
from. That is the difference between a bug report naming `0.2.0-alpha.3` and
one that identifies the exact executable.

`PTMGenerator2.spec` writes `build_info.json` at build time and bundles it, so
the values are stamped by whatever built the artifact rather than computed on
the user's machine.

**A source checkout has no such file, and the fallback says so.** The build
number reads "local" and the date "development": a bug report carrying those is
telling the truth about where the binary came from, where a plausible-looking
`1` would be a lie. That is the same reasoning as the `0.0.0+unknown` version
fallback the shared guide asks for.
"""

import json
import os
import sys

from version import __version__

BUILD_INFO_FILE = "build_info.json"

#: What a checkout reports. Deliberately not number-shaped.
DEVELOPMENT = {
    "version": __version__,
    "build_number": "local",
    "build_date": "development",
    "commit": "unknown",
}


def _candidates():
    """Where the file might be, frozen or not, in the order to trust them.

    Not `core.resources.resource_path`: that resolves the non-frozen case
    against the *current working directory*, and the build metadata has to
    read the same whatever directory the application was started from.

    `sys._MEIPASS` comes first because it is the bundle's own directory and is
    therefore authoritative for a frozen build. **It is not the same as the
    directory holding the executable.** PyInstaller 6 puts a onedir build's
    data in an `_internal/` subdirectory, so beside-the-executable is a real
    layout for older versions and a stale file waiting to win for this one.
    Both are checked; the bundle's is preferred.
    """
    paths = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        paths.append(os.path.join(meipass, BUILD_INFO_FILE))
    if getattr(sys, "frozen", False):
        paths.append(os.path.join(os.path.dirname(sys.executable), BUILD_INFO_FILE))
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths.append(os.path.join(here, BUILD_INFO_FILE))
    return paths


def read(paths=None):
    """The build metadata, falling back to `DEVELOPMENT`.

    Never raises. This runs during startup and on the About dialog, and a
    malformed or unreadable metadata file is not a reason to keep the user out
    of the application — or out of the dialog that would tell them the version
    to put in their bug report.

    Args:
        paths (list[str] | None): Where to look. Defaults to the bundled
            locations; a test passes its own.
    """
    for path in paths or _candidates():
        try:
            # utf-8 rather than the platform default: this is read at startup,
            # and a byte cp949 cannot decode on Korean Windows would otherwise
            # take the application down before it opens.
            with open(path, encoding="utf-8") as fh:
                loaded = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(loaded, dict):
            return {**DEVELOPMENT, **loaded}
    return dict(DEVELOPMENT)


def summary(info=None):
    """One line for the About dialog: ``0.2.0-alpha.3 (build 412, 2026-08-04)``.

    The commit is left out — it is in the diagnostics, where someone pasting a
    bug report wants it, and it makes this line unreadable.
    """
    info = info or read()
    return "{} (build {}, {})".format(info["version"], info["build_number"], info["build_date"])

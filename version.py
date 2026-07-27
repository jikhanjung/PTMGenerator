"""PTMGenerator2 version information.

Single source of truth. Everything that needs the version reads it from here:
the window title, the PyInstaller spec's output filename, pyproject.toml's
dynamic version, and the release workflow's tag check.

Bump it with `python scripts/bump_version.py <major|minor|patch|...>` rather
than editing this file by hand — the script keeps CHANGELOG.md and the git tag
in step. See VERSION_MANAGEMENT.md.
"""

import semver

__version__ = "0.1.2"

_ver = semver.VersionInfo.parse(__version__)
__version_info__ = (_ver.major, _ver.minor, _ver.patch)

COMPANY_NAME = "PaleoBytes"
PROGRAM_NAME = "PTMGenerator2"

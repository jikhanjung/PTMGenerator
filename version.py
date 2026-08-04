"""PTMGenerator2 version information.

Single source of truth. Everything that needs the version reads it from here:
the window title, the PyInstaller spec's output filename, pyproject.toml's
dynamic version, and the release workflow's tag check.

Bump it with `python scripts/bump_version.py <major|minor|patch|...>` rather
than editing this file by hand — the script keeps CHANGELOG.md and the git tag
in step. See VERSION_MANAGEMENT.md.
"""

import semver

__version__ = "0.2.0-alpha.3"

_ver = semver.VersionInfo.parse(__version__)
__version_info__ = (_ver.major, _ver.minor, _ver.patch)

#: The vendor. Load-bearing: it is a segment of the config directory, the data
#: directory, the install directory and the Start-Menu group, so changing it
#: orphans an existing installation's settings. Display strings below are free
#: to change; this one is not. See .guides/branding.md.
COMPANY_NAME = "PaleoBytes"
PROGRAM_NAME = "PTMGenerator2"

#: The copyright holder is the **person**, not the vendor: PaleoBytes is a
#: brand — the name on the installer, the Start-Menu group and the config
#: path — and a brand does not hold a copyright. This is what `LICENSE` says,
#: and `LICENSE` is the record that actually governs.
#:
#: Split into two constants so the About dialog and `docs/manual/conf.py`
#: derive from them rather than each writing the line out. Sphinx wants the
#: years and the holder without the symbol, so it cannot reuse the formatted
#: string, and the two spellings had already drifted — the manual said
#: "2024-2026, PaleoBytes" while LICENSE said "2018-2026 Jikhan Jung".
COPYRIGHT_YEARS = "2018-2026"
COPYRIGHT_HOLDER = "Jikhan Jung"
PROGRAM_COPYRIGHT = f"© {COPYRIGHT_YEARS} {COPYRIGHT_HOLDER}"
PROGRAM_TAGLINE = "Automated Polynomial Texture Mapping capture"
PROGRAM_LICENSE = "MIT"
PROGRAM_HOMEPAGE = "https://github.com/jikhanjung/PTMGenerator"
PROGRAM_MANUAL = "https://jikhanjung.github.io/PTMGenerator/"
PROGRAM_ISSUES = "https://github.com/jikhanjung/PTMGenerator/issues"

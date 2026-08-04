# -*- mode: python ; coding: utf-8 -*-
#
# Single build spec for PTMGenerator2.
#
#   pyinstaller PTMGenerator2.spec   ->  dist/PTMGenerator2/PTMGenerator2.exe
#
# A onedir build, not onefile: the Inno Setup installer in installer/ ships the
# directory, and that is what carries the version — in the installer filename
# and in Add/Remove Programs — so the executable itself has a plain, stable
# name. A onefile build would also unpack itself to a temp directory on every
# launch, which for a ~100 MB bundle is a visible delay before the window
# appears.
#
# The version is still read from version.py, the single source of truth, for the
# Windows file properties. Bump with `python scripts/bump_version.py <part>`.

import datetime
import json
import os
import re
import subprocess
from pathlib import Path

_source = Path(SPECPATH) / "version.py"
_match = re.search(
    r'^__version__\s*=\s*["\'](.+?)["\']', _source.read_text(encoding="utf-8"), re.MULTILINE
)
__version__ = _match.group(1) if _match else "0.0.0"

# The name inside dist/. The installer, not the executable, carries the
# version -- see installer/PTMGenerator2.iss.template.
EXE_NAME = "PTMGenerator2"


def _git(*args):
    """A git value, or None outside a checkout. Never fails the build."""
    try:
        out = subprocess.run(
            ["git", *args], cwd=SPECPATH, capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None if out.returncode == 0 else None


# Stamped into the bundle and read back by core/build_info.py, so a bug report
# identifies the exact executable rather than just the released version.
#
# BUILD_NUMBER comes from the workflow, which derives it from the commit count
# (`git rev-list --count HEAD`) rather than from a per-workflow run number, so
# the build and release paths stamp the same value for the same commit. Falling
# back to the count here means a local build gets a real one too.
_build_number = os.environ.get("BUILD_NUMBER") or _git("rev-list", "--count", "HEAD") or "local"
_build_info = {
    "version": __version__,
    "build_number": _build_number,
    # UTC: this is when the artifact was built, not a date in anyone's day.
    "build_date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
    "commit": _git("rev-parse", "--short", "HEAD") or "unknown",
}
Path(SPECPATH, "build_info.json").write_text(
    json.dumps(_build_info, indent=2) + "\n", encoding="utf-8"
)
print(f"build_info.json: {_build_info}")


a = Analysis(
    ['PTMGenerator2.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('icons/*.png', 'icons'),
        ('translations/*.qm', 'translations'),
        ('build_info.json', '.'),
    ],
    # core/ and ui/ are imported by name from the entry point, which
    # PyInstaller follows, but list the packages so a module that is only
    # reached dynamically cannot be dropped from the bundle.
    hiddenimports=['core', 'ui'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=EXE_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # No UPX: it triggers antivirus heuristics, and an executable quarantined
    # on the user's machine is worse than a larger one. Same reasoning as
    # SolidCompression=no in the installer template.
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # .ico, not .png: on Windows PyInstaller accepts only exe/ico and fails the
    # build outright with a .png unless Pillow happens to be installed to
    # convert it. Linux ignores the icon entirely, which is why a Linux build
    # passed with the .png and the Windows leg did not. Regenerate from the
    # .png with tests/test_packaging.py's recipe if the artwork changes.
    icon=['icons/PTMGenerator2.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=EXE_NAME,
)

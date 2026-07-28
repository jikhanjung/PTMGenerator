# -*- mode: python ; coding: utf-8 -*-
#
# Single build spec for PTMGenerator2.
#
#   pyinstaller PTMGenerator2.spec
#
# The output name is derived from version.py — the single source of truth — plus
# the build date, reproducing the historical naming convention
# (PTMGenerator2_v0.1.2_20251107.exe) without a second version number to keep in
# step. Bump with `python scripts/bump_version.py <part>`.

import re
from datetime import datetime
from pathlib import Path

_source = Path(SPECPATH) / "version.py"
_match = re.search(
    r'^__version__\s*=\s*["\'](.+?)["\']', _source.read_text(encoding="utf-8"), re.MULTILINE
)
__version__ = _match.group(1) if _match else "0.0.0"

EXE_NAME = "PTMGenerator2_v{}_{}.exe".format(__version__, datetime.now().strftime("%Y%m%d"))


a = Analysis(
    ['PTMGenerator2.py'],
    pathex=[],
    binaries=[],
    datas=[('icons/*.png', 'icons'), ('translations/*.qm', 'translations')],
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
    a.binaries,
    a.datas,
    [],
    name=EXE_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
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

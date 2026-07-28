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

import re
from pathlib import Path

_source = Path(SPECPATH) / "version.py"
_match = re.search(
    r'^__version__\s*=\s*["\'](.+?)["\']', _source.read_text(encoding="utf-8"), re.MULTILINE
)
__version__ = _match.group(1) if _match else "0.0.0"

# The name inside dist/. The installer, not the executable, carries the
# version -- see installer/PTMGenerator2.iss.template.
EXE_NAME = "PTMGenerator2"


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
    [],
    exclude_binaries=True,
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

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=EXE_NAME,
)

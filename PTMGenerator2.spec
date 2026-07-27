# -*- mode: python ; coding: utf-8 -*-
#
# Single build spec for PTMGenerator2.
#
#   pyinstaller PTMGenerator2.spec
#
# The output name is derived from PROGRAM_VERSION in PTMGenerator2.py plus the
# build date, reproducing the historical naming convention
# (PTMGenerator2_v0.1.1_20241227.exe) without needing a new spec file per build.

import os
import re
from datetime import datetime

_source = os.path.join(SPECPATH, 'PTMGenerator2.py')
with open(_source, encoding='utf-8') as fh:
    _match = re.search(r'^PROGRAM_VERSION\s*=\s*["\'](.+?)["\']', fh.read(), re.MULTILINE)
VERSION = _match.group(1) if _match else '0.0.0'

EXE_NAME = 'PTMGenerator2_v{}_{}.exe'.format(VERSION, datetime.now().strftime('%Y%m%d'))


a = Analysis(
    ['PTMGenerator2.py'],
    pathex=[],
    binaries=[],
    datas=[('icons/*.png', 'icons'), ('translations/*.qm', 'translations')],
    hiddenimports=[],
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
    icon=['icons/PTMGenerator2.png'],
)

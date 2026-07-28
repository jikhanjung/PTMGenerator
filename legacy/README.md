# legacy/

Superseded code, kept for reference only. **Not maintained, not part of the build.**
The current application is `PTMGenerator2.py` in the repository root.

| File | What it is |
| --- | --- |
| `PTMGenerator.py` | The original Tkinter application, replaced by the PyQt5 rewrite. Requires `Pillow` and `pywin32` (`win32com.shell`), so it is Windows-only. |
| `ptmgenerator2_1.py` | An early snapshot of PTMGenerator2 (v0.1.0), before serial polling, i18n, and PTM generation were finished. |
| `setup.py` | cx_Freeze build script for `PTMGenerator.py`. Current releases are built with PyInstaller from `PTMGenerator2.spec` and packaged as a Windows installer by `installer/PTMGenerator2.iss.template`. |

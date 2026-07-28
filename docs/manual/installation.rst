Installation
============

Requirements
------------

* Python 3.12 or newer
* PyQt5 and pyserial (installed below)
* A DSLR with a remote shutter input, and tethering software that writes
  captured images into a directory on the PC
* An Arduino-based LED dome controller, connected over USB or Bluetooth

Optionally ``PTMfitter.exe``, the external fitter. It is not needed: fitting is
built in, and is what **Generate PTM** uses unless you ask for the external one.

Windows in practice: the tethering software that drops files into the capture
directory is Windows-only, and ``PTMfitter.exe``, if you use it, is a Windows
binary. The Python code has no Windows-specific imports and the interface runs
on Linux and macOS, which is what the test matrix covers.

From a release
--------------

Download ``PTMGenerator2_v<version>_build<n>_Installer.exe`` from the `releases
page <https://github.com/jikhanjung/PTMGenerator/releases>`_ and run it.

It installs per user, so there is no administrator prompt, into
``%LOCALAPPDATA%\Programs\PaleoBytes\PTMGenerator2``. A Start Menu shortcut is created
under **PaleoBytes**; a desktop shortcut is offered and off by default.

Installing a newer version over an older one replaces it in place. Uninstall
from Settings › Apps, or from the Start Menu folder.

Where your settings and logs live
---------------------------------

Neither is in the install directory — the uninstaller removes that. They are in
two places, because they are two different kinds of thing::

    %LOCALAPPDATA%\PaleoBytes\PTMGenerator2\
      preferences.json                 every setting from Edit › Preferences

    %USERPROFILE%\PaleoBytes\PTMGenerator2\
      logs\
        PTMGenerator2_20260728.log     one file per day

Settings go where Windows keeps configuration; see :doc:`configuration` for the
macOS and Linux locations. The log stays with the application's own files, so
that everything you would look at after a failed capture is in one folder.

The application creates both on first run. Uninstalling leaves them alone, so
reinstalling picks up where you left off; delete the folders by hand to start
from defaults.

From source
-----------

.. code-block:: bash

   git clone https://github.com/jikhanjung/PTMGenerator.git
   cd PTMGenerator
   pip install -e .
   python PTMGenerator2.py

Dependencies are declared in ``pyproject.toml``; there is no
``requirements.txt``.

For development, install the extras and the pre-commit hooks instead:

.. code-block:: bash

   make install-dev

To reproduce a build exactly, install from the lockfile for your platform
rather than from the ranges in ``pyproject.toml``:

.. code-block:: bash

   pip install --require-hashes -r requirements-linux.lock

Building the executable
-----------------------

.. code-block:: bash

   make build          # or: pyinstaller PTMGenerator2.spec

The output name is generated from ``version.py`` plus the build date — for
example ``PTMGenerator2_v0.1.2_20260728.exe`` — so bumping the version in the
source is all that is needed for a new release name.

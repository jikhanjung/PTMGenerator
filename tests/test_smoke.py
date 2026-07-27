"""Import and startup checks that must pass on every OS in the CI matrix.

If a module does not import or the window does not construct on a platform,
there is no point running the rest of the suite there.
"""

import importlib

import pytest

pytestmark = pytest.mark.smoke

CORE_MODULES = [
    "core.capture_session",
    "core.image_data",
    "core.light_positions",
    "core.ptm_builder",
    "core.resources",
    "core.serial_controller",
    "core.settings",
]

UI_MODULES = ["ui.main_window", "ui.preferences_window"]


@pytest.mark.parametrize("name", CORE_MODULES + UI_MODULES + ["version", "PTMGenerator2"])
def test_module_imports(name):
    assert importlib.import_module(name) is not None


def test_core_does_not_depend_on_qt():
    """The whole point of the core/ui split.

    Checked in a subprocess so an earlier test having imported PyQt5 cannot
    mask a core module that pulls it in.
    """
    import subprocess
    import sys

    code = (
        "import sys;"
        "import core.capture_session, core.image_data, core.light_positions,"
        "core.ptm_builder, core.resources, core.serial_controller, core.settings;"
        "sys.exit(1 if 'PyQt5' in sys.modules else 0)"
    )
    assert subprocess.call([sys.executable, "-c", code]) == 0, "core imported PyQt5"


def test_main_window_constructs(main_window):
    assert main_window.windowTitle().startswith("PTMGenerator2")
    assert main_window.image_model.columnCount() == 2


def test_preferences_window_constructs(prefs_window):
    assert prefs_window.windowTitle() == "Preferences"
    # Language, serial port, fitter, LED count, retries, polling, adjustment, OK
    assert prefs_window.layout.rowCount() == 8


def test_entry_point_is_callable():
    import PTMGenerator2

    assert callable(PTMGenerator2.main)

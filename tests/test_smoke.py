"""Import and startup checks that must pass on every OS in the CI matrix.

If a module does not import or the window does not construct on a platform,
there is no point running the rest of the suite there.
"""

import importlib

import pytest

from core import settings as prefs

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
    # Language, serial port, engine, fitter path, LED count, retries, polling,
    # adjustment, OK
    assert prefs_window.form_layout.rowCount() == 9


def test_the_fitter_choice_round_trips(prefs_window, main_window):
    """Picking PTMfitter.exe must survive being written and read back --
    the built-in fitter is the default, so this is the escape hatch."""
    prefs_window.comboFitter.setCurrentIndex(
        prefs_window.comboFitter.findData(prefs.FITTER_EXTERNAL)
    )
    prefs_window.save_settings()
    main_window.read_settings()
    assert main_window.fitter == prefs.FITTER_EXTERNAL


def test_the_fitter_choice_defaults_to_the_builtin(prefs_window):
    assert prefs_window.comboFitter.currentData() == prefs.FITTER_NATIVE


def test_entry_point_is_callable():
    import PTMGenerator2

    assert callable(PTMGenerator2.main)

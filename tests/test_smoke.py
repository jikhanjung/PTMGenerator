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
    # Language, serial port, engine, the engine's size notice, fitter path,
    # LED count, retries, polling, adjustment, OK
    assert prefs_window.form_layout.rowCount() == 10


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


def _choose_fitter(window, fitter):
    window.comboFitter.setCurrentIndex(window.comboFitter.findData(fitter))


def test_the_fitter_path_only_applies_to_the_external_engine(prefs_window):
    # The built-in engine is the default, so the path starts disabled.
    assert not prefs_window.ptmfitter_widget.isEnabled()
    assert not prefs_window.lblPtmFitter.isEnabled()

    _choose_fitter(prefs_window, prefs.FITTER_EXTERNAL)
    assert prefs_window.ptmfitter_widget.isEnabled()
    assert prefs_window.lblPtmFitter.isEnabled()

    _choose_fitter(prefs_window, prefs.FITTER_NATIVE)
    assert not prefs_window.ptmfitter_widget.isEnabled()


def test_the_size_limit_is_said_on_screen_for_ptmfitter_exe(prefs_window):
    """The limit costs a whole capture when it bites, so it is not left to a
    tooltip -- but it is only true of one of the two engines."""
    assert prefs_window.lblFitterWarning.isHidden()

    _choose_fitter(prefs_window, prefs.FITTER_EXTERNAL)
    assert not prefs_window.lblFitterWarning.isHidden()
    assert "megapixel" in prefs_window.lblFitterWarning.text()

    _choose_fitter(prefs_window, prefs.FITTER_NATIVE)
    assert prefs_window.lblFitterWarning.isHidden()


def test_the_fitter_path_row_lines_up_with_the_others(prefs_window):
    """The fitter path is the one row that wraps its widgets in a container.

    A nested layout brings its own content margins, so the field sat indented
    and the row was half again as tall as every other one. Measured rather
    than asserted on the margins directly -- what matters is that the fields
    start at the same x and the rows are the same height.
    """
    prefs_window.show()

    def left_edge(widget):
        return widget.mapTo(prefs_window, widget.rect().topLeft()).x()

    assert left_edge(prefs_window.edtPtmFitter) == left_edge(prefs_window.edtNumberOfLEDs)
    # The container must add no height of its own: it is exactly as tall as
    # the taller of the two widgets in it. (Those differ by a pixel -- a push
    # button is not a line edit -- which is not what this is about. The
    # margins were worth 18.)
    tallest = max(prefs_window.edtPtmFitter.height(), prefs_window.btnPtmFitter.height())
    assert prefs_window.ptmfitter_widget.height() == tallest


def test_switching_engines_keeps_the_fitter_path(prefs_window, main_window):
    # Disabled, not cleared: going back to PTMfitter.exe must not mean
    # browsing for the executable again.
    prefs_window.edtPtmFitter.setText("C:/tools/PTMfitter.exe")
    _choose_fitter(prefs_window, prefs.FITTER_NATIVE)
    prefs_window.save_settings()
    main_window.read_settings()
    assert main_window.ptm_fitter == "C:/tools/PTMfitter.exe"


def test_entry_point_is_callable():
    import PTMGenerator2

    assert callable(PTMGenerator2.main)

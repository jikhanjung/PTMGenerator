"""Shared fixtures.

Two things make the GUI testable without hardware or a display:

* Qt's "offscreen" platform plugin is selected before PyQt5 is imported, so the
  suite runs over SSH and in CI without xvfb.
* QSettings is redirected to a temp directory per test, so the suite never
  reads or writes the real ``PaleoBytes / PTMGenerator2`` preferences.

Building a main window also replaces ``sys.stdout`` with an OutputRedirector
and opens ``output.log`` in the current directory, so the ``main_window``
fixture runs inside a temp cwd and restores stdout afterwards.
"""

import io
import os
import sys

# Must be set before PyQt5 is imported.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtCore import QSettings, qInstallMessageHandler
from PyQt5.QtWidgets import QApplication

_EXPECTED_QT_NOISE = (
    # The offscreen platform plugin emits this for every window it shows.
    "propagateSizeHints",
    # show_image() scales whatever the selection lands on; with no captured
    # image on disk that is a null pixmap. Harmless here, noisy in the log.
    "null pixmap",
)


def _filter_qt_messages(mode, context, message):
    if any(fragment in message for fragment in _EXPECTED_QT_NOISE):
        return
    sys.stderr.write(message + "\n")


qInstallMessageHandler(_filter_qt_messages)


@pytest.fixture(scope="session")
def qapp():
    """The process-wide QApplication.

    A QApplication must exist before any QWidget, and PyQt5 destroys it as soon
    as the last Python reference goes away — hence session scope rather than a
    local in each test.
    """
    app = QApplication.instance() or QApplication(sys.argv[:1])
    # read_settings() -> update_language() expects the attributes the entry
    # point attaches to the application object.
    if not hasattr(app, "translator"):
        app.translator = None
        app.language = "en"
    return app


@pytest.fixture
def settings_dir(tmp_path):
    """Point QSettings at a private directory for the duration of a test."""
    path = tmp_path / "settings"
    path.mkdir()
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(path))
    return path


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """A temp cwd, because building a window writes output.log into it."""
    path = tmp_path / "work"
    path.mkdir()
    monkeypatch.chdir(path)
    return path


@pytest.fixture
def main_window(qapp, settings_dir, workdir):
    """A real PTMGeneratorMainWindow, silenced and cleaned up."""
    from ui.main_window import PTMGeneratorMainWindow

    saved_stdout = sys.stdout
    # Constructing the window replaces sys.stdout with its OutputRedirector,
    # which forwards to whatever sys.stdout was at that moment. Point that at a
    # throwaway buffer so the app's debug printing never reaches the console.
    sys.stdout = io.StringIO()
    window = PTMGeneratorMainWindow()
    window.redirector.stdout = None

    yield window

    window.close()
    window.redirector.close()
    sys.stdout = saved_stdout


@pytest.fixture
def prefs_window(qapp, main_window):
    """A PreferencesWindow parented to the main window."""
    from ui.preferences_window import PreferencesWindow

    window = PreferencesWindow(main_window)
    yield window
    window.close()

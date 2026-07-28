"""PTMGenerator2 — automated Polynomial Texture Mapping capture.

Entry point only. The application lives in two packages:

    core/   Qt-free logic: the serial protocol, the capture policy, the dome's
            light geometry, and the .csv / .lp file formats.
    ui/     The PyQt5 windows that drive it.

Run with `python PTMGenerator2.py`, or build the Windows executable with
`pyinstaller PTMGenerator2.spec`.
"""

import os
import sys

from PyQt5.QtCore import QTranslator
from PyQt5.QtGui import QIcon

from core import paths
from core import self_test as self_test_checks
from core.preferences import Preferences, legacy_ini_path, migrate_from_ini
from core.resources import icon_path, translation_path
from core.settings import LANGUAGE, read_str
from ui import error_handling
from ui.app import PtmApplication
from ui.main_window import PTMGeneratorMainWindow
from version import PROGRAM_NAME, __version__


def open_preferences():
    """The preferences store, with anything QSettings left behind brought over.

    The migration runs on every start and is a no-op once the JSON file has the
    keys; that is cheaper than a flag recording whether it has happened, and it
    also picks up a `.ini` restored from a backup later.
    """
    paths.ensure_directories()
    preferences = Preferences()
    if migrate_from_ini(preferences):
        print(f"imported preferences from {legacy_ini_path()}")
    return preferences


def self_test(argv):
    """Start the application headlessly, check the bundle, and exit.

    Run against the built executable in CI. A source checkout has icons/ and
    translations/ on disk whatever happens; a frozen build only has them if
    PyInstaller was told to bundle them, and if it was not, the application
    starts anyway — with no icon and no Korean. Nothing in a source-based test
    suite can see that.
    """
    # Set before QApplication so no display is needed on a CI runner.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = PtmApplication(argv[:1])
    app.settings = open_preferences()

    print(f"{PROGRAM_NAME} {__version__} self-test")
    print(f"  frozen: {getattr(sys, 'frozen', False)}")
    ok = self_test_checks.run()

    # The window is the real check: it touches settings, resources, the
    # translator and every widget in one go.
    #
    # Constructing it also points sys.stdout at its OutputRedirector, so the
    # real stream has to be put back before the redirector is closed —
    # otherwise the next print() writes to a closed file.
    saved_stdout = sys.stdout
    try:
        window = PTMGeneratorMainWindow()
        title, leds = window.windowTitle(), window.number_of_LEDs
        sys.stdout = saved_stdout
        window.redirector.close()
        window.close()
        print(f"  main window: {title!r}, {leds} LEDs")
    except Exception as error:
        sys.stdout = saved_stdout
        print(f"  main window: FAILED — {type(error).__name__}: {error}")
        ok = False

    print("self-test PASSED" if ok else "self-test FAILED")
    return 0 if ok else 1


def main(argv=None):
    argv = sys.argv if argv is None else argv
    if "--self-test" in argv:
        return self_test(argv)

    app = PtmApplication(argv)
    # Before any window exists: an exception escaping a Qt slot otherwise
    # aborts the process with nothing on screen and nothing in the log.
    error_handling.install()
    app.setWindowIcon(QIcon(icon_path("app")))
    app.settings = open_preferences()

    app.language = read_str(app.settings, LANGUAGE)
    translator = QTranslator()
    translator.load(translation_path(app.language))
    app.installTranslator(translator)
    app.translator = translator

    window = PTMGeneratorMainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())

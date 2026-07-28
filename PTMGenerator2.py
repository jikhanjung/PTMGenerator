"""PTMGenerator2 — automated Polynomial Texture Mapping capture.

Entry point only. The application lives in two packages:

    core/   Qt-free logic: the serial protocol, the capture policy, the dome's
            light geometry, and the .csv / .lp file formats.
    ui/     The PyQt5 windows that drive it.

Run with `python PTMGenerator2.py`, or build the Windows executable with
`pyinstaller PTMGenerator2.spec`.
"""

import sys

from PyQt5.QtCore import QSettings, QTranslator
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from core.resources import icon_path, translation_path
from core.settings import LANGUAGE, read_str
from ui import error_handling
from ui.main_window import PTMGeneratorMainWindow
from version import COMPANY_NAME, PROGRAM_NAME


def main(argv=None):
    argv = sys.argv if argv is None else argv
    app = QApplication(argv)
    # Before any window exists: an exception escaping a Qt slot otherwise
    # aborts the process with nothing on screen and nothing in the log.
    error_handling.install()
    app.translator = None
    app.setWindowIcon(QIcon(icon_path("app")))
    app.settings = QSettings(QSettings.IniFormat, QSettings.UserScope, COMPANY_NAME, PROGRAM_NAME)

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

"""The application object, with the attributes the windows read off it.

`QApplication` carries five things that are ours rather than Qt's: the
translator, the language, the preferences store, the serial port and whether to
restore window geometry. They used to be bolted on by the entry point with plain
attribute assignment, which nothing declares and no stub knows about — when
`check_untyped_defs` was first turned on for `ui/`, that pattern accounted for
most of the findings, and `read_settings()` depending on attributes the entry
point happened to have set was a real fragility rather than a typing nicety.

Declaring them on a subclass is the whole fix: the windows get a typed object,
and a window built by a test or a script gets the defaults instead of an
`AttributeError`.
"""

from typing import cast

from PyQt5.QtCore import QTranslator
from PyQt5.QtWidgets import QApplication

from core.preferences import Preferences


class PtmApplication(QApplication):
    """The QApplication PTMGenerator2 runs on."""

    #: Installed by `update_language`; None when the interface is English.
    translator: QTranslator | None
    #: "en" or "ko".
    language: str
    #: Opened by the entry point. None until then — `read_settings()` opens one
    #: if it finds none, which is what lets a script construct a window.
    settings: Preferences | None
    #: The controller's port, as last read from the preferences.
    serial_port: str | None
    #: Whether to restore each window's position and size.
    remember_geometry: bool

    def __init__(self, argv):
        super().__init__(argv)
        self.translator = None
        self.language = "en"
        self.settings = None
        self.serial_port = None
        self.remember_geometry = True

    def preferences(self) -> Preferences:
        """The preferences store, opening one if the entry point has not.

        Returns a `Preferences` rather than `Optional[Preferences]`, which is
        what the windows want: both of them used to carry the same
        "if it is None, make one" guard, and every use afterwards still had to
        be read as possibly-None.
        """
        if self.settings is None:
            self.settings = Preferences()
        return self.settings


def app() -> PtmApplication:
    """The running application.

    `QApplication.instance()` is typed as returning `Optional[QCoreApplication]`,
    which is honest — there need not be one — but a widget cannot exist without
    it, so every caller here would otherwise be guarding against a case that
    cannot arise by the time a window is being built.
    """
    return cast(PtmApplication, QApplication.instance())


def require[T](value: T | None, what: str) -> T:
    """Assert that a Qt accessor returned something, and hand it back typed.

    `menuBar()`, `horizontalHeader()` and `selectionModel()` are all declared as
    returning an Optional, which is honest — a QTableView with no model has no
    selection model. In `setup_ui` they cannot be None: the widget was just
    constructed and the model just set.

    Written as a check rather than a `cast` so that if one of them ever is None,
    the failure names which one instead of surfacing as
    `AttributeError: 'NoneType' object has no attribute ...` several frames away.
    """
    if value is None:
        raise RuntimeError(f"Qt returned no {what}")
    return value

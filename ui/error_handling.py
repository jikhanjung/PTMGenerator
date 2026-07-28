"""Last-resort handling for exceptions that escape a Qt slot.

An unhandled exception raised inside a signal handler does not unwind to
anything that can report it: PyQt5 prints the traceback and aborts the process,
so the window vanishes with no message and nothing in the log the user could
send on.

This hook is the backstop, not the fix. Handlers that do I/O, parsing or talk to
hardware should still fail gracefully on their own — see
`SerialController.open`, which returns False rather than raising. The hook is
what catches the ones nobody anticipated.
"""

import sys
import traceback

from PyQt5.QtWidgets import QApplication, QMessageBox

#: Set while a dialog is up, so a fault inside the reporting path cannot start
#: an endless stack of dialogs.
_reporting = False


def format_exception(exc_type, exc_value, exc_tb):
    return "".join(traceback.format_exception(exc_type, exc_value, exc_tb))


def handle_exception(exc_type, exc_value, exc_tb, show_dialog=True):
    """Log an escaped exception and tell the user, without exiting."""
    global _reporting

    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    text = format_exception(exc_type, exc_value, exc_tb)
    # stdout is the OutputRedirector once a window exists, so this reaches
    # output.log as well as the console.
    print("Unhandled exception:\n" + text)

    if not show_dialog or _reporting or QApplication.instance() is None:
        return

    _reporting = True
    try:
        QMessageBox.critical(
            None,
            "PTMGenerator2",
            "Something went wrong and the operation was stopped.\n\n"
            f"{exc_type.__name__}: {exc_value}\n\n"
            "The application is still running. Details have been written to "
            "output.log.",
        )
    finally:
        _reporting = False


def install(show_dialog=True):
    """Route uncaught exceptions through `handle_exception`.

    Returns the previous hook, so a caller can restore it.
    """
    previous = sys.excepthook

    def hook(exc_type, exc_value, exc_tb):
        handle_exception(exc_type, exc_value, exc_tb, show_dialog=show_dialog)

    sys.excepthook = hook
    return previous

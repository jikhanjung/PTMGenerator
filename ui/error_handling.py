"""Keeping an exception in a Qt slot from taking the window with it.

An unhandled exception raised inside a signal handler does not unwind to
anything that can report it: PyQt5 prints the traceback and **aborts the
process**, so the window vanishes with no message and nothing in the log the
user could send on.

Two layers, and the order matters:

* **`guard_slot` is the fix.** Every connected handler is wrapped in it, so a
  failure is caught inside the slot — before PyQt5 gets the chance to abort —
  logged, and shown. The application keeps running.
* **`install()`'s `sys.excepthook` is the backstop**, for whatever is not
  guarded. It cannot stop PyQt5's abort; what it guarantees is that the
  traceback reaches the log first.

Handlers that do I/O or talk to hardware should still fail gracefully on their
own — see `SerialController.open`, which returns False rather than raising.
The guard is what catches the ones nobody anticipated.
"""

import functools
import inspect
import sys
import traceback

from PyQt5.QtWidgets import QApplication, QMessageBox

from core.paths import log_path

#: Set while a dialog is up, so a fault inside the reporting path cannot start
#: an endless stack of dialogs.
_reporting = False


def format_exception(exc_type, exc_value, exc_tb):
    return "".join(traceback.format_exception(exc_type, exc_value, exc_tb))


def _positional_limit(func):
    """How many positional arguments `func` will accept, or None for any.

    This is the whole subtlety of wrapping a Qt slot. sip decides how many of
    a signal's arguments to forward by **introspecting the slot**, and a plain
    ``def wrapper(*args, **kwargs)`` advertises that it takes everything. So a
    guarded handler connected to ``clicked(bool)`` or ``currentIndexChanged(int)``
    starts receiving an argument the real function never declared, and every
    one of them fails with "takes 1 positional argument but 2 were given" —
    at which point the guard has broken precisely the slots it was added to
    protect.

    Wrapping keeps `*args`, and the surplus is trimmed here instead.
    """
    try:
        parameters = inspect.signature(func).parameters.values()
    except (TypeError, ValueError):  # a builtin or a C function
        return None
    limit = 0
    for parameter in parameters:
        if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
            return None
        if parameter.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ):
            limit += 1
    return limit


def _drain_override_cursors():
    """Put the pointer back, however deep the stack got.

    Nothing here sets one today. It is in the guard rather than waiting until
    something does, because the failure it prevents — an application stuck
    behind a wait cursor it can no longer clear — is invisible in tests and
    obvious to a user.

    The instance check is not defensive noise: `QApplication.overrideCursor()`
    with no running application calls `qFatal()` and aborts the process. A
    cosmetic cursor must never do that, least of all from inside the error
    path.
    """
    if QApplication.instance() is None:
        return
    while QApplication.overrideCursor() is not None:
        QApplication.restoreOverrideCursor()


def guard_slot(context, show_dialog=True):
    """Wrap a connected handler so a failure reports instead of aborting.

    Args:
        context (str): What the user was doing, named in the dialog and the
            log — "Open Directory", "Generate PTM". A traceback alone does not
            tell someone which button they pressed.
        show_dialog (bool): Off in tests that assert on the log instead.

    Returns:
        A decorator. The wrapped function returns None when it fails, which is
        what makes this safe on a save handler: the caller never reaches
        `accept()`, so the dialog stays open with the error visible rather
        than closing as though the save had worked.
    """

    def decorate(func):
        limit = _positional_limit(func)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if limit is not None:
                args = args[:limit]
            try:
                return func(*args, **kwargs)
            except Exception:
                _drain_override_cursors()
                exc_type, exc_value, exc_tb = sys.exc_info()
                handle_exception(
                    exc_type, exc_value, exc_tb, show_dialog=show_dialog, context=context
                )
                return None

        # What `tests/test_error_handling.py` reads to assert that every
        # connected slot is wrapped. Partial coverage of this pattern is worse
        # than none, because it reads as protection that is not there.
        wrapper.guarded = context  # type: ignore[attr-defined]
        return wrapper

    return decorate


def handle_exception(exc_type, exc_value, exc_tb, show_dialog=True, context=None):
    """Log an escaped exception and tell the user, without exiting."""
    global _reporting

    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    text = format_exception(exc_type, exc_value, exc_tb)
    # stdout is the OutputRedirector once a window exists, so this reaches
    # today's log file as well as the console.
    heading = f"Unhandled exception in {context}" if context else "Unhandled exception"
    print(heading + ":\n" + text)

    if not show_dialog or _reporting or QApplication.instance() is None:
        return

    what = f"{context} could not be completed." if context else "Something went wrong."
    _reporting = True
    try:
        QMessageBox.critical(
            None,
            "PTMGenerator2",
            f"{what}\n\n"
            f"{exc_type.__name__}: {exc_value}\n\n"
            "The application is still running. Details have been written to\n"
            f"{log_path()}",
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

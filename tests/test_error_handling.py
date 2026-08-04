"""Failures reach the user instead of killing the window.

An exception raised inside a Qt slot does not unwind to anything that can
report it: PyQt5 prints the traceback and aborts. These tests pin the two
defences — handlers that fail gracefully, and the hook that catches the rest.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest
import serial

from core.serial_controller import SerialController
from ui import error_handling
from ui.main_window import PTMGeneratorMainWindow

pytestmark = pytest.mark.ui


# -- the serial port going away --------------------------------------------
#
# The port name is stored in preferences, so the application will eventually
# try one that has gone away: the board unplugged, the Arduino IDE's serial
# monitor holding it, a USB port re-enumerated, preferences carried to another
# machine. Before this was guarded, that aborted the process.


@pytest.fixture
def unavailable_port():
    """A controller whose configured port refuses to open."""
    controller = SerialController(port="COM3", log=lambda *a: None)
    patcher = patch.object(
        serial, "Serial", side_effect=serial.SerialException("could not open port COM3")
    )
    patcher.start()
    yield controller
    patcher.stop()


def test_open_reports_failure_instead_of_raising(unavailable_port):
    assert unavailable_port.open() is False
    assert not unavailable_port.is_open


def test_open_records_why(unavailable_port):
    unavailable_port.open()
    assert "COM3" in unavailable_port.last_error


def test_a_permission_error_is_caught_too():
    # Linux raises OSError rather than SerialException when the device node
    # exists but the user is not in the dialout group.
    controller = SerialController(port="/dev/ttyUSB0", log=lambda *a: None)
    with patch.object(serial, "Serial", side_effect=PermissionError(13, "Permission denied")):
        assert controller.open() is False
    assert "Permission denied" in controller.last_error


def test_last_error_is_cleared_by_a_successful_open():
    controller = SerialController(port="COM3", log=lambda *a: None)
    with patch.object(serial, "Serial", side_effect=serial.SerialException("nope")):
        controller.open()
    assert controller.last_error
    with (
        patch.object(serial, "Serial", return_value=MagicMock()),
        patch("core.serial_controller.time.sleep"),
    ):
        assert controller.open() is True
    assert controller.last_error is None


def test_no_port_configured_records_no_error():
    """The two failures are distinguishable, because the UI words them differently."""
    controller = SerialController(port=None, log=lambda *a: None)
    assert controller.open() is False
    assert controller.last_error is None


def test_ensure_serial_ready_survives_an_unavailable_port(main_window):
    main_window.serial.port = "COM3"
    with (
        patch.object(
            serial, "Serial", side_effect=serial.SerialException("could not open port COM3")
        ),
        patch.object(
            PTMGeneratorMainWindow, "confirm_capture_without_controller", return_value=False
        ) as prompt,
    ):
        assert main_window.ensure_serial_ready() is False
    # The prompt is told why, so it can name the port rather than claiming
    # none is configured.
    assert "COM3" in prompt.call_args.args[0]


def test_taking_pictures_with_a_dead_port_does_not_crash(main_window):
    main_window.serial.port = "COM3"
    main_window.number_of_LEDs = 3
    with (
        patch.object(
            serial, "Serial", side_effect=serial.SerialException("could not open port COM3")
        ),
        patch.object(
            PTMGeneratorMainWindow, "confirm_capture_without_controller", return_value=False
        ),
    ):
        main_window.take_all_pictures()
    assert not main_window.timer.isActive()


class TestPortUnavailableDialog:
    """It must say which port and why, not "none is configured"."""

    @pytest.fixture
    def dialog(self, main_window):
        from PyQt5.QtWidgets import QMessageBox

        main_window.serial.port = "COM3"
        boxes = []
        real_init = QMessageBox.__init__

        def record(box, *a, **kw):
            real_init(box, *a, **kw)
            boxes.append(box)

        with (
            patch.object(QMessageBox, "__init__", record),
            patch.object(QMessageBox, "exec", lambda box: 0),
        ):
            main_window.confirm_capture_without_controller("could not open port COM3")
        return boxes[-1]

    def test_names_the_port(self, dialog):
        assert "COM3" in dialog.text()

    def test_gives_the_reason(self, dialog):
        assert "could not open port" in dialog.text()

    def test_does_not_claim_none_is_configured(self, dialog):
        assert "No serial port is configured" not in dialog.text()

    def test_still_offers_to_continue(self, dialog):
        assert sorted(b.text() for b in dialog.buttons()) == ["Cancel", "Continue anyway"]


# -- the backstop ----------------------------------------------------------


@pytest.fixture
def restore_hook():
    saved = sys.excepthook
    yield
    sys.excepthook = saved


def raise_and_capture(show_dialog=False):
    try:
        raise ValueError("something went wrong in a slot")
    except ValueError:
        error_handling.handle_exception(*sys.exc_info(), show_dialog=show_dialog)


def test_install_replaces_the_hook(restore_hook):
    previous = error_handling.install()
    assert sys.excepthook is not previous


def test_the_traceback_is_logged(capsys):
    raise_and_capture()
    logged = capsys.readouterr().out
    assert "Unhandled exception" in logged
    assert "ValueError: something went wrong in a slot" in logged
    assert "raise_and_capture" in logged, "the traceback itself should be logged"


def test_the_user_is_shown_a_dialog(qapp):
    from PyQt5.QtWidgets import QMessageBox

    with patch.object(QMessageBox, "critical") as critical:
        raise_and_capture(show_dialog=True)
    critical.assert_called_once()
    assert "ValueError" in critical.call_args.args[2]


def test_a_failure_inside_the_dialog_does_not_recurse(qapp):
    from PyQt5.QtWidgets import QMessageBox

    calls = []

    def exploding_dialog(*args, **kwargs):
        calls.append(args)
        raise RuntimeError("the reporting path itself failed")

    with patch.object(QMessageBox, "critical", exploding_dialog), pytest.raises(RuntimeError):
        raise_and_capture(show_dialog=True)
    assert len(calls) == 1
    # The guard must be released, or every later exception is reported silently.
    assert error_handling._reporting is False


def test_keyboard_interrupt_is_left_alone(capsys):
    try:
        raise KeyboardInterrupt
    except KeyboardInterrupt:
        with patch.object(sys, "__excepthook__") as default:
            error_handling.handle_exception(*sys.exc_info())
    default.assert_called_once()
    assert "Unhandled exception" not in capsys.readouterr().out


# -- guard_slot -------------------------------------------------------------
#
# The hook above is the backstop. This is the fix: a failure is caught inside
# the slot, before PyQt5 gets to abort the process.


@pytest.fixture
def silent_guard(monkeypatch):
    """guard_slot with the dialog suppressed, and the log captured."""
    logged = []
    monkeypatch.setattr(error_handling, "print", logged.append, raising=False)
    return logged


def test_a_guarded_slot_returns_the_value_on_success():
    @error_handling.guard_slot("Anything")
    def fine(value):
        return value * 2

    assert fine(21) == 42


def test_a_guarded_slot_swallows_the_failure_and_returns_none(silent_guard):
    @error_handling.guard_slot("Doing the thing", show_dialog=False)
    def broken():
        raise ValueError("boom")

    assert broken() is None
    assert any("Doing the thing" in line for line in silent_guard)
    assert any("boom" in line for line in silent_guard)


def test_a_guarded_slot_does_not_catch_a_keyboard_interrupt():
    # Ctrl-C must still quit. `except Exception`, not `except BaseException`.
    @error_handling.guard_slot("Anything", show_dialog=False)
    def interrupted():
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        interrupted()


def test_a_failed_guarded_slot_leaves_no_wait_cursor(qapp):
    """A cursor stack that outlives the failure locks the user out.

    Nothing sets one today; the drain is in the guard so that whoever adds the
    first one does not also have to remember this.
    """
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QCursor
    from PyQt5.QtWidgets import QApplication

    @error_handling.guard_slot("Anything", show_dialog=False)
    def broken():
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        raise ValueError("boom")

    broken()
    assert QApplication.overrideCursor() is None


# The variadic trap, pinned with real signals. sip decides how many of a
# signal's arguments to forward by introspecting the slot, and a plain
# `def wrapper(*args, **kwargs)` says it takes everything -- so without the
# trimming in `_positional_limit`, every guarded slot on `clicked(bool)` or
# `currentIndexChanged(int)` raises "takes 1 positional argument but 2 were
# given" the first time it is pressed. That is a guard that breaks exactly
# what it was added to protect.


def test_a_guarded_slot_survives_a_signal_that_carries_an_argument(qapp):
    from PyQt5.QtWidgets import QPushButton

    calls = []

    class Widget(QPushButton):
        @error_handling.guard_slot("Pressed", show_dialog=False)
        def on_clicked(self):
            calls.append("pressed")

    button = Widget()
    button.clicked.connect(button.on_clicked)
    button.click()  # clicked(bool) -- one argument the slot does not declare
    assert calls == ["pressed"], "the argument the signal carries broke the slot"


def test_a_guarded_slot_that_wants_the_argument_still_gets_it(qapp):
    from PyQt5.QtWidgets import QComboBox

    seen = []

    class Widget(QComboBox):
        @error_handling.guard_slot("Changed", show_dialog=False)
        def on_index_changed(self, index):
            seen.append(index)

    combo = Widget()
    combo.currentIndexChanged.connect(combo.on_index_changed)
    combo.addItems(["a", "b"])
    combo.setCurrentIndex(1)
    assert seen[-1] == 1


def test_a_guarded_slot_taking_star_args_is_left_alone():
    @error_handling.guard_slot("Anything")
    def takes_everything(*args):
        return args

    assert takes_everything(1, 2, 3) == (1, 2, 3)


# -- coverage of the pattern ------------------------------------------------


def _connected_slot_names(source):
    import re

    return {match.group(1) for match in re.finditer(r"\.connect\(\s*self\.(\w+)", source)}


@pytest.mark.parametrize("module", ["ui/main_window.py", "ui/preferences_window.py"])
def test_every_connected_slot_is_guarded(module, main_window, prefs_window):
    """Partial coverage of this pattern is worse than none.

    A window where most handlers are guarded reads as protected, so the one
    that is not is the one nobody checks -- and it aborts the process exactly
    like an unguarded window would.
    """
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / module).read_text(encoding="utf-8")
    window = main_window if "main_window" in module else prefs_window

    unguarded = []
    for name in sorted(_connected_slot_names(source)):
        slot = getattr(window, name, None)
        if slot is None or not hasattr(slot, "guarded"):
            unguarded.append(name)
    assert not unguarded, f"connected but not wrapped in guard_slot: {unguarded}"

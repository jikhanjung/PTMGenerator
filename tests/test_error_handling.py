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

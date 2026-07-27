"""The <COMMAND,arg> framing the Arduino firmware parses."""

from unittest.mock import MagicMock

import pytest

from core.serial_controller import SerialController

pytestmark = pytest.mark.unit


@pytest.fixture
def controller():
    """A controller with a fake port already open."""
    c = SerialController(port="/dev/ttyFAKE", log=lambda *a: None)
    c._serial = MagicMock()
    return c


def sent(controller):
    return [call.args[0] for call in controller._serial.write.call_args_list]


def test_send_wraps_in_markers(controller):
    controller.send("PING")
    assert sent(controller) == [b"<PING>"]


def test_turn_on_is_one_based_on_the_wire(controller):
    controller.turn_on(0)
    controller.turn_on(49)
    assert sent(controller) == [b"<ON,1>", b"<ON,50>"]


def test_shoot_is_one_based_on_the_wire(controller):
    controller.shoot(4)
    assert sent(controller) == [b"<SHOOT,5>"]


def test_all_off(controller):
    controller.all_off()
    assert sent(controller) == [b"<OFF>"]


def test_close_turns_the_leds_off_first(controller):
    # Held separately: close() drops the controller's reference to the port.
    port = controller._serial
    controller.close()
    assert [call.args[0] for call in port.write.call_args_list] == [b"<OFF>"]
    port.close.assert_called_once_with()


def test_close_releases_the_port(controller):
    controller.close()
    assert not controller.is_open


def test_receive_returns_the_echoed_line(controller):
    controller._serial.readline.return_value = b"Turn on LED #1\n"
    assert controller.receive() == b"Turn on LED #1\n"


# -- with no controller attached -------------------------------------------
#
# openSerial returns without creating a port whenever none is configured, so
# every path has to tolerate that. It used to raise AttributeError instead:
# pressing Stop with no port configured crashed the application.


@pytest.fixture
def portless():
    return SerialController(port=None, log=lambda *a: None)


@pytest.mark.parametrize("port", [None, "", "None"])
def test_open_is_a_no_op_without_a_configured_port(port):
    c = SerialController(port=port, log=lambda *a: None)
    assert c.open() is False
    assert not c.is_open


def test_send_discards_the_message(portless):
    assert portless.send("ON,1") is False


def test_commands_are_safe(portless):
    portless.turn_on(0)
    portless.shoot(0)
    portless.all_off()
    portless.close()


def test_receive_returns_none(portless):
    assert portless.receive() is None


def test_open_is_idempotent(controller, monkeypatch):
    opened = []
    monkeypatch.setattr(
        "core.serial_controller.serial.Serial", lambda *a, **kw: opened.append(a) or MagicMock()
    )
    assert controller.open() is True
    assert opened == [], "an already-open port must not be reopened"

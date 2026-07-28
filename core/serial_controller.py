"""Talking to the Arduino LED-dome controller.

The firmware reads messages framed with angle brackets and split on commas —
`<ON,7>`, `<SHOOT,7>`, `<OFF>` — at 9600 baud, and echoes human-readable status
lines back that nothing parses.

Every method tolerates there being no port. A capture can legitimately be
started with no controller attached (the user is asked first, and may say to go
ahead), and before this was centralised here each call site reached for a
`serial` attribute that openSerial had never assigned.
"""

import time

import serial


class SerialController:
    """The controller's serial port, or the absence of one."""

    BAUD_RATE = 9600
    READ_TIMEOUT = 2
    # The Arduino resets when the port opens; it cannot be talked to until its
    # bootloader has handed over.
    RESET_DELAY = 2

    def __init__(self, port=None, log=print):
        self.port = port
        self._serial = None
        self._log = log
        #: Why the last open() failed, or None. Set when a port is configured
        #: but could not be opened, which the UI reports differently from
        #: there being no port at all.
        self.last_error = None

    @property
    def is_open(self):
        return self._serial is not None

    @property
    def is_configured(self):
        """True when a port name is set, whether or not it can be opened."""
        # QSettings round-trips an unset value as the string "None".
        return self.port not in (None, "", "None")

    def open(self):
        """Open the configured port. Returns True if there is one to talk to.

        Never raises. The port name is stored in preferences, so the
        application will eventually try one that has gone away — the board
        unplugged, the Arduino IDE's serial monitor holding it, a USB port
        re-enumerated to a different number, or the preferences carried to
        another machine. That used to let a SerialException escape into a Qt
        slot, which aborts the process with no message.
        """
        self._log("Opening serial port...")
        self.last_error = None
        # Checked before the port name: once a port is open it stays usable
        # even if the configured name is later cleared in Preferences.
        if self._serial is not None:
            return True
        if not self.is_configured:
            self._log("No serial port configured.")
            return False
        self._log(f"Serial port: {self.port}")
        try:
            self._serial = serial.Serial(self.port, self.BAUD_RATE, timeout=self.READ_TIMEOUT)
        except (serial.SerialException, OSError) as error:
            self.last_error = str(error)
            self._serial = None
            self._log(f"Could not open {self.port}: {error}")
            return False
        time.sleep(self.RESET_DELAY)
        return True

    def close(self):
        """Turn the LEDs off and release the port. Safe when never opened."""
        if self._serial is None:
            return
        self.all_off()
        self._serial.close()
        self._serial = None

    def send(self, message):
        """Frame and write a message. Discarded, with a note, if there is no port."""
        framed = "<" + message + ">"
        if self._serial is None:
            self._log(f"No serial port open, discarding: {framed}")
            return False
        self._log(framed)
        self._serial.write(framed.encode())
        return True

    def receive(self):
        """Read one echoed status line, or None if there is no port."""
        if self._serial is None:
            return None
        line = self._serial.readline()
        self._log(line)
        return line

    # -- the three commands the firmware understands ------------------------

    def turn_on(self, led_index):
        """Light LED `led_index` (0-based here, 1-based on the wire)."""
        return self.send(f"ON,{led_index + 1}")

    def shoot(self, led_index):
        """Light LED `led_index` and fire the shutter."""
        return self.send(f"SHOOT,{led_index + 1}")

    def all_off(self):
        return self.send("OFF")

    @staticmethod
    def available_ports():
        """Device names of the serial ports currently present."""
        import serial.tools.list_ports

        return [p.device for p in serial.tools.list_ports.comports()]

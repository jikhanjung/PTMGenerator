Hardware
========

The controller
--------------

The firmware lives in ``PTMController/PTMController.ino`` and is flashed with the
Arduino IDE. Seven daisy-chained 74HC595 shift registers give 56 outputs, of
which 50 drive the LEDs. The remaining pins run a 7-segment display showing the
current LED index. A rotary encoder with a push button allows manual LED
selection and manual shooting without the PC.

Pinout
------

==========================  ============
Signal                      Arduino pin
==========================  ============
``SER`` (74HC595 pin 14)    8
``RCLK`` (74HC595 pin 12)   9
``SRCLK`` (74HC595 pin 11)  10
Shutter                     19
==========================  ============

Serial protocol
---------------

9600 baud, 8N1. The PC sends messages framed with ``<`` and ``>``, comma
separated:

===============  ==================================================
Message          Effect
===============  ==================================================
``<ON,n>``       Turn on LED *n*, all others off
``<SHOOT,n>``    Turn on LED *n* and trigger the shutter
``<OFF>``        Turn all LEDs off. Sent when the port closes
===============  ==================================================

LED numbers are 1-based on the wire (1–50 for the default configuration) and
0-based in the code; :py:mod:`core.serial_controller` converts between them.

The Arduino echoes human-readable status lines back — ``Turn on LED #n``,
``Shooting with LED #n turned on.`` — which are informational only. The
application does not parse them.

LED geometry
------------

``core/light_positions.py`` holds one ``[elevation, azimuth]`` pair per LED, in
degrees, measured off the physical rig. **The index into that list is the LED
number**, so the table must not be reordered without re-measuring.

``light_vectors()`` converts it to the unit vectors the fitter wants. The
*Light Position Adjustment* preference rotates the whole dome about the vertical
axis, to line LED #1 up with how the specimen is sitting; elevation is
unaffected.

Configuration
=============

Settings are stored with ``QSettings`` under ``PaleoBytes / PTMGenerator2``:

* Windows: ``%APPDATA%\PaleoBytes\PTMGenerator2.ini``
* Linux: ``~/.config/PaleoBytes/PTMGenerator2.ini``

Preferences
-----------

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Setting
     - Default
     - Meaning
   * - Serial Port
     - *(none)*
     - The controller's port. Must be set before capturing; the list is
       populated from the ports present when the dialog opens.
   * - PTM Engine
     - Built-in
     - Which fitter **Generate PTM** uses. **Built-in** fits in the application
       itself and is limited only by memory. **PTMfitter.exe** shells out to the
       external binary, which is 32-bit and fails above roughly 24 megapixels;
       it is kept for comparison against the built-in fitter's output.
   * - PTM Fitter
     - ``ptmfitter.exe``
     - Path to the external fitter. Only used when the engine is set to
       **PTMfitter.exe**, and then **Generate PTM** refuses to run if it is not
       found.
   * - Number of LEDs
     - 50
     - Shots in a full sequence. Must match the dome, and the light-position
       table.
   * - Retry Count
     - 3
     - How many times a slot is re-shot before being recorded as missing.
   * - Post Shutter Polling
     - 1.0
     - Seconds to wait after the shutter before scanning for the new file.
       Increase it if shots are being missed on a slow card or a large RAW.
   * - Light Position Adjustment
     - 0
     - Azimuth offset in degrees, to align the dome's LED #1 with the
       specimen's orientation. Elevation is unaffected.
   * - Language
     - ``en``
     - ``en`` or ``ko``. Takes effect immediately.

Tuning the timing
-----------------

Two settings interact when shots go missing:

*Post Shutter Polling* is a fixed delay before each check. *Retry Count*
determines how many times a slot that timed out is attempted again. If a whole
run comes back empty, the serial port is the likely cause, not the timing —
check that a **Test Shot** produces a file at all.

If shots are missed intermittently, raise *Post Shutter Polling* first: retries
cost a full timeout each, so a longer wait is cheaper than a retry.

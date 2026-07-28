Troubleshooting
===============

No serial port detected
-----------------------

* Check the Arduino is connected and its driver is installed. Install the CH340
  driver if the board is a CH340-based clone.
* Windows: Device Manager. Linux and macOS: ``ls /dev/tty*``.
* The port list is read when the Preferences dialog opens, so plug the
  controller in first, then open Preferences.

Images are not detected
-----------------------

* Raise *Post Shutter Polling*.
* Confirm the tethering software writes into the directory you opened, and not
  into a subdirectory — the poll deliberately does not search recursively.
* Supported extensions are ``.jpg``, ``.jpeg``, ``.png``, ``.gif``, ``.bmp`` and
  ``.tiff``, matched case-insensitively.

Missing images in a sequence
----------------------------

* Gaps are expected to be recorded, not silently dropped: the slot keeps its LED
  index with ``-`` for the filename.
* Select those rows and use **Retake Picture**.
* ``image_data.csv`` shows which positions failed.

PTM generation fails
--------------------

* At least six images are needed: the polynomial has six coefficients.
* Unchecked and missing shots are excluded. If the count is lower than expected,
  check the Include column.
* The ``.lp`` file is written beside the images; open it to check the count line
  and the filenames.
* If the engine is set to *PTMfitter.exe*, check its path in Preferences, and
  note that it fails on images above roughly 24 megapixels — switch *PTM Engine*
  to **Built-in**, which has no such limit.

The interface is in the wrong language
--------------------------------------

Language is applied immediately from Preferences. If a string is still English
in Korean mode, its translation is missing from ``translations/*.qm`` — see the
translation section of :doc:`developer_guide`.

Whole files show as modified in git with no real changes
--------------------------------------------------------

Line endings are normalized by ``.gitattributes``. Run
``git add --renormalize .`` if phantom whole-file diffs appear.

Architecture
============

The boundary
------------

The split that matters is ``core/`` versus ``ui/``. **``core`` imports no
PyQt5**, and ``tests/test_smoke.py`` asserts that in a subprocess so an earlier
test having imported PyQt5 cannot mask a regression.

That boundary is what makes the capture policy, the serial protocol, the dome
geometry and the file formats testable without a display, a QApplication or a
controller. It is also why the suite runs in about a second.

.. code-block:: text

   PTMGenerator2.py     entry point
   version.py           single source of truth for the version
   core/
     serial_controller.py   <ON,n> / <SHOOT,n> / <OFF>, port lifecycle
     capture_session.py     sequencing: preparation, polling, retakes
     light_positions.py     polar LED table -> unit vectors
     image_data.py          capture table, CSV, rebuilding from disk
     ptm_builder.py         .lp generation, PTMfitter invocation
     resources.py           bundled-file lookup, frozen or not
     settings.py            preference keys, defaults, coercion
   ui/
     main_window.py         widgets, the timer, rendering
     preferences_window.py  the settings dialog

The capture loop
----------------

``ui.main_window.take_picture_process`` is the one-second timer tick. It asks
the session what to do and renders the result; it decides nothing itself:

.. code-block:: python

   result = session.step(shoot=self.serial.shoot, poll=self.poll_for_image)

Because the shutter and the file poll are arguments rather than calls into Qt,
a whole 50-slot run — including retakes and timeouts — is driven in
microseconds in the tests with recorders in their place.

.. code-block:: text

   idle ──shoot──▶ preparing ──(N ticks)──▶ polling
                                              │
                       ┌──────────────────────┼──────────────────────┐
                    found                  timeout                timeout
                       │                 retries left            no retries
                       ▼                      │                      │
                 record image                 ▼                      ▼
                       │                    idle                record "-"
                       └───────────────┬────────────────────────────┘
                                       ▼
                            next LED, or finish

The capture table
-----------------

A run is a list of :py:class:`core.image_data.CaptureSlot`, one per LED:

.. code-block:: python

   CaptureSlot(led_index=0, directory="/shots", filename="a.jpg", include=True)
   CaptureSlot(led_index=1, directory="-",      filename="-",     include=False)

It is a ``NamedTuple``, so it compares equal to a plain 4-tuple and unpacks the
way the older code expected.

A failed shot keeps its slot rather than being dropped. That is what keeps
``led_index`` aligned with ``light_vectors()``, so a run with gaps still
produces a correct ``.lp`` — just from fewer images.

The .lp file
------------

.. code-block:: text

   2
   /shots/specimen01/a.jpg 0.4980 0.8627 0.0871
   /shots/specimen01/d.jpg -0.3869 0.9115 0.1391

First line is the count of images that follow. Each row is an absolute path and
the unit vector of the light that was on. Shots that failed, and shots the user
unchecked, appear in neither.

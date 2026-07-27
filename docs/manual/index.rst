PTMGenerator2
=============

Automated Polynomial Texture Mapping capture for an Arduino LED dome.

An Arduino-driven dome lights 50 LEDs one at a time and fires a DSLR shutter for
each. PTMGenerator2 drives that sequence over a serial link, waits for each photo
to land on disk, builds the light-position (``.lp``) file, and hands everything
to PTMfitter to produce the final ``.ptm``.

.. code-block:: text

     PTMGenerator2  ──serial (9600 8N1)──▶  Arduino + 7x 74HC595  ──▶  50 LEDs
           │                                          │
           │                                          └──▶  DSLR shutter
           │
           └── polls the capture directory for the new image file
                                   │
                                   ▼
                      writes <dirname>.lp  ──▶  PTMfitter -i x.lp -o x.ptm

.. toctree::
   :maxdepth: 2
   :caption: User guide

   installation
   hardware
   user_guide
   configuration
   troubleshooting

.. toctree::
   :maxdepth: 2
   :caption: Developer guide

   developer_guide
   architecture
   api
   changelog

Indices
-------

* :ref:`genindex`
* :ref:`modindex`

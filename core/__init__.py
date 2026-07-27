"""Qt-free logic for PTMGenerator2.

Nothing in this package imports PyQt5. That is the point of the boundary: the
capture policy, the serial protocol, the light geometry and the file formats can
all be tested without a display, a QApplication or a controller attached.

The Qt widgets that drive these live in the `ui` package.
"""

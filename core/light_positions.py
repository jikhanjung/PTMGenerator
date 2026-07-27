"""The dome's LED geometry.

PTMfitter wants a unit vector per shot, pointing from the specimen towards the
light that was on. The dome is described in polar coordinates instead — one
[elevation, azimuth] pair per LED, in degrees — so this module is the conversion
between the two.
"""

import math

# One [theta, phi] pair per LED, in degrees, in the order the controller lights
# them. theta is the angle down from vertical, phi the azimuth around the dome.
# Measured from the physical rig; do not reorder without re-measuring, because
# the index into this list *is* the LED number.
POLAR_LIGHT_LIST = [
    [85, 330], [84, 108], [83, 245], [82, 23], [81, 160], [80, 298], [79, 76], [78, 213], [77, 351], [76, 128],
    [75, 266], [74, 43], [73, 181], [71, 318], [70, 96], [69, 233], [68, 11], [67, 148], [66, 286], [65, 63],
    [64, 201], [62, 338], [61, 116], [60, 253], [59, 31], [58, 168], [56, 306], [55, 83], [54, 221], [52, 358],
    [51, 136], [50, 273], [48, 51], [47, 188], [46, 326], [44, 103], [43, 241], [41, 18], [39, 156], [38, 293],
    [36, 71], [34, 208], [32, 346], [30, 123], [28, 261], [26, 38], [23, 176], [21, 313], [17, 91], [13, 228],
]

LED_COUNT = len(POLAR_LIGHT_LIST)


def light_vectors(azimuth_adjustment=0):
    """Convert the polar LED table into unit vectors for the .lp file.

    Args:
        azimuth_adjustment (int): Degrees to rotate the whole dome about the
            vertical axis, to line LED #1 up with how the specimen is sitting.
            Elevation is unaffected.

    Returns:
        list[list[float]]: One [x, y, z] unit vector per LED, in LED order.
    """
    vectors = []
    for theta, phi in POLAR_LIGHT_LIST:
        phi_corrected = phi - 90 + azimuth_adjustment
        x = math.cos(math.radians(phi_corrected - 180)) * math.sin(math.radians(theta))
        y = math.sin(math.radians(phi_corrected - 180)) * math.sin(math.radians(theta))
        z = math.cos(math.radians(theta))
        vectors.append([x, y, z])
    return vectors

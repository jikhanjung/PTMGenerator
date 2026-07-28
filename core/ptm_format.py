"""Reading and writing the PTM 1.2 container.

A PTM stores, per pixel, the coefficients of a biquadratic in the light
direction, so brightness can be re-evaluated for any light:

    L(u, v) = c0*u² + c1*v² + c2*u*v + c3*u + c4*v + c5

`(u, v)` are the first two components of the unit light vector — exactly what
the `.lp` file carries. The `LRGB` variant fits those six to luminance only and
stores an RGB colour per pixel alongside, which is what this module handles.

The layout was established from `cceh/rti`'s `rti-builder` (`ptmlib.c`,
`ptm-encoder.c`) and cross-checked against output from the shipped
`PTMfitter.exe`. See `devlog/20260728_P02_NativePtmFitter.md`.

    PTM_1.2\\n
    PTM_FORMAT_LRGB\\n
    <width>\\n
    <height>\\n
    <6 floats>\\n        scale, one per coefficient
    <6 ints>\\n          bias,  one per coefficient
    <width*height*6 bytes>   coefficients, interleaved per pixel
    <width*height*3 bytes>   RGB, interleaved per pixel

Two things about that are easy to get wrong and produce plausible-looking
output:

* **Rows run bottom to top.** `ptm-encoder.c` flips each source image while
  reading it. This module returns arrays in normal top-down order and does the
  flip at the boundary, so nothing above it has to remember.
* **Coefficients are quantised per coefficient across the whole image**, so
  a byte means nothing without the header's scale and bias for its position.
"""

import numpy as np

VERSION = "PTM_1.2"
FORMAT_LRGB = "PTM_FORMAT_LRGB"

#: Number of polynomial terms, in the order they appear in the file.
COEFFICIENTS = 6

#: What each coefficient multiplies, in file order. Used to build the design
#: matrix, and as documentation of the ordering.
TERM_NAMES = ("u2", "v2", "uv", "u", "v", "1")


class PtmFormatError(Exception):
    """The file is not a PTM this module can read."""


class Ptm:
    """A decoded LRGB PTM.

    Attributes:
        width, height (int): Pixel dimensions.
        scale (np.ndarray): (6,) float, one per coefficient.
        bias (np.ndarray): (6,) int, one per coefficient.
        coefficients (np.ndarray): (height, width, 6) uint8, top row first.
        rgb (np.ndarray): (height, width, 3) uint8, top row first.
    """

    def __init__(self, width, height, scale, bias, coefficients, rgb):
        self.width = width
        self.height = height
        self.scale = np.asarray(scale, dtype=np.float64)
        self.bias = np.asarray(bias, dtype=np.int64)
        self.coefficients = coefficients
        self.rgb = rgb

    def dequantised(self):
        """Coefficients as floats: `(byte - bias) * scale`.

        Returns:
            np.ndarray: (height, width, 6) float64.
        """
        return (self.coefficients.astype(np.float64) - self.bias) * self.scale

    def luminance(self, u, v):
        """Evaluate the polynomial at one light direction.

        Args:
            u, v (float): First two components of a unit light vector.

        Returns:
            np.ndarray: (height, width) float64.
        """
        terms = np.array([u * u, v * v, u * v, u, v, 1.0])
        return self.dequantised() @ terms

    def __eq__(self, other):
        if not isinstance(other, Ptm):
            return NotImplemented
        return (
            self.width == other.width
            and self.height == other.height
            and np.array_equal(self.scale, other.scale)
            and np.array_equal(self.bias, other.bias)
            and np.array_equal(self.coefficients, other.coefficients)
            and np.array_equal(self.rgb, other.rgb)
        )


def _read_token_line(stream, what):
    line = stream.readline()
    if not line:
        raise PtmFormatError(f"file ended where {what} was expected")
    return line.decode("ascii", errors="replace").strip()


def read(path):
    """Parse an uncompressed LRGB PTM.

    Raises:
        PtmFormatError: Not a PTM 1.2, not LRGB, or the payload is short.
    """
    with open(path, "rb") as fh:
        version = _read_token_line(fh, "the version")
        if version != VERSION:
            raise PtmFormatError(f"not a {VERSION} file: {version!r}")

        image_format = _read_token_line(fh, "the format")
        if image_format != FORMAT_LRGB:
            # The compressed variants exist; nothing here produces or needs
            # them, and a clear refusal beats a confusing misparse.
            raise PtmFormatError(f"only {FORMAT_LRGB} is supported, not {image_format!r}")

        width = int(_read_token_line(fh, "the width"))
        height = int(_read_token_line(fh, "the height"))
        scale = [float(x) for x in _read_token_line(fh, "the scales").split()]
        bias = [int(x) for x in _read_token_line(fh, "the biases").split()]
        if len(scale) != COEFFICIENTS or len(bias) != COEFFICIENTS:
            raise PtmFormatError(
                f"expected {COEFFICIENTS} scales and biases, got {len(scale)} and {len(bias)}"
            )

        pixels = width * height
        payload = fh.read()

    expected = pixels * (COEFFICIENTS + 3)
    if len(payload) < expected:
        raise PtmFormatError(
            f"payload is {len(payload)} bytes, expected {expected} for {width}x{height}"
        )

    coefficients = np.frombuffer(payload[: pixels * COEFFICIENTS], dtype=np.uint8)
    rgb = np.frombuffer(payload[pixels * COEFFICIENTS : expected], dtype=np.uint8)
    # Stored bottom row first; hand back the usual orientation.
    coefficients = coefficients.reshape(height, width, COEFFICIENTS)[::-1]
    rgb = rgb.reshape(height, width, 3)[::-1]
    return Ptm(width, height, scale, bias, coefficients, rgb)


def write(path, ptm):
    """Write an uncompressed LRGB PTM.

    `ptm.coefficients` and `ptm.rgb` are top row first, as `read` returns them;
    the flip back to the file's bottom-up order happens here.
    """
    scales = " ".join(f"{s:.6f}" for s in ptm.scale)
    biases = " ".join(str(int(b)) for b in ptm.bias)
    header = f"{VERSION}\n{FORMAT_LRGB}\n{ptm.width}\n{ptm.height}\n{scales} \n{biases} \n"
    with open(path, "wb") as fh:
        fh.write(header.encode("ascii"))
        fh.write(np.ascontiguousarray(ptm.coefficients[::-1]).tobytes())
        fh.write(np.ascontiguousarray(ptm.rgb[::-1]).tobytes())


def quantise(coefficients):
    """Map float coefficients onto bytes, deriving the scale and bias.

    Follows `ptm_scale_coefficients` in rti-builder: the range of each
    coefficient across the *whole image* sets its scale and bias.

    Args:
        coefficients (np.ndarray): (height, width, 6) float.

    Returns:
        tuple: (bytes (h, w, 6) uint8, scale (6,) float, bias (6,) int)
    """
    flat = coefficients.reshape(-1, COEFFICIENTS)
    minimum = flat.min(axis=0)
    maximum = flat.max(axis=0)
    spread = maximum - minimum

    # A coefficient that is constant over the image has no range to map. The
    # reference divides by zero here; PTMfitter emits a scale of 1 and a bias
    # of 0 for such a plane, which round-trips the value unchanged.
    degenerate = spread == 0
    scale = np.where(degenerate, 1.0, spread / 256.0)
    bias = np.where(degenerate, 0.0, -256.0 / np.where(degenerate, 1.0, spread) * minimum)
    bias = np.rint(bias).astype(np.int64)

    quantised = np.rint(coefficients / scale + bias)
    return np.clip(quantised, 0, 255).astype(np.uint8), scale, bias

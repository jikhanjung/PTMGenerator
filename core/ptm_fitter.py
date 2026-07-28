"""Fitting a PTM from a set of images and their light directions.

This replaces `PTMfitter.exe`, which is a 32-bit binary and fails above about
24 megapixels — see `devlog/20260728_P02_NativePtmFitter.md`.

The algorithm follows `cceh/rti`'s `rti-builder`, which is readable and
therefore serves as the specification:

* luminance is a plain unweighted ``R + G + B``;
* the biquadratic is fitted to luminance by least squares;
* the RGB stored per pixel is the average colour across the images, divided by
  that pixel's luminance so the two multiply back together.

The fit itself is one matrix multiplication. The light directions are the same
for every pixel, so the design matrix and its pseudo-inverse are built once and
applied to the whole image at once — which numpy hands to BLAS, the same
library `rti-builder` reaches for through `cblas_sgemv`.

`fit` holds every image at once and is for small sets and for testing.
`fit_streaming` is what a real capture goes through: it never holds more than
one image, because

    coefficients = solver @ L = Σᵢ outer(solver[:, i], L[i])

decomposes into one rank-1 update per image. That is worth more than the
horizontal banding originally planned: banding bounds memory but re-decodes
every image once per band, and decoding is about 96% of the runtime (see
`devlog/20260728_P02_NativePtmFitter.md`). Streaming bounds memory *and*
decodes each image exactly once.
"""

import numpy as np

from core.ptm_format import COEFFICIENTS, Ptm, quantise, quantise_planes


class FitError(Exception):
    """The images cannot be fitted."""


def design_matrix(light_directions):
    """Rows of ``[u², v², uv, u, v, 1]``, one per light.

    The column order is the order the coefficients appear in the file; see
    `core.ptm_format.TERM_NAMES`.

    Args:
        light_directions: (N, 2) or (N, 3) array. Only u and v are used — the
            third component is determined by the first two on a unit vector,
            and the polynomial is in u and v alone.

    Returns:
        np.ndarray: (N, 6) float64.
    """
    lights = np.asarray(light_directions, dtype=np.float64)
    if lights.ndim != 2 or lights.shape[1] < 2:
        raise FitError(f"expected an (N, 2) or (N, 3) array of lights, got {lights.shape}")
    u, v = lights[:, 0], lights[:, 1]
    return np.column_stack([u * u, v * v, u * v, u, v, np.ones_like(u)])


def fit_luminance(luminance, light_directions):
    """Least-squares fit of the biquadratic, for every pixel at once.

    Args:
        luminance (np.ndarray): (N, pixels) — one row per image.
        light_directions: (N, 2 or 3) light vectors, in the same order.

    Returns:
        np.ndarray: (pixels, 6) float64 coefficients.
    """
    lights = np.asarray(light_directions, dtype=np.float64)
    luminance = np.asarray(luminance, dtype=np.float64)
    if luminance.shape[0] != lights.shape[0]:
        raise FitError(f"{luminance.shape[0]} images but {lights.shape[0]} light directions")
    if luminance.shape[0] < COEFFICIENTS:
        raise FitError(
            f"a biquadratic needs at least {COEFFICIENTS} images, got {luminance.shape[0]}"
        )

    # Computed once for the whole image, because every pixel shares the lights.
    solver = np.linalg.pinv(design_matrix(lights))  # (6, N)
    return (solver @ luminance).T  # (pixels, 6)


def fit(images, light_directions):
    """Fit a PTM from decoded images.

    Args:
        images (np.ndarray): (N, height, width, 3) uint8, top row first.
        light_directions: (N, 2 or 3) unit light vectors, same order.

    Returns:
        Ptm: ready to write.

    Raises:
        FitError: Too few images, or shapes that do not line up.
    """
    images = np.asarray(images)
    if images.ndim != 4 or images.shape[3] != 3:
        raise FitError(f"expected (N, height, width, 3) images, got {images.shape}")
    count, height, width, _ = images.shape
    pixels = height * width

    # L = R + G + B, unweighted. int32 so the sum of three bytes cannot wrap.
    luminance = images.reshape(count, pixels, 3).sum(axis=2, dtype=np.int32)

    coefficients = fit_luminance(luminance, light_directions)

    # The colour is the average across images, divided by the luminance so that
    # colour x luminance recovers the pixel. Guard the division: a pixel that is
    # black in every image has no colour to preserve.
    mean_rgb = images.reshape(count, pixels, 3).mean(axis=0)
    mean_luminance = luminance.mean(axis=0)
    safe = np.where(mean_luminance == 0, 1.0, mean_luminance)
    rgb = np.clip(np.rint(255.0 * mean_rgb / safe[:, None]), 0, 255).astype(np.uint8)

    quantised, scale, bias = quantise(coefficients.reshape(height, width, COEFFICIENTS))
    return Ptm(width, height, scale, bias, quantised, rgb.reshape(height, width, 3))


def reconstruct(ptm, u, v):
    """Re-render the surface under one light, as a viewer would.

    Args:
        ptm (Ptm): The fitted map.
        u, v (float): First two components of a unit light vector.

    Returns:
        np.ndarray: (height, width, 3) float64, in the same units as the
        source images.
    """
    luminance = ptm.luminance(u, v)
    return ptm.rgb.astype(np.float64) * (luminance[:, :, None] / 255.0)


#: Full-resolution buffers `fit_streaming` holds, by element size.
#: float: 6 coefficient planes, 3 colour planes, and 2 scratch rows.
#: byte:  the 6-plane quantised output, the 3-channel result, and one image.
_FLOAT_PLANES = COEFFICIENTS + 3 + 2
_BYTE_PLANES = COEFFICIENTS + 3 + 3


def memory_estimate(width, height, dtype=np.float32):
    """Bytes `fit_streaming` holds at its peak, excluding the decoder.

    Counted from the buffers it actually allocates rather than the ones it
    conceptually needs — an earlier version of this function omitted the
    scratch rows and the output arrays and came out at half the measured
    figure, which is worse than not estimating at all.
    """
    pixels = width * height
    return pixels * (_FLOAT_PLANES * np.dtype(dtype).itemsize + _BYTE_PLANES)


def fit_streaming(loader, light_directions, count=None, dtype=np.float32, progress=None):
    """Fit without ever holding more than one image.

    Args:
        loader: An iterable of (height, width, 3) uint8 arrays, or a callable
            taking an index and returning one. Images arrive in the same order
            as `light_directions`.
        light_directions: (N, 2 or 3) unit light vectors.
        count (int | None): Number of images, when `loader` is a callable.
        dtype: Accumulator precision. float32 halves the memory against float64
            and is ample for 8-bit input — the fit is over at most a few hundred
            values per pixel, each under 766.
        progress: Optional callable, `progress(index, count)`, after each image.

    Returns:
        Ptm: ready to write.

    Raises:
        FitError: Too few images, or an image whose shape does not match the
            first one.
    """
    lights = np.asarray(light_directions, dtype=np.float64)
    if callable(loader):
        if count is None:
            raise FitError("count is required when loader is a callable")
        images = iter(loader(i) for i in range(count))
    else:
        images = iter(loader)
        count = len(lights)

    if count != len(lights):
        raise FitError(f"{count} images but {len(lights)} light directions")
    if count < COEFFICIENTS:
        raise FitError(f"a biquadratic needs at least {COEFFICIENTS} images, got {count}")

    # (6, N): column i is this image's contribution to every coefficient.
    solver = np.linalg.pinv(design_matrix(lights)).astype(dtype)

    try:
        first = _validated_image(next(images), 0)
    except StopIteration:
        raise FitError("no images were supplied") from None

    # Allocated from the first image rather than lazily inside the loop, so
    # every buffer below is an array and not "an array once we have seen one".
    shape = first.shape
    height, width, _ = shape
    pixels = height * width
    coefficients = np.zeros((COEFFICIENTS, pixels), dtype=dtype)
    colour_sum = np.zeros((3, pixels), dtype=dtype)
    # Reused every iteration. Without these the loop allocates a
    # full-resolution temporary per image per operation, which at 48MP dwarfs
    # the accumulators it is supposed to be avoiding.
    luminance = np.empty(pixels, dtype=dtype)
    scratch = np.empty(pixels, dtype=dtype)

    def absorb(image, index):
        """Fold one image into the accumulators."""
        channels = image.reshape(-1, 3).T  # (3, pixels), a view

        # L = R + G + B, into the reused buffer.
        np.add(channels[0], channels[1], out=luminance, dtype=dtype)
        np.add(luminance, channels[2], out=luminance)

        # The rank-1 update, one coefficient at a time so the (6, pixels)
        # product is never materialised.
        for k in range(COEFFICIENTS):
            np.multiply(luminance, solver[k, index], out=scratch)
            coefficients[k] += scratch

        for channel in range(3):
            colour_sum[channel] += channels[channel]

        if progress is not None:
            progress(index + 1, count)

    absorb(first, 0)
    del first

    # Pulled explicitly rather than with `for ... in`, so the previous image is
    # released *before* the next is fetched. A plain for-loop keeps the last one
    # bound while the loader produces the next, leaving two resident at the
    # peak -- 288 MB of them at 48 megapixels.
    index = 0
    while True:
        try:
            image = next(images)
        except StopIteration:
            break
        index += 1
        image = _validated_image(image, index, shape)
        absorb(image, index)
        del image

    return _assemble(coefficients, colour_sum, scratch, width, height)


def _validated_image(value, index, expected=None):
    """Check one image's shape, and that it matches the set."""
    array = np.asarray(value)
    if array.ndim != 3 or array.shape[2] != 3:
        raise FitError(f"image {index} is {array.shape}, expected (height, width, 3)")
    if expected is not None and array.shape != expected:
        raise FitError(f"image {index} is {array.shape}, but the first was {expected}")
    return array


def _assemble(coefficients, colour_sum, scratch, width, height):
    """Turn the accumulators into a Ptm, reusing their storage throughout.

    Everything here is in place. At 48 megapixels each of these arrays is
    hundreds of megabytes, and a single incautious expression would allocate
    another copy of one.
    """
    # The summed luminance is the summed colour added up, so it never needed
    # its own accumulator. Reuses `scratch`, which is finished with.
    np.add(colour_sum[0], colour_sum[1], out=scratch)
    scratch += colour_sum[2]
    scratch[scratch == 0] = 1.0  # a pixel black in every image has no colour

    # In place: the ratio is all that is wanted from colour_sum.
    for channel in range(3):
        colour_sum[channel] *= 255.0
        colour_sum[channel] /= scratch
    np.clip(colour_sum, 0, 255, out=colour_sum)
    np.rint(colour_sum, out=colour_sum)
    rgb = colour_sum.T.astype(np.uint8)

    # Quantised in place, in the (6, pixels) layout it was accumulated in.
    # Transposing to (h, w, 6) first would copy the whole array, and quantising
    # it whole would allocate several more copies on top.
    planes, scale, bias = quantise_planes(coefficients)
    quantised = planes.T.reshape(height, width, COEFFICIENTS)
    return Ptm(width, height, scale, bias, quantised, rgb.reshape(height, width, 3))

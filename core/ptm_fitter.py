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
"""

import numpy as np

from core.ptm_format import COEFFICIENTS, Ptm, quantise


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

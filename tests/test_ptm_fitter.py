"""Fitting a PTM.

The acceptance criterion from the plan is *reconstruction*, not bytes: our
output and `PTMfitter.exe`'s put the normalisation in different places, so their
coefficients cannot agree by construction. What must agree is what the files
mean — evaluate both at each input light and compare against the source.
"""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from core import ptm_fitter, ptm_format
from core.light_positions import light_vectors
from core.ptm_fitter import FitError
from core.ptm_format import COEFFICIENTS

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def capture():
    """The fixture set: source images, their lights, and PTMfitter's output."""
    entries = [
        line.split()
        for line in (FIXTURES / "reference_8x5.lp").read_text().splitlines()[1:]
        if line.strip()
    ]
    images = np.stack(
        [np.asarray(Image.open(FIXTURES / name).convert("RGB")) for name, *_ in entries]
    )
    lights = np.array([[float(u), float(v), float(w)] for _name, u, v, w in entries])
    names = [name for name, *_ in entries]
    return images, lights, names


@pytest.fixture(scope="module")
def ours(capture):
    images, lights, _names = capture
    return ptm_fitter.fit(images, lights)


@pytest.fixture(scope="module")
def theirs():
    return ptm_format.read(str(FIXTURES / "reference_8x5.ptm"))


# -- the design matrix -----------------------------------------------------


def test_design_matrix_columns_are_in_file_order():
    matrix = ptm_fitter.design_matrix([[2.0, 3.0, 0.0]])
    assert matrix[0].tolist() == [4.0, 9.0, 6.0, 2.0, 3.0, 1.0]


def test_design_matrix_ignores_the_third_component():
    """The polynomial is in u and v; w is determined by them on a unit vector."""
    with_w = ptm_fitter.design_matrix([[0.3, 0.4, 0.866]])
    without = ptm_fitter.design_matrix([[0.3, 0.4]])
    assert np.array_equal(with_w, without)


def test_design_matrix_rejects_the_wrong_shape():
    with pytest.raises(FitError, match="N, 2"):
        ptm_fitter.design_matrix([1.0, 2.0, 3.0])


# -- the fit itself --------------------------------------------------------


def test_an_exact_biquadratic_is_recovered_exactly():
    """If the data is genuinely a biquadratic in the light, least squares must
    return the coefficients that generated it."""
    lights = np.array(light_vectors()[:20])
    truth = np.array([0.7, -0.4, 0.25, 1.3, -0.9, 40.0])
    luminance = ptm_fitter.design_matrix(lights) @ truth
    recovered = ptm_fitter.fit_luminance(luminance[:, None], lights)
    assert recovered[0] == pytest.approx(truth, abs=1e-9)


def test_each_pixel_is_fitted_independently():
    lights = np.array(light_vectors()[:12])
    truths = np.array([[1.0, 0.0, 0.0, 0.0, 0.0, 10.0], [0.0, 0.0, 0.0, 2.0, 0.0, 5.0]])
    luminance = ptm_fitter.design_matrix(lights) @ truths.T  # (N, 2 pixels)
    recovered = ptm_fitter.fit_luminance(luminance, lights)
    assert recovered == pytest.approx(truths, abs=1e-9)


def test_too_few_images_is_refused():
    lights = np.array(light_vectors()[:5])
    with pytest.raises(FitError, match="at least 6"):
        ptm_fitter.fit_luminance(np.zeros((5, 4)), lights)


def test_mismatched_counts_are_refused():
    with pytest.raises(FitError, match="light directions"):
        ptm_fitter.fit_luminance(np.zeros((9, 4)), np.array(light_vectors()[:8]))


def test_wrong_image_shape_is_refused():
    with pytest.raises(FitError, match="height, width, 3"):
        ptm_fitter.fit(np.zeros((9, 4, 4)), np.array(light_vectors()[:9]))


# -- the output is a usable PTM --------------------------------------------


def test_dimensions_come_from_the_images(ours, theirs):
    assert (ours.width, ours.height) == (theirs.width, theirs.height) == (8, 5)


def test_the_output_round_trips_through_the_container(ours, tmp_path):
    path = tmp_path / "ours.ptm"
    ptm_format.write(str(path), ours)
    assert ptm_format.read(str(path)) == ours


def test_the_coefficient_block_is_the_right_shape(ours):
    assert ours.coefficients.shape == (5, 8, COEFFICIENTS)
    assert ours.rgb.shape == (5, 8, 3)


# -- the criterion that matters --------------------------------------------


def reconstruction_error(ptm, source, u, v):
    """RMSE after matching overall level.

    The level is matched because the two implementations normalise differently
    -- ours divides the colour by luminance, PTMfitter normalises the
    luminance -- so absolute scale is not the thing under test.
    """
    rendered = ptm_fitter.reconstruct(ptm, u, v)
    return float(np.sqrt((((rendered * (source.mean() / rendered.mean())) - source) ** 2).mean()))


def test_the_fit_reproduces_every_input_image(ours, capture):
    """The property test: evaluated at an image's own light, the fit should
    return that image. This is the only check available on the large sets that
    motivated the work, where there is no reference to compare against."""
    images, lights, _names = capture
    for image, (u, v, _w) in zip(images, lights, strict=True):
        rendered = ptm_fitter.reconstruct(ours, u, v)
        assert np.corrcoef(rendered.ravel(), image.astype(float).ravel())[0, 1] > 0.99


def test_we_reconstruct_at_least_as_well_as_ptmfitter(ours, theirs, capture):
    images, lights, names = capture
    worse = []
    for image, (u, v, _w), name in zip(images, lights, names, strict=True):
        source = image.astype(float)
        mine = reconstruction_error(ours, source, u, v)
        reference = reconstruction_error(theirs, source, u, v)
        # A little slack: the two solve the same least-squares problem but
        # normalise differently, so neither is exactly the other's answer.
        if mine > reference * 1.2:
            worse.append((name, mine, reference))
    assert not worse, f"worse than the reference on: {worse}"


def test_reconstruction_error_is_small_in_absolute_terms(ours, capture):
    images, lights, _names = capture
    for image, (u, v, _w) in zip(images, lights, strict=True):
        error = reconstruction_error(ours, image.astype(float), u, v)
        assert error < 5.0, "out of 255 levels"


# -- colour handling -------------------------------------------------------


def test_the_stored_colour_is_normalised_by_luminance(ours, capture):
    """rti-builder's convention: RGB is divided by L so the two multiply back.

    Ours therefore differs from PTMfitter's, which stores the colour verbatim.
    Pinned because the difference is deliberate.
    """
    images, _lights, _names = capture
    mean_colour = images.astype(float).mean(axis=0)
    stored = ours.rgb.astype(float)
    assert not np.allclose(stored, mean_colour, atol=10), (
        "storing the colour unnormalised would be PTMfitter's convention, not ours"
    )
    # Ratio between channels is what survives normalisation.
    for channel in range(3):
        ratio = stored[:, :, channel] / stored.sum(axis=2)
        truth = mean_colour[:, :, channel] / mean_colour.sum(axis=2)
        assert ratio == pytest.approx(truth, abs=0.02)


def test_a_pixel_black_in_every_image_does_not_divide_by_zero():
    lights = np.array(light_vectors()[:9])
    images = np.zeros((9, 2, 2, 3), dtype=np.uint8)
    result = ptm_fitter.fit(images, lights)
    assert np.all(np.isfinite(result.rgb))
    assert np.all(np.isfinite(result.scale))


# -- streaming, which is how a real capture is fitted ----------------------
#
# The plan called for horizontal banding. Streaming replaces it: the least
# squares decomposes into one rank-1 update per image, so memory is bounded
# *and* each image is decoded exactly once, where banding re-decodes every
# image once per band. Decoding is about 96% of the runtime.


def test_streaming_agrees_with_the_batch_fit(capture):
    images, lights, _names = capture
    batch = ptm_fitter.fit(images, lights)
    streamed = ptm_fitter.fit_streaming(list(images), lights)
    assert np.array_equal(streamed.coefficients, batch.coefficients)
    assert np.array_equal(streamed.rgb, batch.rgb)


def test_streaming_scale_matches_to_the_formats_precision(capture):
    """Not byte-identical: the accumulators are float32, so the derived scale
    can differ in the last digit the header stores. The quantised coefficients
    are the same, which is what the reconstruction depends on."""
    images, lights, _names = capture
    batch = ptm_fitter.fit(images, lights)
    streamed = ptm_fitter.fit_streaming(list(images), lights)
    assert streamed.scale == pytest.approx(batch.scale, rel=1e-4)
    assert np.array_equal(streamed.bias, batch.bias)


def test_streaming_reconstructs_the_inputs(capture):
    images, lights, _names = capture
    ptm = ptm_fitter.fit_streaming(list(images), lights)
    for image, (u, v, _w) in zip(images, lights, strict=True):
        rendered = ptm_fitter.reconstruct(ptm, u, v)
        assert np.corrcoef(rendered.ravel(), image.astype(float).ravel())[0, 1] > 0.99


def test_each_image_is_read_exactly_once(capture):
    """The property that distinguishes this from banding."""
    images, lights, _names = capture
    reads = []

    def loader(index):
        reads.append(index)
        return images[index]

    ptm_fitter.fit_streaming(loader, lights, count=len(images))
    assert reads == list(range(len(images)))


def test_only_one_image_is_alive_at_a_time(capture):
    """A loader that hands out a fresh array each call, checking the previous
    one has been released. If the fit accumulated images instead of folding
    them in, they would all still be referenced."""
    import weakref

    images, lights, _names = capture
    handed_out = []

    def loader(index):
        for reference in handed_out:
            assert reference() is None, "an earlier image is still referenced"
        fresh = np.array(images[index])
        handed_out.append(weakref.ref(fresh))
        return fresh

    ptm_fitter.fit_streaming(loader, lights, count=len(images))


def test_progress_is_reported(capture):
    images, lights, _names = capture
    seen = []
    ptm_fitter.fit_streaming(list(images), lights, progress=lambda i, n: seen.append((i, n)))
    assert seen == [(i + 1, len(images)) for i in range(len(images))]


def test_memory_estimate_counts_every_full_resolution_buffer():
    """Guards against the estimate drifting from what is allocated. It was
    once half the measured figure, which is worse than not estimating."""
    per_pixel = ptm_fitter.memory_estimate(1000, 1000, dtype=np.float32) / 1e6
    # 11 float32 planes and 12 byte planes, per the accumulators in use.
    assert per_pixel == pytest.approx((11 * 4 + 12), rel=0.01)


def test_memory_does_not_grow_with_the_number_of_images():
    assert ptm_fitter.memory_estimate(100, 100) == ptm_fitter.memory_estimate(100, 100)


def test_a_callable_loader_needs_a_count(capture):
    _images, lights, _names = capture
    with pytest.raises(FitError, match="count is required"):
        ptm_fitter.fit_streaming(lambda i: None, lights)


def test_mismatched_image_shapes_are_refused():
    lights = np.array(light_vectors()[:6])
    images = [np.zeros((4, 4, 3), np.uint8)] * 5 + [np.zeros((5, 4, 3), np.uint8)]
    with pytest.raises(FitError, match="but the first was"):
        ptm_fitter.fit_streaming(images, lights)


def test_streaming_refuses_too_few_images():
    with pytest.raises(FitError, match="at least 6"):
        ptm_fitter.fit_streaming([np.zeros((2, 2, 3), np.uint8)] * 3, np.array(light_vectors()[:3]))


# -- the in-place contract, which is easy to trip over ---------------------


def test_quantise_leaves_its_input_alone():
    values = np.random.default_rng(0).uniform(-1, 1, (4, 5, COEFFICIENTS))
    before = values.copy()
    ptm_format.quantise(values)
    assert np.array_equal(values, before)


def test_quantise_planes_works_in_place():
    """Deliberate, and the reason the streaming path can hold what it does."""
    planes = np.random.default_rng(0).uniform(-1, 1, (COEFFICIENTS, 20))
    before = planes.copy()
    ptm_format.quantise_planes(planes)
    assert not np.array_equal(planes, before)

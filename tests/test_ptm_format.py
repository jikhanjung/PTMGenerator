"""Reading and writing the PTM container.

Checked against `tests/fixtures/reference_8x5.ptm`, which the shipped
`PTMfitter.exe` produced from the twelve JPEGs beside it. That fixture is the
whole point of these tests: the format was established by reading
`rti-builder`, and this is what confirms the reading was right.
"""

import numpy as np
import pytest
from PIL import Image

from core import ptm_format
from core.ptm_format import COEFFICIENTS, Ptm, PtmFormatError

pytestmark = pytest.mark.unit

FIXTURES = pytest.importorskip("pathlib").Path(__file__).parent / "fixtures"
REFERENCE = FIXTURES / "reference_8x5.ptm"


@pytest.fixture(scope="module")
def reference():
    return ptm_format.read(str(REFERENCE))


@pytest.fixture(scope="module")
def lights():
    """The .lp entries the fixture was fitted from: (filename, u, v)."""
    text = (FIXTURES / "reference_8x5.lp").read_text()
    return [
        (parts[0], float(parts[1]), float(parts[2]))
        for parts in (line.split() for line in text.splitlines()[1:])
        if parts
    ]


# -- parsing ---------------------------------------------------------------


def test_dimensions(reference):
    assert (reference.width, reference.height) == (8, 5)


def test_arrays_have_the_documented_shapes(reference):
    assert reference.coefficients.shape == (5, 8, COEFFICIENTS)
    assert reference.rgb.shape == (5, 8, 3)


def test_scale_and_bias_are_per_coefficient(reference):
    assert len(reference.scale) == COEFFICIENTS
    assert len(reference.bias) == COEFFICIENTS


def test_dequantised_applies_scale_and_bias(reference):
    manual = (reference.coefficients.astype(float) - reference.bias) * reference.scale
    assert np.array_equal(reference.dequantised(), manual)


# -- the orientation, which is the easiest thing to get wrong --------------


def test_rows_are_returned_top_down(reference, lights):
    """PTM stores rows bottom-up; a reader that forgets produces a plausible
    but vertically mirrored image, which no dimension check would catch."""
    name, _u, _v = lights[0]
    source = np.asarray(Image.open(FIXTURES / name).convert("RGB"), dtype=float)
    stored = reference.rgb.astype(float)

    right_way = np.corrcoef(stored.ravel(), source.ravel())[0, 1]
    upside_down = np.corrcoef(stored[::-1].ravel(), source.ravel())[0, 1]
    assert right_way > 0.99
    assert upside_down < 0.5, "the flip is not actually being exercised"


def test_row_means_line_up_with_the_source(reference, lights):
    name, _u, _v = lights[0]
    source = np.asarray(Image.open(FIXTURES / name).convert("RGB"), dtype=float)
    assert reference.rgb[:, :, 0].mean(axis=1) == pytest.approx(
        source[:, :, 0].mean(axis=1), abs=2.0
    )


# -- what the file means ---------------------------------------------------


def test_the_rgb_block_is_the_source_colour(reference, lights):
    """PTMfitter stores the colour unmodulated and normalises the luminance --
    established by probing it; see devlog P02."""
    name, _u, _v = lights[0]
    source = np.asarray(Image.open(FIXTURES / name).convert("RGB"), dtype=float)
    assert np.corrcoef(reference.rgb.astype(float).ravel(), source.ravel())[0, 1] > 0.999


def test_luminance_is_normalised_per_pixel(reference, lights):
    """The polynomial carries the light-direction shape, not the magnitude.

    Pinned because it is surprising, and because a fitter of our own that
    forgot to normalise would still look plausible on a single image.
    """
    _name, u, v = lights[0]
    evaluated = reference.luminance(u, v)
    assert evaluated.std() < 5.0, "luminance should be near-flat across pixels"


def test_reconstruction_tracks_the_source_across_lights(reference, lights):
    """Evaluated at each input light, the fit reproduces that image's
    brightness up to the constant the normalisation introduces."""
    ratios = []
    for name, u, v in lights:
        source = np.asarray(Image.open(FIXTURES / name).convert("RGB"), dtype=float)
        ratios.append(source.sum(axis=2).mean() / reference.luminance(u, v).mean())
    ratios = np.array(ratios)
    assert ratios.std() / ratios.mean() < 0.02, (
        "the ratio should be constant; if it is not, the light-direction "
        "dependence is being read wrongly"
    )


def test_colour_reconstruction(reference, lights):
    name, u, v = lights[0]
    source = np.asarray(Image.open(FIXTURES / name).convert("RGB"), dtype=float)
    recovered = reference.rgb.astype(float) * (reference.luminance(u, v)[:, :, None] / 255.0)
    assert np.corrcoef(recovered.ravel(), source.ravel())[0, 1] > 0.999


# -- round trip ------------------------------------------------------------


def test_write_then_read_is_identical(reference, tmp_path):
    path = tmp_path / "out.ptm"
    ptm_format.write(str(path), reference)
    assert ptm_format.read(str(path)) == reference


def test_written_bytes_match_the_reference(reference, tmp_path):
    """Not required by the plan, but true here, and a sharp regression test."""
    path = tmp_path / "out.ptm"
    ptm_format.write(str(path), reference)
    assert path.read_bytes() == REFERENCE.read_bytes()


# -- refusals --------------------------------------------------------------


def test_a_non_ptm_is_refused(tmp_path):
    path = tmp_path / "x.ptm"
    path.write_bytes(b"not a ptm\n")
    with pytest.raises(PtmFormatError, match=r"PTM_1\.2"):
        ptm_format.read(str(path))


def test_a_compressed_variant_is_refused(tmp_path):
    path = tmp_path / "x.ptm"
    path.write_bytes(b"PTM_1.2\nPTM_FORMAT_JPEG_LRGB\n1\n1\n")
    with pytest.raises(PtmFormatError, match="LRGB"):
        ptm_format.read(str(path))


def test_a_truncated_payload_is_refused(tmp_path):
    path = tmp_path / "x.ptm"
    path.write_bytes(b"PTM_1.2\nPTM_FORMAT_LRGB\n4\n4\n1 1 1 1 1 1 \n0 0 0 0 0 0 \n" + b"\x00" * 10)
    with pytest.raises(PtmFormatError, match="payload"):
        ptm_format.read(str(path))


def test_a_short_scale_line_is_refused(tmp_path):
    path = tmp_path / "x.ptm"
    path.write_bytes(b"PTM_1.2\nPTM_FORMAT_LRGB\n1\n1\n1 1 1 \n0 0 0 0 0 0 \n")
    with pytest.raises(PtmFormatError, match="scales and biases"):
        ptm_format.read(str(path))


# -- quantisation ----------------------------------------------------------


def test_quantise_round_trips_within_a_step():
    """Compared per coefficient, because each has its own scale.

    The bound is 1.5 steps rather than 0.5: the file stores bias as an integer,
    so rounding it shifts the whole grid for that coefficient by up to half a
    step on top of the rounding of the value itself. That is inherent to the
    format, not slack in the implementation.
    """
    rng = np.random.default_rng(0)
    values = rng.uniform(-3, 5, size=(4, 6, COEFFICIENTS))
    quantised, scale, bias = ptm_format.quantise(values)
    recovered = (quantised.astype(float) - bias) * scale
    worst = np.abs(recovered - values).reshape(-1, COEFFICIENTS).max(axis=0)
    assert np.all(worst < 1.5 * scale), dict(zip(ptm_format.TERM_NAMES, worst / scale, strict=True))


def test_quantise_uses_the_whole_byte_range():
    values = np.linspace(0, 1, 256 * COEFFICIENTS).reshape(-1, 1, COEFFICIENTS)
    quantised, _scale, _bias = ptm_format.quantise(values)
    assert quantised.min() == 0
    assert quantised.max() == 255


def test_a_constant_coefficient_does_not_divide_by_zero():
    """rti-builder's formula divides by (max - min); PTMfitter emits scale 1,
    bias 0 for such a plane, which round-trips the value unchanged."""
    values = np.full((3, 3, COEFFICIENTS), 7.0)
    quantised, scale, bias = ptm_format.quantise(values)
    assert np.all(np.isfinite(scale))
    recovered = (quantised.astype(float) - bias) * scale
    assert recovered == pytest.approx(values)


def test_quantised_output_is_a_valid_ptm(tmp_path):
    rng = np.random.default_rng(1)
    values = rng.uniform(-1, 1, size=(5, 8, COEFFICIENTS))
    quantised, scale, bias = ptm_format.quantise(values)
    rgb = rng.integers(0, 256, size=(5, 8, 3), dtype=np.uint8)
    path = tmp_path / "made.ptm"
    ptm_format.write(str(path), Ptm(8, 5, scale, bias, quantised, rgb))
    assert ptm_format.read(str(path)).coefficients.shape == (5, 8, COEFFICIENTS)

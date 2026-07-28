"""The .lp file and the PTMfitter invocation.

Everything here is about keeping the fitter's input plain — see the module
docstring in core/ptm_builder.py for the measured constraints. The rules that
matter: filenames only in the .lp, ASCII, no whitespace.
"""

import os
import pathlib
from unittest.mock import MagicMock

import pytest

from core.image_data import MISSING, CaptureSlot
from core.light_positions import light_vectors
from core.ptm_builder import (
    STAGED_LP,
    STAGED_PTM,
    NoImagesToFitError,
    PtmFitterFailedError,
    PtmFitterNotFoundError,
    build_lp_content,
    generate,
    is_safe_filename,
    lp_path_for,
    normalise_extension,
    usable_slots,
    write_lp,
)

pytestmark = pytest.mark.unit

VECTORS = light_vectors()


def lines_of(content):
    return content.splitlines()


# -- what goes into the .lp ------------------------------------------------


def test_count_line_precedes_the_body():
    content = build_lp_content([CaptureSlot(0, "/shots", "a.jpg", True)], VECTORS)
    assert lines_of(content)[0] == "1"
    assert len(lines_of(content)) == 2


def test_missing_and_unchecked_shots_are_excluded():
    slots = [
        CaptureSlot(0, "/shots", "a.jpg", True),
        CaptureSlot(1, MISSING, MISSING, False),
        CaptureSlot(2, "/shots", "c.jpg", False),
        CaptureSlot(3, "/shots", "d.jpg", True),
    ]
    lines = lines_of(build_lp_content(slots, VECTORS))
    assert lines[0] == "2"
    assert "a.jpg" in lines[1]
    assert "d.jpg" in lines[2]
    assert not any("c.jpg" in line for line in lines)


def test_rows_carry_the_light_vector_for_that_led():
    content = build_lp_content([CaptureSlot(7, "/shots", "shot.jpg", True)], VECTORS)
    _name, x, y, z = lines_of(content)[1].rsplit(" ", 3)
    assert [float(x), float(y), float(z)] == pytest.approx(VECTORS[7])


def test_only_the_filename_is_written_never_the_path():
    # Absolute paths in the .lp are exactly what breaks the fitter when the
    # directory contains a space or a non-ASCII character.
    content = build_lp_content([CaptureSlot(0, "/some/deep/dir", "a.jpg", True)], VECTORS)
    assert lines_of(content)[1].startswith("a.jpg ")
    assert "/some/deep/dir" not in content


def test_extension_is_lowercased():
    content = build_lp_content([CaptureSlot(0, "/shots", "SHOT.JPG", True)], VECTORS)
    assert lines_of(content)[1].startswith("SHOT.jpg ")


def test_staged_names_override_the_originals():
    slots = [CaptureSlot(0, "/shots", "a b.jpg", True), CaptureSlot(1, "/shots", "c.jpg", True)]
    content = build_lp_content(slots, VECTORS, names=["0000.jpg", "0001.jpg"])
    assert lines_of(content)[1].startswith("0000.jpg ")
    assert lines_of(content)[2].startswith("0001.jpg ")


def test_empty_table_produces_a_zero_count():
    assert build_lp_content([], VECTORS) == "0\n"


def test_camera_filenames_write_as_plain_bytes(tmp_path):
    path = tmp_path / "x.lp"
    write_lp(str(path), build_lp_content([CaptureSlot(0, "/shots", "IMG_9999.jpg", True)], VECTORS))
    path.read_bytes().decode("ascii")  # the realistic case is pure ASCII


def test_writing_an_unencodable_lp_is_refused(tmp_path, monkeypatch):
    # The staging path exists so this should not happen; if it ever does,
    # failing loudly beats writing a file the fitter silently misreads.
    monkeypatch.setattr("core.ptm_builder.lp_encoding", lambda: "ascii")
    with pytest.raises(UnicodeEncodeError):
        write_lp(str(tmp_path / "x.lp"), "1\n표본.jpg 0 0 1\n")


def test_the_lp_is_written_in_the_fitters_codepage(tmp_path, monkeypatch):
    # PTMfitter reads the .lp in the machine's ANSI codepage, not UTF-8 --
    # measured: a Hangul name works written as CP949 and fails as UTF-8.
    monkeypatch.setattr("core.ptm_builder.lp_encoding", lambda: "cp949")
    path = tmp_path / "x.lp"
    write_lp(str(path), "1\n표본.jpg 0 0 1\n")
    # Line endings are the platform's -- CRLF on Windows, which is what a
    # Windows binary reading in text mode expects. The encoding is the point.
    assert path.read_bytes().decode("cp949").splitlines() == ["1", "표본.jpg 0 0 1"]


# -- helpers ---------------------------------------------------------------


@pytest.mark.parametrize("name", ["IMG_0001.jpg", "a-b.jpeg", "0000.tiff", "shot(1).jpg"])
def test_safe_filenames(name):
    assert is_safe_filename(name, encoding="cp949")


@pytest.mark.parametrize("name", ["img 0.jpg", "a\tb.jpg", "two words.tiff"])
def test_whitespace_is_never_safe(name):
    # The parser splits on it, so no encoding rescues these.
    assert not is_safe_filename(name, encoding="cp949")


def test_hangul_is_safe_in_a_codepage_that_has_it():
    assert is_safe_filename("표본01.jpg", encoding="cp949")


def test_hangul_is_unsafe_in_a_codepage_that_does_not():
    assert not is_safe_filename("표본01.jpg", encoding="ascii")


def test_normalise_extension_leaves_a_bare_name_alone():
    assert normalise_extension("noextension") == "noextension"


def test_usable_slots_skips_missing_and_unchecked():
    slots = [
        CaptureSlot(0, "/s", "a.jpg", True),
        CaptureSlot(1, MISSING, MISSING, False),
        CaptureSlot(2, "/s", "c.jpg", False),
    ]
    assert [s.filename for s in usable_slots(slots)] == ["a.jpg"]


def test_lp_is_named_after_the_capture_directory():
    path = lp_path_for(os.path.join("/data", "specimen01"))
    assert os.path.basename(path) == "specimen01.lp"
    assert os.path.basename(os.path.dirname(path)) == "specimen01"


def test_trailing_separator_does_not_produce_an_empty_name():
    path = lp_path_for(os.path.join("/data", "specimen01") + os.sep)
    assert os.path.basename(path) == "specimen01.lp"


# -- running the fitter ----------------------------------------------------


@pytest.fixture
def capture(tmp_path):
    """A directory of images and a fitter that behaves like the real one."""
    directory = tmp_path / "specimen01"
    directory.mkdir()
    slots = []
    for i in range(3):
        name = f"IMG_000{i}.JPG"
        (directory / name).write_bytes(b"jpeg")
        slots.append(CaptureSlot(i, str(directory), name, True))
    fitter = tmp_path / "ptmfitter.exe"
    fitter.touch()
    return slots, str(directory), str(fitter)


def fake_fitter(calls, produce=True):
    """Stands in for PTMfitter: writes its output file where it was told."""

    def run(command, cwd):
        calls.append((command, cwd))
        if produce:
            with open(os.path.join(cwd, STAGED_PTM), "wb") as fh:
                fh.write(b"ptm")

    return run


def test_the_fitter_runs_in_the_image_directory(capture, tmp_path):
    slots, directory, fitter = capture
    calls = []
    generate(slots, VECTORS, fitter, str(tmp_path / "out.ptm"), runner=fake_fitter(calls))
    (_command, cwd) = calls[0]
    assert cwd == directory


def test_the_fitter_is_given_relative_ascii_names(capture, tmp_path):
    slots, _directory, fitter = capture
    calls = []
    generate(slots, VECTORS, fitter, str(tmp_path / "out.ptm"), runner=fake_fitter(calls))
    (command, _cwd) = calls[0]
    assert command[1:] == ["-i", STAGED_LP, "-o", STAGED_PTM]


def test_the_ptm_lands_at_the_destination(capture, tmp_path):
    slots, _directory, fitter = capture
    destination = tmp_path / "결과 파일.ptm"  # the fitter never sees this
    generate(slots, VECTORS, fitter, str(destination), runner=fake_fitter([]))
    assert destination.read_bytes() == b"ptm"


def test_the_lp_is_kept_beside_the_images(capture, tmp_path):
    slots, directory, fitter = capture
    kept = generate(slots, VECTORS, fitter, str(tmp_path / "out.ptm"), runner=fake_fitter([]))
    assert kept == os.path.join(directory, "specimen01.lp")
    assert os.path.exists(kept)


def test_the_staging_files_are_cleaned_up(capture, tmp_path):
    slots, directory, fitter = capture
    generate(slots, VECTORS, fitter, str(tmp_path / "out.ptm"), runner=fake_fitter([]))
    assert not os.path.exists(os.path.join(directory, STAGED_LP))
    assert not os.path.exists(os.path.join(directory, STAGED_PTM))


def test_cleanup_happens_even_when_the_fitter_fails(capture, tmp_path):
    slots, directory, fitter = capture
    with pytest.raises(PtmFitterFailedError):
        generate(
            slots,
            VECTORS,
            fitter,
            str(tmp_path / "out.ptm"),
            runner=fake_fitter([], produce=False),
        )
    assert not os.path.exists(os.path.join(directory, STAGED_LP))


def test_producing_nothing_is_an_error_not_a_silent_success(capture, tmp_path):
    # The fitter exits 1 on success, so its status cannot be used; the output
    # file is what tells us.
    slots, _directory, fitter = capture
    with pytest.raises(PtmFitterFailedError):
        generate(
            slots,
            VECTORS,
            fitter,
            str(tmp_path / "out.ptm"),
            runner=fake_fitter([], produce=False),
        )


def test_a_missing_fitter_raises_before_anything_is_written(capture, tmp_path):
    slots, directory, _fitter = capture
    with pytest.raises(PtmFitterNotFoundError):
        generate(slots, VECTORS, str(tmp_path / "nope.exe"), str(tmp_path / "out.ptm"))
    assert not os.path.exists(os.path.join(directory, "specimen01.lp"))


def test_nothing_to_fit_raises(capture, tmp_path):
    slots, _directory, fitter = capture
    unusable = [s._replace(include=False) for s in slots]
    with pytest.raises(NoImagesToFitError):
        generate(unusable, VECTORS, fitter, str(tmp_path / "out.ptm"), runner=MagicMock())


# -- staging, for filenames the fitter cannot read -------------------------


@pytest.fixture
def capture_with_awkward_names(tmp_path):
    directory = tmp_path / "specimen02"
    directory.mkdir()
    slots = []
    for i, name in enumerate(["IMG 0001.JPG", "IMG 0002.JPG"]):
        (directory / name).write_bytes(b"jpeg")
        slots.append(CaptureSlot(i, str(directory), name, True))
    fitter = tmp_path / "ptmfitter.exe"
    fitter.touch()
    return slots, str(directory), str(fitter)


def test_awkward_names_are_staged_elsewhere(capture_with_awkward_names, tmp_path):
    slots, directory, fitter = capture_with_awkward_names
    calls = []
    generate(slots, VECTORS, fitter, str(tmp_path / "out.ptm"), runner=fake_fitter(calls))
    (_command, cwd) = calls[0]
    assert cwd != directory, "a name with a space must not be fed to the fitter as-is"


def test_staged_copies_are_renamed_safely(capture_with_awkward_names, tmp_path):
    slots, _directory, fitter = capture_with_awkward_names
    seen = {}

    def run(command, cwd):
        seen["names"] = sorted(n for n in os.listdir(cwd) if not n.endswith(".lp"))
        seen["lp"] = pathlib.Path(cwd, STAGED_LP).read_text()
        pathlib.Path(cwd, STAGED_PTM).write_bytes(b"ptm")

    generate(slots, VECTORS, fitter, str(tmp_path / "out.ptm"), runner=run)
    assert seen["names"] == ["0000.jpg", "0001.jpg"]
    assert all(is_safe_filename(line.split(" ")[0]) for line in seen["lp"].splitlines()[1:])


def test_staging_still_delivers_the_ptm(capture_with_awkward_names, tmp_path):
    slots, _directory, fitter = capture_with_awkward_names
    destination = tmp_path / "out.ptm"
    generate(slots, VECTORS, fitter, str(destination), runner=fake_fitter([]))
    assert destination.read_bytes() == b"ptm"


def test_the_kept_lp_records_the_real_names(capture_with_awkward_names, tmp_path):
    """The staged names are an implementation detail of the fitter run.

    The .lp left beside the images is for a human working out why a fit looks
    wrong, so it names the files they can actually see, and is utf-8.
    """
    slots, _directory, fitter = capture_with_awkward_names
    kept = generate(slots, VECTORS, fitter, str(tmp_path / "out.ptm"), runner=fake_fitter([]))
    content = pathlib.Path(kept).read_text(encoding="utf-8")
    assert "IMG 0001.jpg" in content
    assert "IMG 0002.jpg" in content

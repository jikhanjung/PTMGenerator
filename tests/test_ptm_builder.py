"""The .lp file handed to PTMfitter — the real output of this application."""

import os

import pytest

from core.image_data import MISSING, CaptureSlot
from core.light_positions import light_vectors
from core.ptm_builder import (
    PtmFitterNotFound,
    build_lp_content,
    lp_path_for,
    run_fitter,
    write_lp,
)

pytestmark = pytest.mark.unit

VECTORS = light_vectors()


def lines_of(content):
    return content.splitlines()


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


def test_row_carries_the_light_vector_for_that_led():
    content = build_lp_content([CaptureSlot(7, "/shots", "shot.jpg", True)], VECTORS)
    _path, x, y, z = lines_of(content)[1].rsplit(" ", 3)
    assert [float(x), float(y), float(z)] == pytest.approx(VECTORS[7])


def test_paths_are_absolute():
    content = build_lp_content([CaptureSlot(0, "shots", "a.jpg", True)], VECTORS)
    assert os.path.isabs(lines_of(content)[1].rsplit(" ", 3)[0])


def test_extension_is_lowercased():
    content = build_lp_content([CaptureSlot(0, "/shots", "SHOT.JPG", True)], VECTORS)
    assert lines_of(content)[1].rsplit(" ", 3)[0].endswith("SHOT.jpg")


def test_empty_table_produces_a_zero_count():
    assert build_lp_content([], VECTORS) == "0\n"


# Asserted on the parts rather than a suffix: os.path.join builds a native
# separator while the input keeps whatever it was given, so a suffix match
# compares "specimen01\specimen01.lp" against "specimen01/specimen01.lp" on
# Windows and fails for a reason that has nothing to do with the contract.


def test_lp_is_named_after_the_capture_directory():
    path = lp_path_for(os.path.join("/data", "specimen01"))
    assert os.path.basename(path) == "specimen01.lp"
    assert os.path.basename(os.path.dirname(path)) == "specimen01"


def test_trailing_separator_does_not_produce_an_empty_name():
    path = lp_path_for(os.path.join("/data", "specimen01") + os.sep)
    assert os.path.basename(path) == "specimen01.lp"


def test_write_lp_round_trip(tmp_path):
    path = str(tmp_path / "x.lp")
    write_lp(path, "1\n/shots/a.jpg 0 0 1\n")
    with open(path) as fh:
        assert fh.read() == "1\n/shots/a.jpg 0 0 1\n"


def test_run_fitter_builds_the_command(tmp_path):
    fitter = tmp_path / "ptmfitter.exe"
    fitter.touch()
    calls = []
    run_fitter(str(fitter), "/x.lp", "/x.ptm", runner=calls.append)
    assert calls == [[str(fitter), "-i", "/x.lp", "-o", "/x.ptm"]]


def test_missing_fitter_raises(tmp_path):
    with pytest.raises(PtmFitterNotFound):
        run_fitter(str(tmp_path / "nope.exe"), "/x.lp", "/x.ptm", runner=lambda cmd: None)


def test_missing_fitter_runs_nothing(tmp_path):
    calls = []
    with pytest.raises(PtmFitterNotFound):
        run_fitter(str(tmp_path / "nope.exe"), "/x.lp", "/x.ptm", runner=calls.append)
    assert calls == []

"""The capture table: CSV persistence, polling, and rebuilding from disk."""

import csv
import os

import pytest

from core.image_data import (
    MISSING,
    CaptureSlot,
    detect_irregular_intervals,
    find_newest_image,
    read_csv,
    write_csv,
)

pytestmark = pytest.mark.unit


# -- CaptureSlot -----------------------------------------------------------


def test_slot_is_tuple_compatible():
    assert CaptureSlot(0, "d", "a.jpg", True) == (0, "d", "a.jpg", True)


def test_captured_is_false_for_a_missing_shot():
    assert not CaptureSlot(1, MISSING, MISSING, False).captured
    assert CaptureSlot(0, "d", "a.jpg", True).captured


# -- CSV -------------------------------------------------------------------


def test_read_csv_of_a_missing_file_is_empty(tmp_path):
    assert read_csv(str(tmp_path / "nope.csv")) == []


def test_round_trip(tmp_path):
    path = str(tmp_path / "image_data.csv")
    original = [
        CaptureSlot(0, "/shots", "a.jpg", True),
        CaptureSlot(1, MISSING, MISSING, False),
        CaptureSlot(2, "/shots", "c.jpg", False),
    ]
    write_csv(path, original)
    assert read_csv(path) == original


def test_legacy_three_column_rows_default_to_included(tmp_path):
    path = tmp_path / "image_data.csv"
    with open(path, "w", newline="") as fh:
        csv.writer(fh).writerow([0, "/shots", "a.jpg"])
    assert read_csv(str(path)) == [CaptureSlot(0, "/shots", "a.jpg", True)]


def test_malformed_rows_are_skipped(tmp_path):
    path = tmp_path / "image_data.csv"
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([0, "/shots", "a.jpg", "True"])
        writer.writerow(["junk"])
        writer.writerow([1, "/shots", "b.jpg", "True"])
    assert [slot.filename for slot in read_csv(str(path))] == ["a.jpg", "b.jpg"]


@pytest.mark.parametrize("written,expected", [("True", True), ("true", True), ("False", False)])
def test_include_flag_parsing(tmp_path, written, expected):
    path = tmp_path / "image_data.csv"
    with open(path, "w", newline="") as fh:
        csv.writer(fh).writerow([0, "/shots", "a.jpg", written])
    assert read_csv(str(path))[0].include is expected


# -- rebuilding a table from files on disk ---------------------------------


def run_detection(directory, names, ctimes):
    """Create `names` and detect intervals with creation times faked exactly."""
    for name in names:
        (directory / name).touch()
    lookup = {os.path.join(str(directory), n): t for n, t in zip(names, ctimes, strict=False)}
    return detect_irregular_intervals(str(directory), getctime=lookup.__getitem__)


def test_empty_directory(tmp_path):
    assert run_detection(tmp_path, [], []) == []


def test_single_image_yields_no_intervals(tmp_path):
    assert run_detection(tmp_path, ["a.jpg"], [1000]) == []


def test_evenly_spaced_images_map_one_to_one(tmp_path):
    slots = run_detection(tmp_path, ["a.jpg", "b.jpg", "c.jpg"], [1000, 1010, 1020])
    assert [s.led_index for s in slots] == [0, 1, 2]
    assert [s.filename for s in slots] == ["a.jpg", "b.jpg", "c.jpg"]
    assert all(s.include for s in slots)
    assert all(s.directory == str(tmp_path) for s in slots)


def test_double_gap_inserts_one_placeholder(tmp_path):
    # c.jpg lands 20s after b.jpg while the typical interval is 10s, so one
    # shot went missing in between.
    slots = run_detection(tmp_path, ["a.jpg", "b.jpg", "c.jpg", "d.jpg"], [1000, 1010, 1030, 1040])
    assert [s.filename for s in slots] == ["a.jpg", "b.jpg", MISSING, "c.jpg", "d.jpg"]
    placeholder = slots[2]
    assert placeholder.directory == MISSING
    assert placeholder.include is False


def test_triple_gap_inserts_two_placeholders(tmp_path):
    slots = run_detection(tmp_path, ["a.jpg", "b.jpg", "c.jpg", "d.jpg"], [1000, 1010, 1040, 1050])
    assert [s.filename for s in slots] == ["a.jpg", "b.jpg", MISSING, MISSING, "c.jpg", "d.jpg"]


def test_indices_stay_contiguous_across_a_gap(tmp_path):
    slots = run_detection(tmp_path, ["a.jpg", "b.jpg", "c.jpg", "d.jpg"], [1000, 1010, 1030, 1040])
    assert [s.led_index for s in slots] == [0, 1, 2, 3, 4]


def test_non_image_files_are_ignored(tmp_path):
    slots = run_detection(
        tmp_path, ["a.jpg", "notes.txt", "b.jpg", "image_data.csv"], [1000, 1005, 1010, 1015]
    )
    assert [s.filename for s in slots] == ["a.jpg", "b.jpg"]


def test_extensions_are_matched_case_insensitively(tmp_path):
    slots = run_detection(tmp_path, ["a.JPG", "b.Tiff"], [1000, 1010])
    assert [s.filename for s in slots] == ["a.JPG", "b.Tiff"]


# -- polling for an incoming shot ------------------------------------------


def touch(directory, name, mtime):
    path = directory / name
    path.touch()
    os.utime(path, (mtime, mtime))
    return str(path)


def test_nothing_newer_returns_none(tmp_path):
    touch(tmp_path, "old.jpg", 1000)
    assert find_newest_image(str(tmp_path), 2000) == (None, 2000)


def test_returns_the_newest_of_several(tmp_path):
    touch(tmp_path, "first.jpg", 2500)
    newest = touch(tmp_path, "second.jpg", 3500)
    path, mtime = find_newest_image(str(tmp_path), 2000)
    assert path == newest
    assert mtime == 3500


def test_non_image_files_are_not_returned(tmp_path):
    touch(tmp_path, "image_data.csv", 3000)
    touch(tmp_path, "output.log", 3000)
    assert find_newest_image(str(tmp_path), 2000)[0] is None


def test_polling_matches_extensions_case_insensitively(tmp_path):
    expected = touch(tmp_path, "SHOT.JPG", 3000)
    assert find_newest_image(str(tmp_path), 2000)[0] == expected


def test_subdirectories_are_not_searched(tmp_path):
    nested = tmp_path / "sub"
    nested.mkdir()
    touch(nested, "deep.jpg", 3000)
    assert find_newest_image(str(tmp_path), 2000)[0] is None

"""The capture table: one slot per LED, and how it is persisted.

A run produces one image per LED. The table that tracks them is a list of
`CaptureSlot`s, mirrored to `image_data.csv` in the capture directory so a run
can be reopened later.

Slots for shots that failed carry "-" for both the directory and the filename,
which keeps the LED index aligned with the light-position table even when part
of a run is missing.
"""

import csv
import os
from typing import NamedTuple

# One list, used both when polling for an incoming shot and when rebuilding a
# table from a directory. They disagreed before this was shared: polling
# accepted .gif and .bmp and matched case-insensitively, while the rebuild
# accepted neither and missed a file named .JPG.
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff")

# What a failed shot looks like in the table.
MISSING = "-"


class CaptureSlot(NamedTuple):
    """One LED's shot. A plain tuple, so existing unpacking keeps working."""

    led_index: int
    directory: str
    filename: str
    include: bool

    @property
    def captured(self):
        """False for a shot that never arrived."""
        return self.filename != MISSING


def read_csv(path):
    """Load a capture table. Returns [] if there is no file.

    Accepts the 3-column format written before include flags existed; those
    rows default to included.

    Read as utf-8-sig: utf-8 to match what write_csv produces regardless of
    platform, and -sig so a file someone opened and re-saved in Excel, which
    prefixes a byte-order mark, still parses its first column as a number.
    """
    if not os.path.exists(path):
        return []
    slots = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.reader(fh):
            if len(row) == 3:
                index, directory, filename = row
                include = True
            elif len(row) == 4:
                index, directory, filename, include_str = row
                include = include_str.lower() == "true"
            else:
                continue  # malformed; skip rather than abort the load
            slots.append(CaptureSlot(int(index), directory, filename, include))
    return slots


def write_csv(path, slots):
    """Write the capture table, overwriting whatever was there.

    utf-8 explicitly, not the platform default. The table holds directory and
    file names, which for this application are routinely non-ASCII, and it is
    written into the capture directory to be read back later — possibly on a
    machine whose default encoding is cp949 rather than utf-8.
    """
    with open(path, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(slots)


def detect_irregular_intervals(directory_path, getctime=os.path.getctime):
    """Rebuild the capture table for a directory of already-taken images.

    Sorts the images by creation time, takes the most frequent gap between
    consecutive files as the typical shot interval, and reads any gap longer
    than 1.5x that as one or more missed shots, inserting a placeholder slot for
    each so the surviving images keep their original LED indices.

    Args:
        directory_path (str): Directory to scan. Not searched recursively.
        getctime: Seam for tests, which need exact intervals without sleeping.

    Returns:
        list[CaptureSlot]: One slot per LED position. Empty when fewer than two
        images make the interval unmeasurable.
    """
    image_files = [f for f in os.listdir(directory_path) if f.lower().endswith(IMAGE_EXTENSIONS)]
    image_files.sort(key=lambda f: getctime(os.path.join(directory_path, f)))

    intervals = []
    for i in range(1, len(image_files)):
        try:
            first = getctime(os.path.join(directory_path, image_files[i - 1]))
            second = getctime(os.path.join(directory_path, image_files[i]))
            # Subtracted as timestamps, not datetimes. The old code converted
            # both with datetime.fromtimestamp() and subtracted those, which
            # produces naive local datetimes: across a DST transition the
            # difference is an hour out, and a normal gap reads as several
            # missed shots. Seconds since the epoch have no such discontinuity.
            intervals.append(round(second - first))
        except FileNotFoundError:
            print(f"Error: Image file not found: {image_files[i]}")

    if not intervals:
        return []

    counts = {}
    for interval in intervals:
        counts[interval] = counts.get(interval, 0) + 1
    typical = max(counts, key=counts.get)

    slots = [CaptureSlot(0, directory_path, image_files[0], True)]
    span = 0
    for i, interval in enumerate(intervals):
        if interval == 0:
            # Two files with the same timestamp: one shot, two files (RAW+JPEG,
            # say). Consume the index without emitting a slot.
            span += 1
            continue
        if interval > 1.5 * typical:
            missed = round(interval / typical) - 1
            slots.extend(CaptureSlot(i + j + 1, MISSING, MISSING, False) for j in range(missed))
            span += missed
        slots.append(CaptureSlot(i + span + 1, directory_path, image_files[i + 1], True))
    return slots


def find_newest_image(directory, newer_than):
    """The most recent image in `directory` created after `newer_than`.

    Returns (path, mtime), or (None, newer_than) if nothing new has landed.
    Not recursive: the tethering software drops files in one directory, and
    walking subdirectories made every poll slower for no gain.
    """
    from pathlib import Path

    newest_path, newest_time = None, newer_than
    for candidate in Path(directory).glob("*"):
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        mtime = candidate.stat().st_mtime
        if mtime > newest_time:
            newest_time, newest_path = mtime, str(candidate)
    return newest_path, newest_time

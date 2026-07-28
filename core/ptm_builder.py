"""Producing the .lp file and driving PTMfitter.

PTMfitter is a Hewlett-Packard binary from around 2001 and it is particular
about paths. Measured against the shipped `PTMfitter.exe` with nine images:

    ============================================================  ======
    .lp lists bare filenames, run with cwd = the image directory  works
      ... directory name contains a space                         works
      ... directory name contains Hangul                          works
      ... directory path is very long                             works
    .lp lists absolute paths, ASCII, no spaces                    works
    .lp lists absolute paths containing a space                   FAILS
    .lp lists absolute paths containing Hangul                    FAILS
    a filename inside the .lp contains a space                    FAILS
    -o is an absolute path containing a space and Hangul          FAILS
    -o is a relative ASCII name                                   works
    a Hangul filename, .lp written as UTF-8                       FAILS
    a Hangul filename, .lp written as CP949                       works
    ============================================================  ======

Two separate constraints come out of that:

* **It splits each .lp line on whitespace**, so anything containing a space is
  read as part of the light vector. No amount of encoding fixes this.
* **It reads the .lp in the machine's ANSI codepage**, not UTF-8 — which is
  what a 2001 Windows binary using `fopen` would do. So a Hangul filename works
  when the file is written as CP949 on a Korean Windows, and fails as UTF-8.

Where the process happens to be running does not matter at all; only what it
parses does. So the .lp lists bare filenames, is written in the local ANSI
codepage, the output name handed to it is relative ASCII, and cwd is set to the
images. Python then moves the result wherever the user asked, having no such
difficulty. A filename it could not read either way — one containing a space —
is worked around by staging the images under safe names.

In practice neither arises: the images come straight off the camera as
IMG_9999.JPG. This is here so that a renamed file produces a working fit or a
clear error, rather than a silently wrong one.

Note also that **the fitter returns 1 on success**, so its exit status cannot be
used to tell whether it worked; the output file is checked instead.
"""

import locale
import os
import re
import shutil
import subprocess
import sys
import tempfile

#: The fitter tokenises .lp lines on whitespace, so a name containing any is
#: unusable whatever the encoding.
UNSAFE_FILENAME = re.compile(r"\s")

#: Names used while the fitter runs, before the result is moved into place.
STAGED_LP = "ptmfit.lp"
STAGED_PTM = "ptmfit.ptm"


class PtmFitterNotFoundError(Exception):
    """The configured PTMfitter executable is not on disk."""


class PtmFitterFailedError(Exception):
    """PTMfitter ran but produced no output.

    The message names what was run and where to look, which is what the user
    has to act on -- the fitter itself reports almost nothing.
    """


class NoImagesToFitError(Exception):
    """Every slot is missing or unchecked."""


def lp_encoding():
    """The encoding PTMfitter reads a .lp in: the machine's ANSI codepage.

    `mbcs` is that codepage on Windows, which is where the fitter runs. Off
    Windows there is no such thing, so the platform's preferred encoding stands
    in — only the test suite exercises that path.
    """
    if sys.platform == "win32":
        return "mbcs"
    return locale.getpreferredencoding(False)


def is_safe_filename(name, encoding=None):
    """True if PTMfitter can read this name out of a .lp file.

    Two ways it cannot: whitespace, which its parser splits on, and a character
    absent from the codepage it reads the file in.
    """
    if UNSAFE_FILENAME.search(name):
        return False
    try:
        name.encode(encoding or lp_encoding())
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def usable_slots(slots):
    """The slots that belong in a .lp: captured, and included by the user."""
    return [slot for slot in slots if slot.captured and slot.include]


def normalise_extension(filename):
    """Lowercase the extension.

    Tethering software writes .JPG as often as .jpg and the fitter is
    case-sensitive about what it is given.
    """
    stem, _, extension = filename.rpartition(".")
    return f"{stem}.{extension.lower()}" if stem else filename


def build_lp_content(slots, light_vectors, names=None):
    """Render the .lp file.

    Args:
        slots (list[CaptureSlot]): The capture table. Shots that failed and
            shots the user unchecked are left out of both the count and the body.
        light_vectors (list[list[float]]): Unit vectors, indexed by LED.
        names (list[str] | None): One filename per usable slot, when the images
            have been staged under different names. Defaults to each slot's own.

    Returns:
        str: The complete file contents. Filenames only, never paths -- see the
        module docstring for why.
    """
    usable = usable_slots(slots)
    if names is None:
        names = [normalise_extension(slot.filename) for slot in usable]
    lines = [
        f"{name} {' '.join(str(c) for c in light_vectors[slot.led_index])}"
        for slot, name in zip(usable, names, strict=True)
    ]
    return f"{len(lines)}\n" + "".join(line + "\n" for line in lines)


def lp_path_for(image_directory):
    """Where the kept .lp goes: beside the images, named after their directory."""
    name = os.path.basename(os.path.normpath(image_directory))
    return os.path.join(image_directory, name + ".lp")


def write_lp(path, content):
    """Write a .lp for the fitter, in the codepage it reads.

    Strict on purpose: if this raises, the staging check has a hole in it.
    Failing loudly beats writing a file the fitter silently misreads.
    """
    with open(path, "w", encoding=lp_encoding(), errors="strict") as fh:
        fh.write(content)


def write_reference_lp(path, content):
    """Write the .lp kept beside the images, for a human to look at.

    This one records the real filenames, which may be non-ASCII, so it is
    written as utf-8 and is not what the fitter is given.
    """
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def generate(slots, light_vectors, fitter_path, destination, runner=None):
    """Build the .lp, run PTMfitter, and put the .ptm where it was asked for.

    Args:
        slots (list[CaptureSlot]): The capture table.
        light_vectors (list[list[float]]): Unit vectors, indexed by LED.
        fitter_path (str): The PTMfitter executable.
        destination (str): Where the finished .ptm should end up. May contain
            anything -- spaces, Hangul -- because Python moves it there.
        runner: Seam for tests. Called as runner(command, cwd=...).

    Returns:
        str: The .lp written beside the images, kept for inspection when a fit
        looks wrong.

    Raises:
        PtmFitterNotFoundError: The executable is missing.
        NoImagesToFitError: Nothing to fit.
        PtmFitterFailedError: It ran but produced no .ptm.
    """
    if not os.path.exists(fitter_path):
        raise PtmFitterNotFoundError(fitter_path)

    usable = usable_slots(slots)
    if not usable:
        raise NoImagesToFitError("no captured, included images")

    image_directory = usable[0].directory
    kept_lp = lp_path_for(image_directory)
    write_reference_lp(kept_lp, build_lp_content(slots, light_vectors))

    unsafe = [s for s in usable if not is_safe_filename(normalise_extension(s.filename))]
    if unsafe:
        _fit_via_staging(usable, slots, light_vectors, fitter_path, destination, runner)
    else:
        _fit_in_place(image_directory, kept_lp, fitter_path, destination, runner)
    return kept_lp


def _fit_in_place(image_directory, kept_lp, fitter_path, destination, runner):
    """Run the fitter where the images already are. The common case."""
    staged_lp = os.path.join(image_directory, STAGED_LP)
    staged_ptm = os.path.join(image_directory, STAGED_PTM)
    shutil.copyfile(kept_lp, staged_lp)
    try:
        _run(fitter_path, image_directory, runner)
        shutil.move(staged_ptm, destination)
    finally:
        for leftover in (staged_lp, staged_ptm):
            if os.path.exists(leftover):
                os.remove(leftover)


def _fit_via_staging(usable, slots, light_vectors, fitter_path, destination, runner):
    """Copy the images out under safe names first.

    Rare -- camera filenames are IMG_0001.JPG -- but a file renamed to include
    a space makes the fitter read the name as part of the light vector, which
    produces a wrong fit rather than an error.
    """
    with tempfile.TemporaryDirectory(prefix="ptmfit-") as staging:
        names = [
            f"{i:04d}{os.path.splitext(slot.filename)[1].lower()}" for i, slot in enumerate(usable)
        ]
        for slot, name in zip(usable, names, strict=True):
            shutil.copy2(os.path.join(slot.directory, slot.filename), os.path.join(staging, name))
        write_lp(
            os.path.join(staging, STAGED_LP),
            build_lp_content(slots, light_vectors, names=names),
        )
        _run(fitter_path, staging, runner)
        shutil.move(os.path.join(staging, STAGED_PTM), destination)


def _run(fitter_path, cwd, runner=None):
    """Invoke the fitter in `cwd`, and check it actually produced something."""
    if runner is None:
        runner = _subprocess_runner
    command = [str(fitter_path), "-i", STAGED_LP, "-o", STAGED_PTM]
    print(f"Executing {command} in {cwd}")
    runner(command, cwd=cwd)
    produced = os.path.join(cwd, STAGED_PTM)
    if not os.path.exists(produced) or os.path.getsize(produced) == 0:
        # Not checked via the exit status: the fitter returns 1 on success.
        raise PtmFitterFailedError(
            f"PTMfitter produced no output. Its input is {STAGED_LP} in {cwd}."
        )


def _subprocess_runner(command, cwd):
    subprocess.run(command, cwd=cwd, check=False)

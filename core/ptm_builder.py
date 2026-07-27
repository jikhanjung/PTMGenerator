"""Producing the .lp file and handing it to PTMfitter.

PTMfitter takes a light-position file: a count, then one line per image giving
its path and the unit vector of the light that was on. This module builds that
text and runs the fitter; choosing the output path is the UI's job.
"""

import os
import subprocess


class PtmFitterNotFound(Exception):
    """Raised when the configured PTMfitter executable is not on disk."""


def build_lp_content(slots, light_vectors):
    """Render the .lp file for a capture table.

    Shots that failed, and shots the user unchecked, are left out — both of
    the count on the first line and of the body.

    Args:
        slots (list[CaptureSlot]): The capture table.
        light_vectors (list[list[float]]): Unit vectors, indexed by LED.

    Returns:
        str: The complete file contents.
    """
    lines = []
    for index, directory, filename, include in slots:
        if filename == "-" or not include:
            continue
        # PTMfitter is case-sensitive about the extension it is handed, and
        # tethering software writes .JPG as often as .jpg.
        stem, _, extension = filename.rpartition(".")
        normalised = f"{stem}.{extension.lower()}" if stem else filename
        path = os.path.abspath(os.path.join(directory, normalised))
        vector = " ".join(str(component) for component in light_vectors[index])
        lines.append(f"{path} {vector}")
    body = "".join(line + "\n" for line in lines)
    return f"{len(lines)}\n{body}"


def lp_path_for(image_directory):
    """Where the .lp goes: beside the images, named after their directory."""
    name = os.path.basename(os.path.normpath(image_directory))
    return os.path.join(image_directory, name + ".lp")


def write_lp(path, content):
    with open(path, "w") as fh:
        fh.write(content)


def run_fitter(fitter_path, lp_path, ptm_path, runner=None):
    """Invoke PTMfitter.

    Args:
        runner: Seam for tests, so the suite never launches a real process.
            Resolved at call time rather than bound as a default, so patching
            `core.ptm_builder.subprocess.call` works.

    Raises:
        PtmFitterNotFound: If `fitter_path` does not exist.
    """
    if not os.path.exists(fitter_path):
        raise PtmFitterNotFound(fitter_path)
    if runner is None:
        runner = subprocess.call
    command = [str(fitter_path), "-i", str(lp_path), "-o", str(ptm_path)]
    print(f"Executing: {command}")
    return runner(command)

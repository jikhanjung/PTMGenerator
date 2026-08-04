"""The `--self-test` gate, and the checks behind it.

This file exists because of what the gate *is*. `reusable_build.yml` runs
`PTMGenerator2.exe --self-test` against the frozen bundle, and that is the only
thing in the project that can see a PyInstaller build shipped without its icons
or its translations -- a source checkout has those on disk whatever happens.

A gate like that has a specific failure mode: if the flag stops being
recognised, or `run()` stops returning False on a failed check, **the CI step
still passes and examines nothing.** So the checks here are not only "does the
self-test pass" -- they pin that it *fails when it should*, which is the only
evidence the gate is looking at anything.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

import PTMGenerator2
from core import self_test

ROOT = Path(__file__).resolve().parents[1]


# -- the checks --------------------------------------------------------------


def test_every_check_passes_against_the_source_tree():
    assert self_test.run(log=lambda _message: None) is True


def test_a_failing_check_makes_the_run_fail():
    def broken():
        raise self_test.CheckFailedError("nope")

    assert self_test.run([("broken", broken)], log=lambda _m: None) is False


def test_a_failing_check_does_not_stop_the_others():
    """One missing icon must not hide a missing translation.

    The CI log is the only place anyone sees this, so it has to name
    everything that is wrong, not just the first thing.
    """
    seen = []

    def broken():
        raise self_test.CheckFailedError("nope")

    self_test.run([("broken", broken), ("fine", lambda: "ok")], log=seen.append)
    assert any("FAILED" in line for line in seen)
    assert any("fine: ok" in line for line in seen)


def test_a_check_that_raises_something_unexpected_is_still_caught():
    # `except Exception`, not `except CheckFailedError` -- a check that breaks
    # in a way nobody predicted must report, not take the build down with a
    # traceback that says nothing about the bundle.
    def broken():
        raise RuntimeError("not a CheckFailedError")

    assert self_test.run([("broken", broken)], log=lambda _m: None) is False


def test_a_missing_icon_is_reported(monkeypatch):
    monkeypatch.setitem(self_test.resources.ICON, "nope", "icons/not-here.png")
    with pytest.raises(self_test.CheckFailedError, match="nope"):
        self_test.check_icons()


def test_a_missing_translation_is_reported(monkeypatch):
    monkeypatch.setattr(self_test, "SUPPORTED_LANGUAGES", [("Klingon", "tlh")])
    with pytest.raises(self_test.CheckFailedError, match="tlh"):
        self_test.check_translations()


def test_a_short_light_table_is_reported(monkeypatch):
    monkeypatch.setattr(self_test, "light_vectors", lambda: [(0.0, 0.0, 1.0)])
    with pytest.raises(self_test.CheckFailedError, match="expected 50"):
        self_test.check_light_table()


def test_a_light_vector_that_is_not_a_unit_vector_is_reported(monkeypatch):
    table = [(0.0, 0.0, 1.0)] * self_test.LED_COUNT
    table[7] = (0.0, 0.0, 2.0)
    monkeypatch.setattr(self_test, "light_vectors", lambda: table)
    with pytest.raises(self_test.CheckFailedError, match="LED 7"):
        self_test.check_light_table()


# -- the flag ----------------------------------------------------------------


def test_the_flag_is_parsed_and_short_circuits_startup(monkeypatch):
    """`main` must hand over to the self-test and return, never reach exec_().

    If this dispatch breaks, the executable CI launches with `--self-test`
    opens a window instead and waits for an event loop that never gets one --
    or worse, returns 0 having run the application rather than the checks.
    """
    called = []
    monkeypatch.setattr(PTMGenerator2, "self_test", lambda argv: called.append(argv) or 0)
    # Nothing further may run: exec_() would block, and a QApplication built
    # here would collide with the session-scoped one.
    monkeypatch.setattr(
        PTMGenerator2, "PtmApplication", _never("main() continued past --self-test")
    )

    assert PTMGenerator2.main(["PTMGenerator2.py", "--self-test"]) == 0
    assert called == [["PTMGenerator2.py", "--self-test"]]


def test_without_the_flag_the_self_test_does_not_run(monkeypatch):
    monkeypatch.setattr(PTMGenerator2, "self_test", _never("self_test ran without the flag"))
    monkeypatch.setattr(PTMGenerator2, "PtmApplication", _never("stop here"))
    with pytest.raises(AssertionError, match="stop here"):
        PTMGenerator2.main(["PTMGenerator2.py"])


def _never(message):
    def fail(*_args, **_kwargs):
        raise AssertionError(message)

    return fail


# -- end to end --------------------------------------------------------------
#
# In a subprocess, because the self-test builds its own QApplication and the
# suite already has a session-scoped one. That is not a workaround: what CI
# runs is the process, and the exit code is the whole contract.


def _run_self_test(tmp_path, preamble=""):
    env = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        # Never the developer's real preferences or log.
        "PTMGENERATOR2_CONFIG_DIR": str(tmp_path / "config"),
        "PTMGENERATOR2_DATA_DIR": str(tmp_path / "data"),
    }
    code = f"{preamble}\nimport sys, PTMGenerator2\nsys.exit(PTMGenerator2.main(sys.argv))"
    return subprocess.run(
        [sys.executable, "-c", code, "--self-test"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        # The self-test takes about a second. A generous ceiling, but well
        # under CI's per-test `--timeout=60`, so that if the flag ever stops
        # being recognised -- `main()` then opens a window and waits on an
        # event loop -- this fails with the subprocess output rather than
        # pytest killing the whole test with nothing to show.
        timeout=45,
    )


@pytest.mark.slow
def test_the_self_test_passes_and_exits_zero(tmp_path):
    result = _run_self_test(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "self-test PASSED" in result.stdout
    # Each check reported, not silently skipped.
    for name in ("icons", "translations", "light table", "main window"):
        assert name in result.stdout


@pytest.mark.slow
def test_the_self_test_fails_and_exits_nonzero_when_the_bundle_is_incomplete(tmp_path):
    """The gate run against known-bad input -- the point of the whole file.

    Making a check gating and making it see what you think it sees are two
    different pieces of work; this is the second one. An icon named in
    `resources.ICON` with no file behind it is exactly what a PyInstaller spec
    that forgot `--add-data` produces.
    """
    result = _run_self_test(
        tmp_path,
        preamble=(
            "import core.resources\n"
            "core.resources.ICON['missing'] = 'icons/not-in-the-bundle.png'\n"
        ),
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "self-test FAILED" in result.stdout
    assert "missing" in result.stdout

"""The About dialog and the build metadata behind it."""

import json

import pytest
from PyQt5.QtWidgets import QMessageBox

import version
from core import build_info
from ui import about

pytestmark = pytest.mark.ui


# -- build metadata ----------------------------------------------------------


def test_a_checkout_reports_that_it_is_a_checkout(tmp_path):
    """The fallback has to look broken, not plausible.

    A build number of "1" in a bug report is a lie that nobody can detect;
    "local" is the truth and is immediately readable as such.
    """
    info = build_info.read([str(tmp_path / "nothing.json")])
    assert info["build_number"] == "local"
    assert info["build_date"] == "development"
    assert info["commit"] == "unknown"
    # The version still comes from the single source, not from the fallback.
    assert info["version"] == version.__version__


def test_a_stamped_file_is_read_back(tmp_path):
    path = tmp_path / "build_info.json"
    path.write_text(
        json.dumps({"build_number": "412", "build_date": "2026-08-04", "commit": "deadbee"}),
        encoding="utf-8",
    )
    info = build_info.read([str(path)])
    assert info["build_number"] == "412"
    assert info["commit"] == "deadbee"


def test_a_partial_file_keeps_the_defaults_for_what_is_missing(tmp_path):
    path = tmp_path / "build_info.json"
    path.write_text(json.dumps({"build_number": "412"}), encoding="utf-8")
    info = build_info.read([str(path)])
    assert info["build_number"] == "412"
    assert info["commit"] == "unknown"


@pytest.mark.parametrize("content", ["not json at all", '"a string, not an object"', "[1, 2]"])
def test_a_corrupt_file_does_not_stop_startup(tmp_path, content):
    # This is read during startup. A metadata file nobody can parse must not
    # be the reason the application will not open.
    path = tmp_path / "build_info.json"
    path.write_text(content, encoding="utf-8")
    assert build_info.read([str(path)])["build_number"] == "local"


def test_the_first_readable_candidate_wins(tmp_path):
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    second.write_text(json.dumps({"build_number": "second"}), encoding="utf-8")
    assert build_info.read([str(first), str(second)])["build_number"] == "second"


def test_the_bundled_copy_is_preferred_over_one_beside_the_executable(tmp_path, monkeypatch):
    """`sys._MEIPASS` is not the directory holding the executable.

    PyInstaller 6 puts a onedir build's data in `_internal/`, so the metadata
    is *not* beside the .exe -- a CI check asserting the pre-6 path failed on
    its first real run while the runtime lookup was fine. Both layouts are
    still searched, and the bundle's own directory wins, so a leftover file
    next to the executable cannot report a stale build.
    """
    bundle = tmp_path / "_internal"
    bundle.mkdir()
    (bundle / "build_info.json").write_text(json.dumps({"build_number": "bundled"}))
    (tmp_path / "build_info.json").write_text(json.dumps({"build_number": "stale"}))

    monkeypatch.setattr(build_info.sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setattr(build_info.sys, "frozen", True, raising=False)
    monkeypatch.setattr(build_info.sys, "executable", str(tmp_path / "PTMGenerator2"))

    candidates = build_info._candidates()
    assert candidates[0] == str(bundle / "build_info.json")
    assert build_info.read()["build_number"] == "bundled"


def test_a_source_checkout_looks_beside_the_package():
    # Not via the working directory: the metadata must read the same whatever
    # directory the application was started from.
    monkeypatch_free = build_info._candidates()
    assert monkeypatch_free[-1].endswith("build_info.json")
    assert "core" not in monkeypatch_free[-1].split("/")[-2:]


def test_the_summary_names_the_build():
    info = {"version": "1.2.3", "build_number": "412", "build_date": "2026-08-04"}
    assert build_info.summary(info) == "1.2.3 (build 412, 2026-08-04)"


# -- the dialog --------------------------------------------------------------


@pytest.fixture
def box(main_window):
    dialog, copy_button = about.build_about_box(main_window)
    yield dialog, copy_button
    dialog.deleteLater()


def test_the_about_box_carries_what_the_brand_guide_asks_for(box):
    dialog, _copy = box
    text = dialog.text()
    assert version.PROGRAM_NAME in text
    assert version.__version__ in text
    # The vendor, not only the app name.
    assert version.COMPANY_NAME in text
    assert version.PROGRAM_COPYRIGHT in text
    assert version.PROGRAM_LICENSE in text


def test_the_links_are_present_and_clickable(box):
    dialog, _copy = box
    text = dialog.text()
    for url in (version.PROGRAM_HOMEPAGE, version.PROGRAM_MANUAL, version.PROGRAM_ISSUES):
        assert f'href="{url}"' in text, url
    # Plain text would render the anchors as markup rather than links.
    assert dialog.textFormat() == 1  # Qt.RichText


def test_the_build_is_shown_next_to_the_version(box):
    dialog, _copy = box
    info = build_info.read()
    assert info["build_number"] in dialog.text()
    assert info["build_date"] in dialog.text()


def test_there_is_a_copy_diagnostics_button(box):
    dialog, copy_button = box
    assert copy_button in dialog.buttons()
    assert dialog.buttonRole(copy_button) == QMessageBox.ActionRole


def test_the_copyright_matches_the_license_file():
    """The brand guide's one hard rule about copyright: they must agree.

    LICENSE is the record that actually governs, so it is the one the About
    dialog has to match -- not the other way round.
    """
    from pathlib import Path

    licence = Path(__file__).resolve().parents[1] / "LICENSE"
    years_and_holder = version.PROGRAM_COPYRIGHT.removeprefix("© ")
    assert years_and_holder in licence.read_text(encoding="utf-8")


# -- diagnostics -------------------------------------------------------------


def test_diagnostics_carry_both_directories(settings_dir):
    """Config and data are deliberately two locations (devlog 014).

    Reporting one of them answers half of "where are your settings and your
    log", which is the question this button exists to save asking.
    """
    from core import paths

    text = about.diagnostics()
    assert paths.config_dir() in text
    assert paths.data_dir() in text
    assert paths.log_path() in text
    assert paths.config_dir() != paths.data_dir()


def test_diagnostics_carry_the_version_and_the_build():
    text = about.diagnostics(
        {"version": "1.2.3", "build_number": "9", "build_date": "d", "commit": "c"}
    )
    assert "1.2.3" in text
    assert "build: 9" in text
    assert "c" in text


def test_diagnostics_are_plain_text():
    # It is going into an issue tracker, not a rich-text widget.
    assert "<" not in about.diagnostics()


def test_the_copy_button_puts_the_diagnostics_on_the_clipboard(main_window, monkeypatch):
    from PyQt5.QtWidgets import QApplication

    built = {}
    real_build = about.build_about_box

    def record(parent, info=None):
        built["box"], built["copy"] = real_build(parent, info)
        return built["box"], built["copy"]

    monkeypatch.setattr(about, "build_about_box", record)

    shown = []

    def fake_exec(self):
        # Press Copy diagnostics first, then dismiss. If show_about ever stops
        # re-showing, the first assertion below fails; if it stops breaking out
        # on any other button, this test hangs -- which is the other half of
        # what the loop can get wrong.
        shown.append(1)
        pressed = built["copy"] if len(shown) == 1 else None
        monkeypatch.setattr(self, "clickedButton", lambda: pressed)
        return 0

    monkeypatch.setattr(QMessageBox, "exec_", fake_exec)
    about.show_about(main_window)

    assert len(shown) == 2, "the dialog did not stay up after Copy diagnostics"
    assert "config:" in QApplication.clipboard().text()


@pytest.fixture
def korean(qapp):
    """The Korean catalogue installed, and taken back off afterwards.

    A leaked QTranslator is global state: it stays installed for every test
    that runs after this one, and the failures land somewhere else entirely.
    """
    from PyQt5.QtCore import QTranslator

    from core.resources import translation_path

    translator = QTranslator()
    assert translator.load(translation_path("ko")), "the compiled Korean catalogue is missing"
    qapp.installTranslator(translator)
    yield
    qapp.removeTranslator(translator)


def test_the_about_dialog_is_translated(korean, main_window):
    """Driven through the real catalogue, not checked for the shape of the call.

    There is a silent way for this to break. pylupdate5 reads the source
    rather than running it and extracts a call only when *both* arguments are
    string literals at the call site -- so a `_tr()` helper or a `CONTEXT`
    constant leaves the code working and the strings untranslated, with
    nothing failing to say so. Both were tried here first, and a test that
    looked for `translate("About", ...)` in the source passed against both,
    because a call that is no longer in that form is simply not found.

    Asserting on the rendered text is what closes that: a string that stopped
    being extracted comes back English here.
    """
    dialog, copy_button = about.build_about_box(main_window)
    try:
        assert dialog.windowTitle() == "정보"
        assert copy_button.text() == "진단 정보 복사"
        assert "라이선스로 배포됩니다" in dialog.text()
        assert "빌드" in dialog.text()
    finally:
        dialog.deleteLater()

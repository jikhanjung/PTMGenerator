"""The build inputs the PyInstaller spec names must exist.

None of this is exercised by running the application, and the Windows build is
the only place it bites: PyInstaller accepts a .png icon on Linux and refuses it
on Windows, so a wrong path here passes every Linux check and fails the release.
Cheap to assert here, expensive to discover in a release run.
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parent.parent
SPEC = (ROOT / "PTMGenerator2.spec").read_text(encoding="utf-8")


def test_the_icon_the_spec_names_exists():
    match = re.search(r"icon=\['([^']+)'\]", SPEC)
    assert match, "the spec no longer declares an icon"
    assert (ROOT / match.group(1)).is_file(), f"{match.group(1)} is missing"


def test_the_windows_icon_is_an_ico():
    # Windows PyInstaller accepts only ('exe', 'ico'). A .png fails the build.
    match = re.search(r"icon=\['([^']+)'\]", SPEC)
    assert match.group(1).lower().endswith(".ico")


def test_the_ico_carries_the_sizes_windows_asks_for():
    # Windows picks a size per context: 16 in the title bar, 32 in the taskbar,
    # 48 in Explorer, 256 for the preview tile. A single-size .ico renders
    # blurry in most of them.
    Image = pytest.importorskip("PIL.Image", reason="Pillow is not a runtime dependency")
    with Image.open(ROOT / "icons" / "PTMGenerator2.ico") as ico:
        sizes = set(ico.info.get("sizes", ()))
    assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= sizes


def test_the_datas_globs_match_something():
    """('icons/*.png', 'icons') style entries must actually collect files."""
    for pattern, _dest in re.findall(r"\('([^']+)',\s*'([^']+)'\)", SPEC):
        assert list(ROOT.glob(pattern)), f"the spec bundles {pattern}, which matches nothing"


def test_the_entry_point_exists():
    match = re.search(r"Analysis\(\s*\['([^']+)'\]", SPEC)
    assert match and (ROOT / match.group(1)).is_file()


def test_the_spec_reads_the_version_rather_than_hardcoding_it():
    assert "version.py" in SPEC
    assert not re.search(r"name\s*=\s*['\"]PTMGenerator2_v\d", SPEC)


# -- the Inno Setup installer ----------------------------------------------
#
# The template and the spec have to agree on where the build lands and what it
# is called. Nothing else checks that pair until a Windows runner has spent six
# minutes on it.

INSTALLER = (ROOT / "installer" / "PTMGenerator2.iss.template").read_text(encoding="utf-8")


def test_the_spec_builds_a_directory_not_a_single_file():
    """The installer ships dist/PTMGenerator2/, which only exists with COLLECT."""
    assert "COLLECT(" in SPEC
    assert "exclude_binaries=True" in SPEC


def test_the_installer_ships_what_the_spec_produces():
    name = re.search(r"EXE_NAME\s*=\s*[\"']([^\"']+)[\"']", SPEC).group(1)
    assert rf"{{{{DIST_PATH}}}}\{name}\*" in INSTALLER
    assert rf"{{app}}\{name}.exe" in INSTALLER


def test_the_executable_name_carries_no_version():
    """The installer filename carries it; a versioned .exe inside {app} would
    leave the old one behind on every upgrade, and the Start Menu shortcut
    would point at whichever version installed last."""
    name = re.search(r"EXE_NAME\s*=\s*[\"']([^\"']+)[\"']", SPEC).group(1)
    assert not re.search(r"_v?\d+\.", name), name
    assert "{" not in name, "the name must be a constant, not built per build"


def test_the_installer_has_a_stable_app_id():
    """Inno keys upgrades and the uninstall entry off AppId. Changing it orphans
    every existing installation."""
    assert re.search(r"AppId=\{\{[0-9A-F-]{36}\}", INSTALLER)


def test_the_installer_is_published_under_paleobytes():
    assert "AppPublisher=PaleoBytes" in INSTALLER
    assert r"DefaultDirName={userpf}\PaleoBytes\PTMGenerator2" in INSTALLER


def test_the_installer_needs_no_administrator():
    assert "PrivilegesRequired=lowest" in INSTALLER


def test_the_installer_does_not_touch_the_data_directory():
    """Preferences and logs live in %USERPROFILE%\\PaleoBytes\\PTMGenerator2 and
    must survive an uninstall. Anything the installer places there it also
    removes -- so it must place nothing there. Directives only; the header
    comment explains this and would otherwise trip the check."""
    directives = [
        line for line in INSTALLER.splitlines() if line.strip() and not line.startswith(";")
    ]
    assert not [line for line in directives if "userprofile" in line.lower()]


def test_every_placeholder_ci_fills_is_one_ci_knows_about():
    filled = {"VERSION", "DIST_PATH", "OUTPUT_DIR"}
    assert set(re.findall(r"\{\{([A-Z_]+)\}\}", INSTALLER)) == filled


def test_the_workflow_substitutes_every_placeholder():
    workflow = (ROOT / ".github/workflows/reusable_build.yml").read_text(encoding="utf-8")
    for placeholder in re.findall(r"\{\{([A-Z_]+)\}\}", INSTALLER):
        assert f'Replace("{{{{{placeholder}}}}}"' in workflow or (
            f'.Replace("{{{{{placeholder}}}}}"' in workflow
        ), f"{placeholder} is never substituted"

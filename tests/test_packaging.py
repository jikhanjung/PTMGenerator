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


#: Bundled files the spec writes itself, so they are absent from a checkout.
#: Each must be paired with a test below proving the spec really does produce
#: it -- otherwise this set is just a way to silence the check.
GENERATED = {"build_info.json"}


def test_the_datas_globs_match_something():
    """('icons/*.png', 'icons') style entries must actually collect files."""
    for pattern, _dest in re.findall(r"\('([^']+)',\s*'([^']+)'\)", SPEC):
        if pattern in GENERATED:
            continue
        assert list(ROOT.glob(pattern)), f"the spec bundles {pattern}, which matches nothing"


def test_the_spec_writes_the_build_metadata_it_bundles():
    """The other half of the waiver above.

    `build_info.json` is not in the tree because the spec stamps it at build
    time. If that ever stops happening the bundle silently loses it and the
    About dialog reports "local" from a released executable -- so assert the
    spec both writes it and hands it to PyInstaller.
    """
    assert "build_info.json" in SPEC
    assert re.search(r'Path\(SPECPATH, "build_info\.json"\)\.write_text', SPEC)
    assert re.search(r"\('build_info\.json',\s*'\.'\)", SPEC)


def test_the_build_number_is_not_taken_from_a_per_workflow_counter():
    # github.run_number differs between build.yml and release.yml, so the same
    # commit would stamp two different build numbers. The commit count does not.
    assert "rev-list" in SPEC
    assert "run_number" not in SPEC


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
    """Preferences live in %LOCALAPPDATA%\\PaleoBytes\\PTMGenerator2 and the log
    in %USERPROFILE%\\PaleoBytes\\PTMGenerator2 -- two locations since devlog
    014. Both must survive an uninstall, and anything the installer places
    there it also removes -- so it must place nothing in either. Directives
    only; the header comment explains this and would otherwise trip the check.

    Note {userpf} expands to %LOCALAPPDATA%\\Programs, which is where the
    payload is *supposed* to go; matching on the literal string leaves it
    alone."""
    directives = [
        line for line in INSTALLER.splitlines() if line.strip() and not line.startswith(";")
    ]
    stray = [
        line
        for line in directives
        if "userprofile" in line.lower() or "localappdata" in line.lower()
    ]
    assert not stray


def test_the_license_the_installer_shows_exists():
    """ISCC aborts on a missing LicenseFile, and the wizard is the only place
    the MIT terms are shown to someone who never opens the repository. The path
    is absolute once CI substitutes DIST_PATH, so resolve it the same way."""
    match = re.search(r"^LicenseFile=(.+)$", INSTALLER, re.MULTILINE)
    assert match, "the installer no longer shows the licence"
    named = match.group(1).replace(r"{{DIST_PATH}}", str(ROOT / "dist")).replace("\\", "/")
    assert Path(named).resolve() == (ROOT / "LICENSE").resolve()
    assert (ROOT / "LICENSE").is_file()


def test_every_placeholder_ci_fills_is_one_ci_knows_about():
    filled = {"VERSION", "DIST_PATH", "OUTPUT_DIR"}
    assert set(re.findall(r"\{\{([A-Z_]+)\}\}", INSTALLER)) == filled


def test_the_workflow_substitutes_every_placeholder():
    workflow = (ROOT / ".github/workflows/reusable_build.yml").read_text(encoding="utf-8")
    for placeholder in re.findall(r"\{\{([A-Z_]+)\}\}", INSTALLER):
        assert f'Replace("{{{{{placeholder}}}}}"' in workflow or (
            f'.Replace("{{{{{placeholder}}}}}"' in workflow
        ), f"{placeholder} is never substituted"


# -- the release workflow ----------------------------------------------------

RELEASE = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
BUILD = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
REUSABLE = (ROOT / ".github" / "workflows" / "reusable_build.yml").read_text(encoding="utf-8")


def _directives(workflow):
    """The workflow with its comments removed.

    Necessary because these files *explain* why they do not use
    `github.run_number`, and a check reading the prose would fail on the
    comment that documents the fix.
    """
    return "\n".join(line for line in workflow.splitlines() if not line.strip().startswith("#"))


@pytest.mark.parametrize("workflow", [RELEASE, BUILD], ids=["release", "build"])
def test_both_build_paths_derive_the_build_number_the_same_way(workflow):
    """One commit, one build number, whichever workflow built it.

    github.run_number counts runs of a single workflow, so build.yml and
    release.yml would stamp different numbers into identical builds.
    """
    assert "git rev-list --count HEAD" in workflow
    # `rev-list --count` on a shallow clone returns 1. actions/checkout is
    # shallow by default, so this line is what makes the number real.
    assert "fetch-depth: 0" in workflow
    assert "github.run_number" not in _directives(workflow)


def test_the_build_number_reaches_the_bundle_and_the_installer():
    # The spec reads BUILD_NUMBER to stamp build_info.json; Inno reads it for
    # the installer filename. Setting it for only one was the earlier bug.
    assert REUSABLE.count("BUILD_NUMBER") >= 2
    assert "inputs.build_number" in REUSABLE
    assert "github.run_number" not in _directives(REUSABLE)


def test_the_release_publishes_checksums():
    assert "sha256sum" in RELEASE
    assert "SHA256SUMS.txt" in RELEASE

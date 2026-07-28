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
        sizes = {size for size in ico.info.get("sizes", ())}
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

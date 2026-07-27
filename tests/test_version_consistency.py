"""version.py is the single source of truth; nothing may drift from it."""

import re
from pathlib import Path

import pytest
import semver

import version

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parent.parent


def test_version_is_valid_semver():
    semver.VersionInfo.parse(version.__version__)


def test_version_info_matches():
    parsed = semver.VersionInfo.parse(version.__version__)
    assert version.__version_info__ == (parsed.major, parsed.minor, parsed.patch)


def test_pyproject_takes_its_version_from_version_py():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'dynamic = ["version"]' in text
    assert 'version = {attr = "version.__version__"}' in text


def test_spec_derives_the_exe_name_from_version_py():
    """The build must not carry a second, hand-edited version number."""
    text = (ROOT / "PTMGenerator2.spec").read_text(encoding="utf-8")
    assert "__version__" in text
    assert not re.search(r"name\s*=\s*['\"]PTMGenerator2_v\d", text), (
        "the spec hardcodes a version instead of reading version.py"
    )


def test_changelog_mentions_the_current_version():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert version.__version__ in text, (
        f"CHANGELOG.md has no entry for {version.__version__}; run scripts/bump_version.py"
    )

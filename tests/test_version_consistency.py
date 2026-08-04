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


# -- brand identity ----------------------------------------------------------
#
# These strings are keys, not labels: the vendor is a segment of the config
# directory, the data directory, the install directory and the Start-Menu
# group. Changing one orphans an existing installation's settings, so each is
# pinned to the single source rather than repeated as a literal.

INSTALLER = (ROOT / "installer" / "PTMGenerator2.iss.template").read_text(encoding="utf-8")


def test_the_installer_publisher_is_the_vendor():
    assert f"AppPublisher={version.COMPANY_NAME}" in INSTALLER


def test_the_installer_paths_carry_the_vendor():
    assert f"{{userpf}}\\{version.COMPANY_NAME}\\{version.PROGRAM_NAME}" in INSTALLER
    assert f"{{userprograms}}\\{version.COMPANY_NAME}\\{version.PROGRAM_NAME}" in INSTALLER


def test_the_application_tells_qt_who_it_is():
    """Qt has its own idea of the organization and derives locations from it.

    Left unset it defaults to the executable name, which is how a project ends
    up with several organization strings and a Qt-resolved path nothing else
    writes to.
    """
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt5.QtWidgets import QApplication

    from ui.app import PtmApplication

    app = QApplication.instance() or PtmApplication([])
    assert app.organizationName() == version.COMPANY_NAME
    assert app.applicationName() == version.PROGRAM_NAME
    assert app.applicationVersion() == version.__version__


# -- the supported runtime ---------------------------------------------------

PYPROJECT = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
TEST_WORKFLOW = (ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")


def _supported_versions():
    """The Python versions `requires-python` admits, as (major, minor)."""
    spec = re.search(r'^requires-python\s*=\s*"([^"]+)"', PYPROJECT, re.MULTILINE).group(1)
    lower = re.search(r">=\s*3\.(\d+)", spec)
    upper = re.search(r"<\s*3\.(\d+)", spec)
    assert lower, f"no lower bound in {spec!r}"
    # No upper bound means every future release is claimed. That is the state
    # this test exists to stop returning to.
    assert upper, f"{spec!r} claims every Python above 3.{lower.group(1)}, tested or not"
    return [(3, minor) for minor in range(int(lower.group(1)), int(upper.group(1)))]


def _matrix_versions():
    return {(3, int(minor)) for minor in re.findall(r"python-version:\s*'3\.(\d+)'", TEST_WORKFLOW)}


def test_every_python_the_project_claims_is_one_ci_runs():
    """The guide's keystone check, stated as a contract.

    A desktop app's production environment is the user's machine, so a version
    in `requires-python` that no CI leg exercises is a claim nobody verified.
    Widening one of these without the other is what this catches.
    """
    claimed = set(_supported_versions())
    tested = _matrix_versions()
    assert claimed <= tested, f"claimed but never tested: {sorted(claimed - tested)}"


def test_the_classifiers_list_the_versions_the_project_claims():
    for _major, minor in _supported_versions():
        assert f"Programming Language :: Python :: 3.{minor}" in PYPROJECT


def test_the_lockfiles_are_compiled_for_a_supported_version():
    lock_args = (ROOT / "Makefile").read_text(encoding="utf-8")
    pinned = re.search(r"--python-version\s+3\.(\d+)", lock_args)
    assert pinned, "make lock no longer pins a Python version"
    assert (3, int(pinned.group(1))) in _supported_versions()

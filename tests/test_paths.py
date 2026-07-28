"""Where user data lives.

The rule these all serve: nothing the application writes may land inside the
install directory, because the installer removes that on uninstall.
"""

import datetime
import os

import pytest

from core import paths
from version import COMPANY_NAME, PROGRAM_NAME

pytestmark = pytest.mark.unit


@pytest.fixture
def unset_override(monkeypatch):
    monkeypatch.delenv(paths.DATA_DIR_ENV, raising=False)


def test_the_data_directory_follows_the_paleobytes_convention(unset_override):
    """~/PaleoBytes/PTMGenerator2 -- %USERPROFILE%\\PaleoBytes\\... on Windows,
    which is where the sibling projects put theirs."""
    assert paths.data_dir().endswith(os.path.join(COMPANY_NAME, PROGRAM_NAME))


def test_the_data_directory_is_under_the_home_directory(unset_override):
    assert paths.data_dir().startswith(os.path.expanduser("~"))


def test_the_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path))
    assert paths.data_dir() == str(tmp_path)


def test_the_override_expands_a_tilde(monkeypatch):
    monkeypatch.setenv(paths.DATA_DIR_ENV, "~/somewhere")
    assert paths.data_dir() == os.path.join(os.path.expanduser("~"), "somewhere")


def test_the_override_is_read_on_every_call(monkeypatch, tmp_path):
    """Resolved per call, not at import: a test that sets the variable after
    importing the module must still be honoured."""
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path / "first"))
    first = paths.data_dir()
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path / "second"))
    assert paths.data_dir() != first


def test_everything_lives_under_the_data_directory(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path))
    for path in (paths.preferences_path(), paths.log_dir(), paths.log_path()):
        assert path.startswith(str(tmp_path))


def test_the_preferences_file_is_json(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path))
    assert os.path.basename(paths.preferences_path()) == "preferences.json"


# -- the log, one file per day ---------------------------------------------


def test_the_log_is_named_for_the_day(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path))
    path = paths.log_path(datetime.date(2026, 7, 28))
    assert os.path.basename(path) == "PTMGenerator2_20260728.log"


def test_a_different_day_is_a_different_file(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path))
    assert paths.log_path(datetime.date(2026, 7, 27)) != paths.log_path(datetime.date(2026, 7, 28))


def test_the_log_defaults_to_today(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path))
    assert paths.log_path() == paths.log_path(datetime.date.today())


def test_the_log_sits_in_a_logs_subdirectory(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path))
    assert os.path.dirname(paths.log_path()) == str(tmp_path / "logs")


# -- creating them ----------------------------------------------------------


def test_ensure_directories_creates_both(monkeypatch, tmp_path):
    target = tmp_path / "fresh"
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(target))
    paths.ensure_directories()
    assert target.is_dir()
    assert (target / "logs").is_dir()


def test_ensure_directories_is_repeatable(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path / "fresh"))
    paths.ensure_directories()
    paths.ensure_directories()  # must not raise


def test_ensure_directories_leaves_existing_content_alone(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path))
    (tmp_path / "preferences.json").write_text("{}", encoding="utf-8")
    paths.ensure_directories()
    assert (tmp_path / "preferences.json").read_text(encoding="utf-8") == "{}"

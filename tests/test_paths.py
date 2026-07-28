"""Where preferences and logs live.

Two rules these serve. Nothing the application writes may land inside the
install directory, because the installer removes that on uninstall. And
**configuration does not live with data** — see the PaleoBytes convention in
`devlog/20260728_014_config_location_convention.md`.
"""

import datetime
import os

import platformdirs
import pytest

from core import paths
from version import COMPANY_NAME, PROGRAM_NAME

pytestmark = pytest.mark.unit


@pytest.fixture
def unset_override(monkeypatch):
    monkeypatch.delenv(paths.DATA_DIR_ENV, raising=False)
    monkeypatch.delenv(paths.CONFIG_DIR_ENV, raising=False)


def test_the_data_directory_follows_the_paleobytes_convention(unset_override):
    """~/PaleoBytes/PTMGenerator2 -- %USERPROFILE%\\PaleoBytes\\... on Windows,
    which is where the sibling projects put theirs."""
    assert paths.data_dir().endswith(os.path.join(COMPANY_NAME, PROGRAM_NAME))


# -- configuration, which does not live with the data ----------------------


def test_configuration_is_not_inside_the_data_directory(unset_override):
    """The rule the whole convention exists for. Settings are machine-local
    state; data is not. Keeping them apart is also what would let the data
    location become configurable without the settings needing to be found
    inside the directory they configure."""
    assert not paths.config_dir().startswith(paths.data_dir())
    assert not paths.preferences_path().startswith(paths.data_dir())


def test_configuration_sits_under_the_os_config_location(unset_override):
    """platformdirs, not a hand-assembled path: XDG_CONFIG_HOME fallbacks and
    localised Windows folder names are its job, not ours."""
    assert paths.config_dir().startswith(platformdirs.user_config_dir())


def test_configuration_carries_the_vendor_segment(unset_override):
    """Joined here, not passed as platformdirs' appauthor -- that is honoured on
    Windows only, so macOS and Linux would silently lose the grouping."""
    assert paths.config_dir().endswith(os.path.join(COMPANY_NAME, PROGRAM_NAME))


def test_the_preferences_file_is_in_the_config_directory(unset_override):
    assert os.path.dirname(paths.preferences_path()) == paths.config_dir()


def test_the_config_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.CONFIG_DIR_ENV, str(tmp_path))
    assert paths.config_dir() == str(tmp_path)


def test_the_two_overrides_are_independent(monkeypatch, tmp_path):
    """A test may care about one and not the other."""
    monkeypatch.setenv(paths.CONFIG_DIR_ENV, str(tmp_path / "c"))
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path / "d"))
    assert paths.config_dir() == str(tmp_path / "c")
    assert paths.data_dir() == str(tmp_path / "d")


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


def test_the_log_lives_under_the_data_directory(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path))
    for path in (paths.log_dir(), paths.log_path()):
        assert path.startswith(str(tmp_path))


def test_the_log_stays_with_the_data(unset_override, monkeypatch):
    """Deliberately not moved to the config directory with the preferences:
    logging is set up before preferences are read, so a log location that
    depended on a setting would need a discarded first log or a double
    initialisation."""
    monkeypatch.delenv(paths.CONFIG_DIR_ENV, raising=False)
    assert paths.log_dir().startswith(paths.data_dir())
    assert not paths.log_dir().startswith(paths.config_dir())


def test_the_preferences_file_is_json(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.CONFIG_DIR_ENV, str(tmp_path))
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


def test_ensure_directories_creates_all_of_them(monkeypatch, tmp_path):
    target = tmp_path / "fresh"
    config = tmp_path / "conf"
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(target))
    monkeypatch.setenv(paths.CONFIG_DIR_ENV, str(config))
    paths.ensure_directories()
    assert target.is_dir()
    assert (target / "logs").is_dir()
    assert config.is_dir()


def test_ensure_directories_is_repeatable(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path / "fresh"))
    monkeypatch.setenv(paths.CONFIG_DIR_ENV, str(tmp_path / "conf"))
    paths.ensure_directories()
    paths.ensure_directories()  # must not raise


def test_ensure_directories_leaves_existing_content_alone(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.CONFIG_DIR_ENV, str(tmp_path))
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path))
    (tmp_path / "preferences.json").write_text("{}", encoding="utf-8")
    paths.ensure_directories()
    assert (tmp_path / "preferences.json").read_text(encoding="utf-8") == "{}"

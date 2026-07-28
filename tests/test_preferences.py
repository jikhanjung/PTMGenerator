"""The JSON preferences store, and the QSettings file it takes over from."""

import json
import pathlib

import pytest

from core import settings as prefs
from core.preferences import Preferences, legacy_ini_path, migrate_from_ini

pytestmark = pytest.mark.unit


@pytest.fixture
def store(tmp_path):
    return Preferences(str(tmp_path / "preferences.json"))


# -- the store --------------------------------------------------------------


def test_a_missing_file_reads_as_empty(tmp_path):
    assert Preferences(str(tmp_path / "nothing.json")).as_dict() == {}


def test_a_value_round_trips_through_the_file(store):
    store.setValue(prefs.SERIAL_PORT, "COM3")
    store.sync()
    assert Preferences(store.path).value(prefs.SERIAL_PORT) == "COM3"


def test_the_default_is_returned_for_a_missing_key(store):
    assert store.value("nope", "fallback") == "fallback"


def test_types_survive_the_round_trip(store):
    """QSettings handed everything back as a string. JSON does not, which is
    what makes the file readable."""
    store.setValue("count", 50)
    store.setValue("polling", 1.5)
    store.setValue("flag", True)
    store.sync()
    reopened = Preferences(store.path)
    assert reopened.value("count") == 50
    assert reopened.value("polling") == 1.5
    assert reopened.value("flag") is True


def test_a_slash_in_a_key_nests(store):
    store.setValue("WindowGeometry/MainWindow", [1, 2, 3, 4])
    store.sync()
    written = json.loads(pathlib.Path(store.path).read_text(encoding="utf-8"))
    assert written == {"WindowGeometry": {"MainWindow": [1, 2, 3, 4]}}


def test_a_nested_key_reads_back(store):
    store.setValue("WindowGeometry/MainWindow", [1, 2, 3, 4])
    store.sync()
    assert Preferences(store.path).value("WindowGeometry/MainWindow") == [1, 2, 3, 4]


def test_a_missing_branch_gives_the_default(store):
    assert store.value("WindowGeometry/Nothing", "d") == "d"


def test_the_file_is_written_where_the_directory_does_not_exist_yet(tmp_path):
    store = Preferences(str(tmp_path / "made" / "up" / "preferences.json"))
    store.setValue("a", 1)
    store.sync()  # first run has no data directory
    assert Preferences(store.path).value("a") == 1


def test_the_file_is_human_readable(store):
    """The reason for JSON over an ini in %APPDATA%: someone can open it."""
    store.setValue(prefs.LANGUAGE, "ko")
    store.sync()
    text = pathlib.Path(store.path).read_text(encoding="utf-8")
    assert '"language": "ko"' in text
    assert text.endswith("\n")


def test_korean_is_not_escaped(store):
    store.setValue("note", "한국어")
    store.sync()
    assert "한국어" in pathlib.Path(store.path).read_text(encoding="utf-8")


def test_a_corrupt_file_does_not_stop_startup(tmp_path):
    """Every default is reachable from the Preferences dialog; refusing to
    start over an unparseable file would not be."""
    path = tmp_path / "preferences.json"
    path.write_text("{not json", encoding="utf-8")
    assert Preferences(str(path)).as_dict() == {}


def test_a_file_holding_something_other_than_an_object_is_ignored(tmp_path):
    path = tmp_path / "preferences.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert Preferences(str(path)).as_dict() == {}


def test_as_dict_is_a_copy(store):
    store.setValue("a", 1)
    store.as_dict()["a"] = 2
    assert store.value("a") == 1


def test_core_settings_reads_through_it(store):
    """core.settings is written against the QSettings API, and must keep
    working unchanged -- that is why the store mimics it."""
    store.setValue(prefs.NUMBER_OF_LEDS, "24")
    assert prefs.read_int(store, prefs.NUMBER_OF_LEDS) == 24
    assert prefs.read_int(store, prefs.RETRY_COUNT) == prefs.DEFAULTS[prefs.RETRY_COUNT]


# -- migration from the QSettings ini ---------------------------------------


def ini(tmp_path, text):
    path = tmp_path / "old.ini"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_nothing_to_migrate_is_not_an_error(store, tmp_path):
    assert migrate_from_ini(store, str(tmp_path / "absent.ini")) is False


def test_general_keys_arrive_unnested(store, tmp_path):
    path = ini(tmp_path, "[General]\nlanguage=ko\nserial_port=COM7\n")
    assert migrate_from_ini(store, path) is True
    assert store.value(prefs.LANGUAGE) == "ko"
    assert store.value(prefs.SERIAL_PORT) == "COM7"


def test_key_case_is_preserved(store, tmp_path):
    """configparser lower-cases keys by default, and Number_of_LEDs would
    silently become number_of_leds -- a setting that then reads as its default."""
    path = ini(tmp_path, "[General]\nNumber_of_LEDs=24\n")
    migrate_from_ini(store, path)
    assert store.value(prefs.NUMBER_OF_LEDS) == 24


def test_sections_become_nested_keys(store, tmp_path):
    path = ini(tmp_path, "[IsMaximized]\nMainWindow=false\n")
    migrate_from_ini(store, path)
    assert store.value("IsMaximized/MainWindow") is False


def test_numbers_are_typed(store, tmp_path):
    path = ini(tmp_path, "[General]\nRetryCount=5\npost_shutter_polling=1.5\n")
    migrate_from_ini(store, path)
    assert store.value(prefs.RETRY_COUNT) == 5
    assert store.value(prefs.POST_SHUTTER_POLLING) == 1.5


def test_qt_typed_values_are_dropped(store, tmp_path):
    """QSettings wrote geometry as @Rect(...), which nothing here can read.
    Importing it as a string would leave the window trying to unpack it."""
    path = ini(tmp_path, "[WindowGeometry]\nMainWindow=@Rect(100 100 1400 800)\n")
    migrate_from_ini(store, path)
    assert store.value("WindowGeometry/MainWindow") is None


def test_a_dropped_value_leaves_no_trace_in_the_file(store, tmp_path):
    """Not written as an explicit null: it would read the same, but sit in the
    file looking like a setting someone chose."""
    path = ini(tmp_path, "[General]\nlanguage=ko\n[WindowGeometry]\nMainWindow=@Rect(1 2 3 4)\n")
    migrate_from_ini(store, path)
    assert store.as_dict() == {"language": "ko"}


def test_migration_does_not_overwrite_what_is_already_set(store, tmp_path):
    store.setValue(prefs.LANGUAGE, "en")
    path = ini(tmp_path, "[General]\nlanguage=ko\n")
    migrate_from_ini(store, path)
    assert store.value(prefs.LANGUAGE) == "en"


def test_migration_persists(store, tmp_path):
    path = ini(tmp_path, "[General]\nlanguage=ko\n")
    migrate_from_ini(store, path)
    assert Preferences(store.path).value(prefs.LANGUAGE) == "ko"


def test_running_migration_twice_changes_nothing(store, tmp_path):
    """It runs on every start, so the second time must be a no-op rather than
    resurrecting a setting the user has since changed."""
    path = ini(tmp_path, "[General]\nlanguage=ko\n")
    migrate_from_ini(store, path)
    store.setValue(prefs.LANGUAGE, "en")
    store.sync()
    assert migrate_from_ini(store, path) is False
    assert store.value(prefs.LANGUAGE) == "en"


def test_an_unreadable_ini_is_survivable(store, tmp_path):
    path = ini(tmp_path, "this is not an ini file at all\n")
    assert migrate_from_ini(store, path) is False


def test_the_legacy_path_is_the_qsettings_one(monkeypatch, tmp_path):
    """Where QSettings(IniFormat, UserScope, "PaleoBytes", "PTMGenerator2")
    actually wrote, per platform."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr("core.preferences.sys.platform", "linux")
    assert legacy_ini_path() == str(tmp_path / "PaleoBytes" / "PTMGenerator2.conf")


def test_the_legacy_path_on_windows(monkeypatch):
    monkeypatch.setenv("APPDATA", r"C:\Users\x\AppData\Roaming")
    monkeypatch.setattr("core.preferences.sys.platform", "win32")
    assert legacy_ini_path().endswith("PTMGenerator2.ini")
    assert "PaleoBytes" in legacy_ini_path()

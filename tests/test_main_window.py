"""The main window: settings, the capture table, and the capture loop."""

import csv
import os
from unittest.mock import MagicMock, patch

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItem
from PyQt5.QtWidgets import QFileDialog, QMessageBox

import version
from core import ptm_builder
from core.image_data import MISSING, CaptureSlot
from ui.main_window import PTMGeneratorMainWindow

pytestmark = pytest.mark.ui


# -- settings --------------------------------------------------------------


def test_defaults(main_window):
    assert main_window.number_of_LEDs == 50
    assert main_window.ptm_fitter == "ptmfitter.exe"
    assert not main_window.serial.is_open


def test_window_title_carries_the_version(main_window):
    assert version.__version__ in main_window.windowTitle()


def test_settings_are_read_back(main_window):
    main_window.m_app.settings.setValue("Number_of_LEDs", "24")
    main_window.m_app.settings.setValue("light_position_adjustment", "15")
    main_window.m_app.settings.sync()
    main_window.read_settings()
    assert main_window.number_of_LEDs == 24
    assert main_window.light_position_adjustment == 15


def test_selected_rows_defaults_to_empty(main_window):
    # Retake used to raise AttributeError before any row was ever selected.
    assert main_window.selected_rows == []


# -- capture table ---------------------------------------------------------


@pytest.fixture
def window_in(main_window, workdir):
    main_window.monitor_root = str(workdir)
    main_window.edtDirectory.setText(str(workdir))
    return main_window


def test_update_csv_writes_every_slot(window_in, workdir):
    window_in.image_data = [
        CaptureSlot(0, str(workdir), "a.jpg", True),
        CaptureSlot(1, MISSING, MISSING, False),
    ]
    window_in.update_csv()
    with open(workdir / "image_data.csv", newline="") as fh:
        assert list(csv.reader(fh)) == [
            ["0", str(workdir), "a.jpg", "True"],
            ["1", MISSING, MISSING, "False"],
        ]


def test_load_csv_data_fills_the_table(window_in, workdir):
    with open(workdir / "image_data.csv", "w", newline="") as fh:
        csv.writer(fh).writerows(
            [[0, str(workdir), "a.jpg", "True"], [1, str(workdir), "b.jpg", "False"]]
        )
    window_in.load_csv_data()
    assert window_in.image_data == [
        CaptureSlot(0, str(workdir), "a.jpg", True),
        CaptureSlot(1, str(workdir), "b.jpg", False),
    ]
    assert window_in.image_model.item(0, 0).checkState() == Qt.Checked
    assert window_in.image_model.item(1, 0).checkState() == Qt.Unchecked
    assert window_in.image_model.item(1, 1).text() == "b.jpg"


def test_unchecking_clears_the_include_flag(window_in, workdir):
    window_in.image_data = [
        CaptureSlot(0, str(workdir), "a.jpg", True),
        CaptureSlot(1, str(workdir), "b.jpg", True),
    ]
    for name in ("a.jpg", "b.jpg"):
        box = QStandardItem()
        box.setCheckable(True)
        box.setCheckState(Qt.Checked)
        window_in.image_model.appendRow([box, QStandardItem(name)])

    window_in.image_model.item(1, 0).setCheckState(Qt.Unchecked)
    window_in.sync_checkbox_states_to_image_data()

    assert [s.include for s in window_in.image_data] == [True, False]
    # Index, directory and filename must survive the sync.
    assert window_in.image_data[0][:3] == (0, str(workdir), "a.jpg")


def test_clear_image_data_resets_the_table(window_in):
    window_in.image_data = [CaptureSlot(0, "d", "a.jpg", True)]
    window_in.image_model.appendRow([QStandardItem(), QStandardItem("a.jpg")])
    window_in.clear_image_data()
    assert window_in.image_data == []
    assert window_in.image_model.rowCount() == 0
    assert [
        window_in.image_model.horizontalHeaderItem(c).text()
        for c in range(window_in.image_model.columnCount())
    ] == ["Include", "Filename"]


def test_record_slot_appends_a_missing_shot(window_in):
    window_in.record_slot(0, None)
    assert window_in.image_data == [CaptureSlot(0, MISSING, MISSING, False)]
    assert window_in.image_model.item(0, 0).checkState() == Qt.Unchecked


def test_record_slot_appends_a_captured_shot(window_in, workdir):
    path = str(workdir / "shot.jpg")
    window_in.record_slot(0, path)
    assert window_in.image_data == [CaptureSlot(0, str(workdir), "shot.jpg", True)]
    assert window_in.image_model.item(0, 0).checkState() == Qt.Checked


def test_record_slot_overwrites_on_retake(window_in, workdir):
    window_in.record_slot(0, None)
    window_in.record_slot(0, str(workdir / "later.jpg"))
    assert len(window_in.image_data) == 1
    assert window_in.image_data[0].filename == "later.jpg"


# -- capture control -------------------------------------------------------


@pytest.fixture
def connected(main_window):
    """A window that believes a controller is attached."""
    port = MagicMock()
    main_window.serial._serial = port
    main_window.serial.port = "/dev/ttyFAKE"
    return main_window, port


def test_take_all_pictures_queues_every_led(connected):
    window, _port = connected
    window.number_of_LEDs = 6
    window.take_all_pictures()
    try:
        assert window.session.current_index == 0
        assert window.session.queue == [1, 2, 3, 4, 5]
        assert window.timer.isActive()
    finally:
        window.timer.stop()


def test_take_all_pictures_clears_a_previous_run(connected):
    window, _port = connected
    window.number_of_LEDs = 3
    window.image_data = [CaptureSlot(0, "somewhere", "stale.jpg", True)]
    window.take_all_pictures()
    try:
        assert window.image_data == []
    finally:
        window.timer.stop()


def test_retake_queues_selected_rows_in_order(connected):
    window, _port = connected
    window.selected_rows = [7, 2, 5]
    window.on_retake_picture_triggered()
    try:
        assert window.session.current_index == 2
        assert window.session.queue == [5, 7]
    finally:
        window.timer.stop()


def test_retake_without_a_selection_does_nothing(connected):
    window, _port = connected
    window.selected_rows = []
    window.on_retake_picture_triggered()
    assert not window.timer.isActive()


def test_pause_then_continue_toggles_the_timer(main_window):
    main_window.timer.start(1000)
    try:
        main_window.pause_continue_process()
        assert not main_window.timer.isActive()
        main_window.pause_continue_process()
        assert main_window.timer.isActive()
    finally:
        main_window.timer.stop()


def test_stop_halts_the_run_and_turns_the_leds_off(connected):
    window, port = connected
    window.timer.start(1000)
    window.stop_process()
    assert not window.timer.isActive()
    assert window.session is None
    port.write.assert_called_once_with(b"<OFF>")


def test_a_tick_with_no_session_stops_the_timer(main_window):
    main_window.session = None
    main_window.timer.start(1000)
    main_window.take_picture_process()
    assert not main_window.timer.isActive()


def test_finishing_a_run_writes_the_csv_and_releases_the_port(connected, workdir):
    window, _port = connected
    window.monitor_root = str(workdir)
    window.number_of_LEDs = 1
    window.post_shutter_polling = 0
    window.auto_retake_maximum = 0
    window.take_all_pictures()
    # Nothing ever lands, so the single slot times out and the run ends.
    for _ in range(12):
        if window.session is None:
            break
        window.take_picture_process()
    assert window.session is None
    assert not window.timer.isActive()
    assert os.path.exists(workdir / "image_data.csv")
    assert not window.serial.is_open


# -- no controller attached ------------------------------------------------


@pytest.fixture
def prompt(main_window):
    """Stub the confirm dialog; a real one would block the suite forever."""
    with patch.object(
        PTMGeneratorMainWindow, "confirm_capture_without_controller", return_value=False
    ) as stub:
        yield main_window, stub


def test_ensure_serial_ready_follows_the_answer(prompt):
    window, stub = prompt
    assert window.ensure_serial_ready() is False
    stub.return_value = True
    assert window.ensure_serial_ready() is True


def test_no_prompt_when_a_port_opens(prompt):
    window, stub = prompt
    window.serial._serial = MagicMock()
    assert window.ensure_serial_ready() is True
    stub.assert_not_called()


def test_take_all_pictures_stops_when_cancelled(prompt):
    window, stub = prompt
    window.take_all_pictures()
    stub.assert_called_once()
    assert not window.timer.isActive()
    assert window.session is None


def test_cancelled_run_leaves_the_capture_table_alone(prompt):
    window, _stub = prompt
    existing = [CaptureSlot(0, "somewhere", "keep-me.jpg", True)]
    window.image_data = list(existing)
    window.take_all_pictures()
    assert window.image_data == existing


def test_retake_stops_when_cancelled(prompt):
    window, stub = prompt
    window.selected_rows = [1, 2]
    window.on_retake_picture_triggered()
    stub.assert_called_once()
    assert not window.timer.isActive()


def test_retake_without_a_selection_does_not_prompt(prompt):
    window, stub = prompt
    window.selected_rows = []
    window.on_retake_picture_triggered()
    stub.assert_not_called()


def test_test_shot_stops_when_cancelled(prompt):
    window, stub = prompt
    with patch.object(window.serial, "shoot") as shoot:
        window.test_shot()
    stub.assert_called_once()
    shoot.assert_not_called()


class TestPromptDialog:
    """The dialog itself, with exec() stubbed so nothing blocks."""

    @pytest.fixture
    def dialog(self, main_window):
        boxes = []
        real_init = QMessageBox.__init__

        def record(box, *a, **kw):
            real_init(box, *a, **kw)
            boxes.append(box)

        with (
            patch.object(QMessageBox, "__init__", record),
            patch.object(QMessageBox, "exec", lambda box: 0),
        ):
            result = main_window.confirm_capture_without_controller()
        return result, boxes[-1]

    def test_offers_continue_and_cancel(self, dialog):
        _result, box = dialog
        labels = [b.text() for b in box.buttons()]
        assert sorted(labels) == ["Cancel", "Continue anyway"]

    def test_cancel_is_the_default(self, dialog):
        _result, box = dialog
        assert box.defaultButton().text() == "Cancel"

    def test_dismissing_without_choosing_counts_as_cancel(self, dialog):
        result, _box = dialog
        assert result is False

    def test_warns_rather_than_merely_informs(self, dialog):
        _result, box = dialog
        assert box.icon() == QMessageBox.Warning

    def test_message_names_the_preferences_location(self, dialog):
        _result, box = dialog
        assert "Preferences" in box.text()


# -- PTM generation --------------------------------------------------------


@pytest.fixture
def ready_to_generate(main_window, workdir):
    capture_dir = workdir / "specimen01"
    capture_dir.mkdir()
    for i in range(3):
        (capture_dir / f"IMG_000{i}.JPG").write_bytes(b"jpeg")
    fitter = workdir / "ptmfitter.exe"
    fitter.touch()
    main_window.monitor_root = str(capture_dir)
    main_window.ptm_fitter = str(fitter)
    main_window.light_position_adjustment = 0
    main_window.image_data = [
        CaptureSlot(i, str(capture_dir), f"IMG_000{i}.JPG", True) for i in range(3)
    ]
    return main_window, capture_dir, str(fitter)


def fitter_that_works(command, cwd):
    """Stands in for PTMfitter, writing its output where it was told."""
    with open(os.path.join(cwd, ptm_builder.STAGED_PTM), "wb") as fh:
        fh.write(b"ptm")


def test_generate_writes_the_lp_and_delivers_the_ptm(ready_to_generate, workdir):
    window, capture_dir, _fitter = ready_to_generate
    out = str(workdir / "결과.ptm")
    with (
        patch.object(QFileDialog, "getSaveFileName", return_value=(out, "")),
        patch.object(ptm_builder, "_subprocess_runner", fitter_that_works),
    ):
        window.generatePTM()

    assert (capture_dir / "specimen01.lp").exists()
    assert os.path.exists(out), "the .ptm must reach a destination the fitter never saw"


def test_the_lp_lists_bare_filenames(ready_to_generate, workdir):
    window, capture_dir, _fitter = ready_to_generate
    with (
        patch.object(QFileDialog, "getSaveFileName", return_value=(str(workdir / "o.ptm"), "")),
        patch.object(ptm_builder, "_subprocess_runner", fitter_that_works),
    ):
        window.generatePTM()
    lines = (capture_dir / "specimen01.lp").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "3"
    assert lines[1].startswith("IMG_0000.jpg ")
    assert str(capture_dir) not in lines[1]


def test_cancelling_the_save_dialog_runs_nothing(ready_to_generate, workdir):
    window, capture_dir, _fitter = ready_to_generate
    with (
        patch.object(QFileDialog, "getSaveFileName", return_value=("", "")),
        patch.object(ptm_builder, "_subprocess_runner") as runner,
    ):
        window.generatePTM()
    runner.assert_not_called()
    assert not (capture_dir / "specimen01.lp").exists()


def test_a_missing_fitter_is_reported(ready_to_generate, workdir):
    window, _capture_dir, _fitter = ready_to_generate
    window.ptm_fitter = str(workdir / "does-not-exist.exe")
    with (
        patch.object(QFileDialog, "getSaveFileName", return_value=(str(workdir / "o.ptm"), "")),
        patch.object(QMessageBox, "critical") as critical,
    ):
        window.generatePTM()
    critical.assert_called_once()


def test_a_fitter_that_produces_nothing_is_reported(ready_to_generate, workdir):
    window, _capture_dir, _fitter = ready_to_generate
    with (
        patch.object(QFileDialog, "getSaveFileName", return_value=(str(workdir / "o.ptm"), "")),
        patch.object(ptm_builder, "_subprocess_runner", lambda command, cwd: None),
        patch.object(QMessageBox, "critical") as critical,
    ):
        window.generatePTM()
    critical.assert_called_once()
    assert "no output" in critical.call_args.args[2]


def test_an_empty_table_is_reported(ready_to_generate, workdir):
    window, _capture_dir, _fitter = ready_to_generate
    window.image_data = []
    with (
        patch.object(QFileDialog, "getSaveFileName", return_value=(str(workdir / "o.ptm"), "")),
        patch.object(QMessageBox, "critical") as critical,
    ):
        window.generatePTM()
    critical.assert_called_once()


class TestCaptureDirectoryAdoption:
    """The chosen folder is watched; the folder shots land in becomes the working one.

    Canon's EOS Utility (and others) file images into a dated subfolder that
    does not exist until the day's first shot. So at the moment a session
    starts, the only folder the user can pick is the parent, and the run's
    images end up one level down.
    """

    @pytest.fixture
    def watching(self, main_window, workdir):
        main_window.monitor_root = str(workdir)
        main_window.capture_directory = None
        main_window.post_shutter_polling = 0
        main_window.last_checked = 1000
        return main_window, workdir

    @staticmethod
    def shoot_into(directory, name="IMG_0001.JPG", mtime=5000):
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        path.touch()
        os.utime(path, (mtime, mtime))
        return str(path)

    def test_a_shot_in_a_dated_subfolder_is_found(self, watching):
        window, root = watching
        expected = self.shoot_into(root / "2026-07-28")
        assert window.poll_for_image() == expected

    def test_that_subfolder_becomes_the_working_directory(self, watching):
        window, root = watching
        self.shoot_into(root / "2026-07-28")
        window.poll_for_image()
        assert window.capture_directory == str(root / "2026-07-28")
        assert window.working_directory == str(root / "2026-07-28")

    def test_the_working_directory_is_the_root_until_something_lands(self, watching):
        window, root = watching
        assert window.working_directory == str(root)

    def test_the_capture_folder_is_shown_above_the_list(self, watching):
        window, root = watching
        self.shoot_into(root / "2026-07-28")
        window.poll_for_image()
        assert str(root / "2026-07-28") in window.lblCaptureDirectory.text()

    def test_before_anything_lands_the_label_says_so(self, watching):
        window, root = watching
        window.update_capture_directory_label()
        text = window.lblCaptureDirectory.text()
        assert "Waiting" in text
        assert str(root) in text

    def test_the_top_field_keeps_showing_the_watched_folder(self, watching):
        window, root = watching
        window.edtDirectory.setText(str(root))
        self.shoot_into(root / "2026-07-28")
        window.poll_for_image()
        assert window.edtDirectory.text() == str(root), (
            "the monitored root must stay visible once a subfolder is adopted"
        )

    def test_later_polls_stay_in_the_adopted_folder(self, watching):
        window, root = watching
        self.shoot_into(root / "2026-07-28", "IMG_0001.JPG", 5000)
        window.poll_for_image()
        # A stray image elsewhere under the root must not be picked up now that
        # the run's folder is known.
        self.shoot_into(root / "elsewhere", "IMG_9999.JPG", 6000)
        assert window.poll_for_image() is None

    def test_the_csv_goes_to_the_adopted_folder(self, watching):
        window, root = watching
        self.shoot_into(root / "2026-07-28")
        window.poll_for_image()
        window.image_data = [CaptureSlot(0, window.capture_directory, "IMG_0001.jpg", True)]
        window.update_csv()
        assert (root / "2026-07-28" / "image_data.csv").exists()
        assert not (root / "image_data.csv").exists()

    def test_a_shot_directly_in_the_root_still_works(self, watching):
        window, root = watching
        expected = self.shoot_into(root)
        assert window.poll_for_image() == expected
        assert window.capture_directory == str(root)

    def test_a_new_run_rediscovers_the_folder(self, main_window, workdir):
        # The dated folder changes daily; a run started after midnight must not
        # keep writing into yesterday's.
        main_window.monitor_root = str(workdir)
        main_window.capture_directory = str(workdir / "2026-07-27")
        main_window.serial._serial = MagicMock()
        main_window.number_of_LEDs = 2
        main_window.take_all_pictures()
        try:
            assert main_window.capture_directory is None
        finally:
            main_window.timer.stop()

    def test_opening_a_directory_clears_a_previous_adoption(self, main_window, workdir):
        main_window.capture_directory = str(workdir / "old")
        with patch.object(QFileDialog, "getExistingDirectory", return_value=str(workdir)):
            main_window.on_action_open_directory_triggered()
        assert main_window.capture_directory is None
        assert main_window.monitor_root == str(workdir)

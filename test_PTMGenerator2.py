"""Tests for PTMGenerator2.

Run with:

    python -m unittest test_PTMGenerator2 -v

No display is required: the module forces Qt's "offscreen" platform plugin
before PyQt5 is imported, so this works over SSH and in CI without xvfb.

Two things make the GUI class testable without hardware:

* QSettings is redirected to a temp directory per test, so the suite never
  reads or writes the real ``PaleoBytes/PTMGenerator2`` settings.
* ``PTMGeneratorMainWindow.initialize_variables`` replaces ``sys.stdout`` with
  an OutputRedirector and opens ``output.log`` in the current directory, so
  tests that build a window run inside a temp cwd and restore stdout after.

Logic that touches neither Qt nor hardware (light-position maths, interval
detection) is exercised through ``bare_window()``, which builds an uninitialised
instance and sets only the attributes the method under test reads.
"""

import contextlib
import csv
import io
import math
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Must be set before PyQt5 is imported.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QSettings, Qt, qInstallMessageHandler
from PyQt5.QtGui import QStandardItem
from PyQt5.QtWidgets import QApplication, QFileDialog

import PTMGenerator2
from PTMGenerator2 import (
    OutputRedirector,
    POLAR_LIGHT_LIST,
    PTMGeneratorMainWindow,
    PreferencesWindow,
    resource_path,
    value_to_bool,
)


_EXPECTED_QT_NOISE = (
    # The offscreen platform plugin emits this for every window it shows.
    "propagateSizeHints",
    # show_image() scales whatever the selection lands on; with no captured
    # image on disk that is a null pixmap. Harmless here, noisy in the log.
    "null pixmap",
)


def _filter_qt_messages(mode, context, message):
    if any(fragment in message for fragment in _EXPECTED_QT_NOISE):
        return
    sys.stderr.write(message + "\n")


qInstallMessageHandler(_filter_qt_messages)

# A QApplication must exist before any QWidget, and PyQt5 destroys it as soon as
# the last Python reference goes away — so it is created once here and held for
# the lifetime of the process.
APP = QApplication.instance() or QApplication(sys.argv[:1])
# read_settings() -> update_language() expects the attributes the __main__ block
# attaches to the application object.
if not hasattr(APP, "translator"):
    APP.translator = None
    APP.language = "en"


def get_app():
    """Return the process-wide QApplication."""
    return APP


@contextlib.contextmanager
def quiet():
    """Swallow the app's debug printing so test output stays readable."""
    with contextlib.redirect_stdout(io.StringIO()):
        yield


def bare_window(**attrs):
    """An uninitialised PTMGeneratorMainWindow with only `attrs` set.

    Lets pure-logic methods be called without constructing a real widget.
    """
    win = PTMGeneratorMainWindow.__new__(PTMGeneratorMainWindow)
    for name, value in attrs.items():
        setattr(win, name, value)
    return win


class TempDirMixin(unittest.TestCase):
    """Gives each test a private temp directory and isolated QSettings."""

    def setUp(self):
        super().setUp()
        self.tmpdir = tempfile.mkdtemp(prefix="ptmgen-test-")
        self.addCleanup(shutil.rmtree, self.tmpdir, True)

        settings_dir = os.path.join(self.tmpdir, "settings")
        os.makedirs(settings_dir)
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, settings_dir)


class GuiTestCase(TempDirMixin):
    """Base for tests that construct real windows."""

    def setUp(self):
        super().setUp()
        get_app()
        self._saved_stdout = sys.stdout
        self._saved_cwd = os.getcwd()
        # initialize_variables() opens output.log relative to the cwd.
        self.workdir = os.path.join(self.tmpdir, "work")
        os.makedirs(self.workdir)
        os.chdir(self.workdir)
        self.addCleanup(self._restore)

    def _restore(self):
        os.chdir(self._saved_cwd)
        sys.stdout = self._saved_stdout

    def make_window(self):
        # Constructing the window replaces sys.stdout with its OutputRedirector,
        # which forwards to whatever sys.stdout was at that moment. Point that at
        # a throwaway buffer so the app's debug printing never reaches the
        # console; _restore() puts the real stdout back afterwards.
        sys.stdout = io.StringIO()
        win = PTMGeneratorMainWindow()
        win.redirector.stdout = None
        self.addCleanup(win.close)
        self.addCleanup(win.redirector.close)
        return win


class ResourcePathTests(unittest.TestCase):
    def tearDown(self):
        if hasattr(sys, "_MEIPASS"):
            del sys._MEIPASS

    def test_relative_path_is_anchored_to_cwd(self):
        self.assertEqual(
            resource_path("icons/PTMGenerator2.png"),
            os.path.join(os.path.abspath("."), "icons/PTMGenerator2.png"),
        )

    def test_meipass_takes_precedence_when_frozen(self):
        sys._MEIPASS = os.path.join(os.sep, "frozen", "bundle")
        self.assertEqual(
            resource_path("translations/PTMGenerator2_ko.qm"),
            os.path.join(sys._MEIPASS, "translations/PTMGenerator2_ko.qm"),
        )

    def test_absolute_relative_path_wins_over_the_base(self):
        # os.path.join semantics: an absolute second argument discards the base.
        sys._MEIPASS = os.path.join(os.sep, "frozen", "bundle")
        absolute = os.path.join(os.sep, "etc", "ptmfitter.conf")
        self.assertEqual(resource_path(absolute), absolute)


class ValueToBoolTests(unittest.TestCase):
    def test_qsettings_style_strings(self):
        # QSettings hands back "true"/"false" strings from an .ini file.
        for text in ("true", "True", "TRUE"):
            self.assertIs(value_to_bool(text), True, text)
        for text in ("false", "False", "", "0", "no"):
            self.assertIs(value_to_bool(text), False, text)

    def test_non_strings_use_truthiness(self):
        self.assertIs(value_to_bool(True), True)
        self.assertIs(value_to_bool(False), False)
        self.assertIs(value_to_bool(1), True)
        self.assertIs(value_to_bool(0), False)
        self.assertIs(value_to_bool(None), False)


class OutputRedirectorTests(TempDirMixin):
    def setUp(self):
        super().setUp()
        get_app()  # pyqtSignal needs a QObject-capable environment
        self.log_path = os.path.join(self.tmpdir, "output.log")
        self.redirector = OutputRedirector(self.log_path)
        self.addCleanup(self.redirector.close)

    def test_write_reaches_stdout_file_and_signal(self):
        received = []
        self.redirector.output_written.connect(received.append)
        fake_stdout = MagicMock()
        self.redirector.stdout = fake_stdout

        self.redirector.write("hello")

        fake_stdout.write.assert_called_once_with("hello")
        self.assertEqual(received, ["hello"])
        with open(self.log_path) as fh:
            self.assertEqual(fh.read(), "hello")

    def test_write_tolerates_absent_stdout(self):
        # Under --noconsole PyInstaller builds sys.stdout is None.
        self.redirector.stdout = None
        self.redirector.write("no console here")
        with open(self.log_path) as fh:
            self.assertEqual(fh.read(), "no console here")

    def test_flush_forwards_to_stdout(self):
        fake_stdout = MagicMock()
        self.redirector.stdout = fake_stdout
        self.redirector.flush()
        fake_stdout.flush.assert_called_once_with()

    def test_close_closes_the_log_file(self):
        self.redirector.close()
        self.assertTrue(self.redirector.file.closed)
        self.redirector.close = lambda: None  # cleanup already ran


class LightPositionTests(unittest.TestCase):
    """prepare_light_positions converts the polar LED table to unit vectors."""

    def positions(self, adjustment=0):
        with quiet():
            return bare_window(light_position_adjustment=adjustment).prepare_light_positions()

    def test_one_vector_per_configured_led(self):
        positions = self.positions()
        self.assertEqual(len(positions), len(POLAR_LIGHT_LIST))
        self.assertEqual(len(POLAR_LIGHT_LIST), 50)

    def test_every_vector_is_a_unit_vector(self):
        for i, (x, y, z) in enumerate(self.positions()):
            self.assertAlmostEqual(math.sqrt(x * x + y * y + z * z), 1.0, places=9,
                                   msg="LED %d is not on the unit sphere" % i)

    def test_z_is_cosine_of_elevation(self):
        for (theta, _phi), (_x, _y, z) in zip(POLAR_LIGHT_LIST, self.positions()):
            self.assertAlmostEqual(z, math.cos(math.radians(theta)), places=9)

    def test_all_leds_are_above_the_horizon(self):
        # The dome only has LEDs on the upper hemisphere.
        for _x, _y, z in self.positions():
            self.assertGreater(z, 0.0)

    def test_adjustment_leaves_elevation_untouched(self):
        for (_x, _y, z0), (_x2, _y2, z1) in zip(self.positions(0), self.positions(37)):
            self.assertAlmostEqual(z0, z1, places=9)

    def test_adjustment_rotates_about_the_vertical_axis(self):
        base = self.positions(0)
        turned = self.positions(90)
        for (x0, y0, _z0), (x1, y1, _z1) in zip(base, turned):
            # +90 deg of azimuth maps (x, y) to (-y, x).
            self.assertAlmostEqual(x1, -y0, places=9)
            self.assertAlmostEqual(y1, x0, places=9)

    def test_full_turn_is_identity(self):
        for (x0, y0, z0), (x1, y1, z1) in zip(self.positions(0), self.positions(360)):
            self.assertAlmostEqual(x0, x1, places=9)
            self.assertAlmostEqual(y0, y1, places=9)
            self.assertAlmostEqual(z0, z1, places=9)


class DetectIrregularIntervalsTests(TempDirMixin):
    """Rebuilding the capture slot table from files already on disk.

    Creation times are patched rather than slept for, so the gaps are exact.
    """

    def run_detection(self, names, ctimes):
        for name in names:
            open(os.path.join(self.tmpdir, name), "w").close()
        lookup = {os.path.join(self.tmpdir, n): t for n, t in zip(names, ctimes)}
        win = bare_window()
        with quiet(), patch.object(
            PTMGenerator2.os.path, "getctime", side_effect=lookup.__getitem__
        ):
            return win.detect_irregular_intervals(self.tmpdir)

    def test_empty_directory(self):
        self.assertEqual(self.run_detection([], []), [])

    def test_single_image_yields_no_intervals(self):
        self.assertEqual(self.run_detection(["a.jpg"], [1000]), [])

    def test_evenly_spaced_images_map_one_to_one(self):
        result = self.run_detection(
            ["a.jpg", "b.jpg", "c.jpg", "d.jpg"], [1000, 1010, 1020, 1030]
        )
        self.assertEqual([r[0] for r in result], [0, 1, 2, 3])
        self.assertEqual([r[2] for r in result], ["a.jpg", "b.jpg", "c.jpg", "d.jpg"])
        self.assertTrue(all(r[1] == self.tmpdir for r in result))
        self.assertTrue(all(r[3] is True for r in result))

    def test_result_rows_are_four_tuples(self):
        result = self.run_detection(["a.jpg", "b.jpg"], [1000, 1010])
        self.assertTrue(all(len(row) == 4 for row in result))

    def test_double_gap_inserts_one_placeholder(self):
        # c.jpg arrives 20s after b.jpg while the typical interval is 10s,
        # so one shot went missing in between.
        result = self.run_detection(
            ["a.jpg", "b.jpg", "c.jpg", "d.jpg"], [1000, 1010, 1030, 1040]
        )
        self.assertEqual(len(result), 5)
        placeholders = [row for row in result if row[2] == "-"]
        self.assertEqual(len(placeholders), 1)
        self.assertEqual(placeholders[0][1], "-")
        self.assertIs(placeholders[0][3], False)
        self.assertEqual([r[2] for r in result],
                         ["a.jpg", "b.jpg", "-", "c.jpg", "d.jpg"])

    def test_triple_gap_inserts_two_placeholders(self):
        result = self.run_detection(
            ["a.jpg", "b.jpg", "c.jpg", "d.jpg"], [1000, 1010, 1040, 1050]
        )
        self.assertEqual([r[2] for r in result],
                         ["a.jpg", "b.jpg", "-", "-", "c.jpg", "d.jpg"])

    def test_indices_stay_contiguous_across_a_gap(self):
        result = self.run_detection(
            ["a.jpg", "b.jpg", "c.jpg", "d.jpg"], [1000, 1010, 1030, 1040]
        )
        self.assertEqual([r[0] for r in result], [0, 1, 2, 3, 4])

    def test_non_image_files_are_ignored(self):
        result = self.run_detection(
            ["a.jpg", "notes.txt", "b.jpg", "image_data.csv"],
            [1000, 1005, 1010, 1015],
        )
        self.assertEqual([r[2] for r in result], ["a.jpg", "b.jpg"])

    def test_supported_extensions(self):
        result = self.run_detection(
            ["a.jpg", "b.jpeg", "c.png", "d.tiff"], [1000, 1010, 1020, 1030]
        )
        self.assertEqual(len(result), 4)


class SerialProtocolTests(GuiTestCase):
    """The <COMMAND,arg> framing the Arduino firmware parses."""

    def setUp(self):
        super().setUp()
        self.win = self.make_window()
        self.win.serial = MagicMock()

    def sent(self):
        return [call.args[0] for call in self.win.serial.write.call_args_list]

    def test_send_serial_wraps_in_markers(self):
        self.win.sendSerial("PING")
        self.assertEqual(self.sent(), [b"<PING>"])

    def test_turn_on_led_is_one_based(self):
        self.win.turn_on_led(0)
        self.win.turn_on_led(49)
        self.assertEqual(self.sent(), [b"<ON,1>", b"<ON,50>"])

    def test_take_shot_uses_current_index_one_based(self):
        self.win.current_index = 4
        self.win.take_shot()
        self.assertEqual(self.sent(), [b"<SHOOT,5>"])

    def test_close_serial_turns_the_leds_off_first(self):
        self.win.closeSerial()
        self.assertEqual(self.sent(), [b"<OFF>"])
        self.win.serial.close.assert_called_once_with()

    def test_open_serial_is_a_no_op_without_a_configured_port(self):
        self.win.serial_exist = True
        self.win.serial_port = "None"  # QSettings round-trips None as this
        with patch.object(PTMGenerator2.serial, "Serial") as fake_serial:
            self.win.openSerial()
        fake_serial.assert_not_called()
        self.assertFalse(self.win.serial_exist)

    def test_receive_serial_returns_the_line(self):
        self.win.serial.readline.return_value = b"Turn on LED #1\n"
        self.assertEqual(self.win.receiveSerial(), b"Turn on LED #1\n")


class IncomingImagePollingTests(GuiTestCase):
    def setUp(self):
        super().setUp()
        self.win = self.make_window()
        self.win.post_shutter_polling = 0  # keep the suite fast
        self.win.current_index = 0
        self.win.retake_counter = 0

    def touch(self, name, mtime):
        path = os.path.join(self.workdir, name)
        open(path, "w").close()
        os.utime(path, (mtime, mtime))
        return path

    def test_returns_none_when_nothing_is_newer(self):
        self.touch("old.jpg", 1000)
        self.win.last_checked = 2000
        self.assertIsNone(self.win.get_incoming_image(self.workdir))

    def test_returns_the_new_file(self):
        expected = self.touch("new.jpg", 3000)
        self.win.last_checked = 2000
        self.assertEqual(self.win.get_incoming_image(self.workdir), expected)

    def test_returns_the_newest_of_several(self):
        self.touch("first.jpg", 2500)
        newest = self.touch("second.jpg", 3500)
        self.win.last_checked = 2000
        self.assertEqual(self.win.get_incoming_image(self.workdir), newest)

    def test_checkpoint_advances_so_the_same_file_is_not_returned_twice(self):
        self.touch("new.jpg", 3000)
        self.win.last_checked = 2000
        self.assertIsNotNone(self.win.get_incoming_image(self.workdir))
        self.assertIsNone(self.win.get_incoming_image(self.workdir))

    def test_non_image_files_are_ignored(self):
        self.touch("image_data.csv", 3000)
        self.touch("output.log", 3000)
        self.win.last_checked = 2000
        self.assertIsNone(self.win.get_incoming_image(self.workdir))

    def test_extension_matching_is_case_insensitive(self):
        expected = self.touch("SHOT.JPG", 3000)
        self.win.last_checked = 2000
        self.assertEqual(self.win.get_incoming_image(self.workdir), expected)

    def test_subdirectories_are_not_searched(self):
        nested = os.path.join(self.workdir, "sub")
        os.makedirs(nested)
        path = os.path.join(nested, "deep.jpg")
        open(path, "w").close()
        os.utime(path, (3000, 3000))
        self.win.last_checked = 2000
        self.assertIsNone(self.win.get_incoming_image(self.workdir))


class CsvRoundTripTests(GuiTestCase):
    def setUp(self):
        super().setUp()
        self.win = self.make_window()
        self.win.current_directory = self.workdir
        self.win.edtDirectory.setText(self.workdir)

    def write_csv(self, rows):
        with open(os.path.join(self.workdir, self.win.csv_file), "w", newline="") as fh:
            csv.writer(fh).writerows(rows)

    def test_update_csv_writes_every_slot(self):
        self.win.image_data = [
            (0, self.workdir, "a.jpg", True),
            (1, "-", "-", False),
        ]
        self.win.update_csv()
        with open(os.path.join(self.workdir, self.win.csv_file), newline="") as fh:
            rows = list(csv.reader(fh))
        self.assertEqual(rows, [
            ["0", self.workdir, "a.jpg", "True"],
            ["1", "-", "-", "False"],
        ])

    def test_load_csv_data_reads_the_four_column_format(self):
        self.write_csv([
            [0, self.workdir, "a.jpg", "True"],
            [1, self.workdir, "b.jpg", "False"],
        ])
        self.win.load_csv_data()
        self.assertEqual(self.win.image_data, [
            (0, self.workdir, "a.jpg", True),
            (1, self.workdir, "b.jpg", False),
        ])

    def test_legacy_three_column_rows_default_to_included(self):
        self.write_csv([[0, self.workdir, "a.jpg"]])
        self.win.load_csv_data()
        self.assertEqual(self.win.image_data, [(0, self.workdir, "a.jpg", True)])

    def test_malformed_rows_are_skipped(self):
        self.write_csv([
            [0, self.workdir, "a.jpg", "True"],
            ["junk"],
            [1, self.workdir, "b.jpg", "True"],
        ])
        self.win.load_csv_data()
        self.assertEqual([row[2] for row in self.win.image_data], ["a.jpg", "b.jpg"])

    def test_checkbox_column_mirrors_the_include_flag(self):
        self.write_csv([
            [0, self.workdir, "a.jpg", "True"],
            [1, self.workdir, "b.jpg", "False"],
        ])
        self.win.load_csv_data()
        model = self.win.image_model
        self.assertEqual(model.item(0, 0).checkState(), Qt.Checked)
        self.assertEqual(model.item(1, 0).checkState(), Qt.Unchecked)
        self.assertEqual(model.item(1, 1).text(), "b.jpg")

    def test_round_trip_preserves_data(self):
        original = [
            (0, self.workdir, "a.jpg", True),
            (1, self.workdir, "b.jpg", False),
        ]
        self.win.image_data = list(original)
        self.win.update_csv()
        self.win.image_data = []
        self.win.load_csv_data()
        self.assertEqual(self.win.image_data, original)


class CheckboxSyncTests(GuiTestCase):
    def setUp(self):
        super().setUp()
        self.win = self.make_window()
        self.win.current_directory = self.workdir
        self.win.image_data = [
            (0, self.workdir, "a.jpg", True),
            (1, self.workdir, "b.jpg", True),
        ]
        for name in ("a.jpg", "b.jpg"):
            checkbox = QStandardItem()
            checkbox.setCheckable(True)
            checkbox.setCheckState(Qt.Checked)
            self.win.image_model.appendRow([checkbox, QStandardItem(name)])

    def test_unchecking_clears_the_include_flag(self):
        self.win.image_model.item(1, 0).setCheckState(Qt.Unchecked)
        self.win.sync_checkbox_states_to_image_data()
        self.assertEqual([row[3] for row in self.win.image_data], [True, False])

    def test_sync_keeps_index_directory_and_filename(self):
        self.win.image_model.item(0, 0).setCheckState(Qt.Unchecked)
        self.win.sync_checkbox_states_to_image_data()
        self.assertEqual(self.win.image_data[0][:3], (0, self.workdir, "a.jpg"))

    def test_update_csv_persists_the_checkbox_state(self):
        self.win.image_model.item(0, 0).setCheckState(Qt.Unchecked)
        self.win.update_csv()
        with open(os.path.join(self.workdir, self.win.csv_file), newline="") as fh:
            rows = list(csv.reader(fh))
        self.assertEqual(rows[0][3], "False")


class GeneratePtmTests(GuiTestCase):
    """The .lp file handed to PTMfitter is the real output of this app."""

    def setUp(self):
        super().setUp()
        self.win = self.make_window()
        self.capture_dir = os.path.join(self.workdir, "specimen01")
        os.makedirs(self.capture_dir)
        self.win.current_directory = self.capture_dir
        self.win.light_position_adjustment = 0

        self.fitter = os.path.join(self.workdir, "ptmfitter.exe")
        open(self.fitter, "w").close()
        self.win.ptm_fitter = self.fitter

        self.lp_path = os.path.join(self.capture_dir, "specimen01.lp")

    def generate(self, save_as=""):
        with patch.object(QFileDialog, "getSaveFileName", return_value=(save_as, "")), \
             patch.object(PTMGenerator2.subprocess, "call") as self.fake_call:
            self.win.generatePTM()

    def test_lp_lists_only_included_shots(self):
        self.win.image_data = [
            (0, self.capture_dir, "a.jpg", True),
            (1, "-", "-", False),
            (2, self.capture_dir, "c.jpg", False),
            (3, self.capture_dir, "d.jpg", True),
        ]
        self.generate()
        with open(self.lp_path) as fh:
            lines = fh.read().splitlines()
        self.assertEqual(lines[0], "2")
        self.assertEqual(len(lines), 3)
        self.assertIn("a.jpg", lines[1])
        self.assertIn("d.jpg", lines[2])

    def test_lp_rows_carry_the_light_vector_for_that_led(self):
        self.win.image_data = [(7, self.capture_dir, "shot.jpg", True)]
        self.generate()
        with open(self.lp_path) as fh:
            row = fh.read().splitlines()[1]
        path, x, y, z = row.rsplit(" ", 3)
        expected = self.win.prepare_light_positions()[7]
        for got, want in zip((float(x), float(y), float(z)), expected):
            self.assertAlmostEqual(got, want, places=9)

    def test_image_paths_are_absolute(self):
        self.win.image_data = [(0, self.capture_dir, "shot.jpg", True)]
        self.generate()
        with open(self.lp_path) as fh:
            path = fh.read().splitlines()[1].rsplit(" ", 3)[0]
        self.assertTrue(os.path.isabs(path))

    def test_extension_is_lowercased(self):
        self.win.image_data = [(0, self.capture_dir, "SHOT.JPG", True)]
        self.generate()
        with open(self.lp_path) as fh:
            path = fh.read().splitlines()[1].rsplit(" ", 3)[0]
        self.assertTrue(path.endswith("SHOT.jpg"))

    def test_lp_is_named_after_the_capture_directory(self):
        self.win.image_data = [(0, self.capture_dir, "a.jpg", True)]
        self.generate()
        self.assertTrue(os.path.exists(self.lp_path))

    def test_fitter_is_invoked_with_the_chosen_output_path(self):
        self.win.image_data = [(0, self.capture_dir, "a.jpg", True)]
        out = os.path.join(self.capture_dir, "specimen01.ptm")
        self.generate(save_as=out)
        self.fake_call.assert_called_once_with(
            [self.fitter, "-i", self.lp_path, "-o", out]
        )

    def test_cancelling_the_save_dialog_skips_the_fitter(self):
        self.win.image_data = [(0, self.capture_dir, "a.jpg", True)]
        self.generate(save_as="")
        self.fake_call.assert_not_called()

    def test_missing_fitter_aborts_before_writing_anything(self):
        self.win.ptm_fitter = os.path.join(self.workdir, "does-not-exist.exe")
        self.win.image_data = [(0, self.capture_dir, "a.jpg", True)]
        with patch.object(PTMGenerator2.QMessageBox, "critical") as warn:
            self.win.generatePTM()
        warn.assert_called_once()
        self.assertFalse(os.path.exists(self.lp_path))


class RetakeSelectionTests(GuiTestCase):
    def setUp(self):
        super().setUp()
        self.win = self.make_window()
        self.win.serial_exist = False

    def test_retake_without_a_selection_does_nothing(self):
        self.win.selected_rows = []
        self.win.on_retake_picture_triggered()
        self.assertFalse(self.win.timer.isActive())

    def test_retake_queues_selected_rows_in_order(self):
        self.win.selected_rows = [7, 2, 5]
        self.win.on_retake_picture_triggered()
        self.addCleanup(self.win.timer.stop)
        self.assertEqual(self.win.current_index, 2)
        self.assertEqual(self.win.image_index_list, [5, 7])
        self.assertTrue(self.win.timer.isActive())


class TakeAllPicturesTests(GuiTestCase):
    def setUp(self):
        super().setUp()
        self.win = self.make_window()
        self.win.serial_exist = False

    def test_queue_covers_every_led(self):
        self.win.number_of_LEDs = 6
        self.win.take_all_pictures()
        self.addCleanup(self.win.timer.stop)
        self.assertEqual(self.win.current_index, 0)
        self.assertEqual(self.win.image_index_list, [1, 2, 3, 4, 5])

    def test_previous_run_is_cleared(self):
        self.win.number_of_LEDs = 3
        self.win.image_data = [(0, "somewhere", "stale.jpg", True)]
        self.win.take_all_pictures()
        self.addCleanup(self.win.timer.stop)
        self.assertEqual(self.win.image_data, [])


class PauseAndStopTests(GuiTestCase):
    def setUp(self):
        super().setUp()
        self.win = self.make_window()

    def test_pause_then_continue_toggles_the_timer(self):
        self.win.timer.start(1000)
        self.addCleanup(self.win.timer.stop)
        self.win.pause_continue_process()
        self.assertFalse(self.win.timer.isActive())
        self.win.pause_continue_process()
        self.assertTrue(self.win.timer.isActive())

    def test_stop_halts_the_timer_and_clears_the_queue(self):
        # stop_process() unconditionally calls closeSerial(), so a serial object
        # has to be present — see openSerial() for how it is normally created.
        self.win.serial = MagicMock()
        self.win.timer.start(1000)
        self.win.image_index_list = [3, 4, 5]
        self.win.stop_process()
        self.assertFalse(self.win.timer.isActive())
        self.assertEqual(self.win.image_index_list, [])
        self.win.serial.write.assert_called_once_with(b"<OFF>")


class PreferencesWindowTests(GuiTestCase):
    def make_prefs(self, **values):
        parent = self.make_window()
        settings = parent.m_app.settings
        for key, value in values.items():
            settings.setValue(key, value)
        settings.sync()
        prefs = PreferencesWindow(parent)
        self.addCleanup(prefs.close)
        prefs.read_settings()
        return prefs

    def test_defaults_when_nothing_is_stored(self):
        prefs = self.make_prefs()
        self.assertEqual(prefs.ptm_fitter, "ptmfitter.exe")
        self.assertEqual(prefs.number_of_LEDs, 50)
        self.assertEqual(prefs.language, "en")
        self.assertEqual(prefs.light_position_adjustment, 0)
        self.assertEqual(prefs.post_shutter_polling, 1.0)

    def test_stored_values_are_read_back(self):
        prefs = self.make_prefs(
            ptm_fitter="/opt/ptmfitter",
            Number_of_LEDs="24",
            RetryCount="5",
            light_position_adjustment="15",
            post_shutter_polling="2.5",
            language="ko",
        )
        self.assertEqual(prefs.ptm_fitter, "/opt/ptmfitter")
        self.assertEqual(prefs.number_of_LEDs, 24)
        self.assertEqual(prefs.retry_count, 5)
        self.assertEqual(prefs.light_position_adjustment, 15)
        self.assertEqual(prefs.post_shutter_polling, 2.5)
        self.assertEqual(prefs.language, "ko")

    def test_numeric_settings_are_coerced_from_strings(self):
        # QSettings returns strings from an .ini file, never ints.
        prefs = self.make_prefs(Number_of_LEDs="12", post_shutter_polling="0.5")
        self.assertIsInstance(prefs.number_of_LEDs, int)
        self.assertIsInstance(prefs.post_shutter_polling, float)


class MainWindowSettingsTests(GuiTestCase):
    def test_defaults(self):
        win = self.make_window()
        self.assertEqual(win.number_of_LEDs, 50)
        self.assertEqual(win.ptm_fitter, "ptmfitter.exe")
        self.assertFalse(win.serial_exist)

    def test_number_of_leds_is_read_from_settings(self):
        win = self.make_window()
        win.m_app.settings.setValue("Number_of_LEDs", "24")
        win.m_app.settings.sync()
        win.read_settings()
        self.assertEqual(win.number_of_LEDs, 24)

    def test_window_title_carries_the_version(self):
        win = self.make_window()
        self.assertIn(PTMGenerator2.PROGRAM_VERSION, win.windowTitle())


if __name__ == "__main__":
    unittest.main()

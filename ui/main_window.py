"""The main window: the capture table, the buttons and the capture loop."""

import os
import sys
import time

from PyQt5.QtCore import QObject, QRect, Qt, QTimer, QTranslator, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QStandardItem, QStandardItemModel
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QStatusBar,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from core import image_data, paths, ptm_builder, ptm_fitter
from core import settings as prefs
from core.capture_session import CaptureSession
from core.image_data import MISSING, CaptureSlot
from core.light_positions import light_vectors
from core.resources import icon_path, translation_path
from core.serial_controller import SerialController
from ui.app import app, require
from ui.geometry import to_list, to_rect
from ui.preferences_window import PreferencesWindow
from version import __version__

#: One capture tick per second.
TICK_MS = 1000


class PtmFitCancelledError(Exception):
    """The user cancelled the fit from the progress dialog."""


class OutputRedirector(QObject):
    """Tees stdout to a log file so a --noconsole build still leaves a trace."""

    output_written = pyqtSignal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self.stdout = sys.stdout
        # Held open for the lifetime of the window and closed in close();
        # a context manager cannot express that.
        # Appended, not truncated: the file is one day's log, and a second run
        # on the same day must not erase the first one's record.
        self.file = open(file_path, "a", encoding="utf-8")  # noqa: SIM115

    def write(self, message):
        if self.stdout is not None:
            self.stdout.write(message)
        self.file.write(message)
        self.file.flush()
        self.output_written.emit(message)

    def flush(self):
        if self.stdout is not None:
            self.stdout.flush()
        self.file.flush()

    def close(self):
        self.file.close()


class PTMGeneratorMainWindow(QMainWindow):
    """Drives a capture run and turns the result into a .ptm.

    The sequencing lives in core.capture_session; this class owns the widgets,
    the one-second timer and the serial port, and renders whatever the session
    decides.
    """

    def __init__(self):
        super().__init__()
        self.initialize_variables()
        self.setup_ui()

    # -- setup --------------------------------------------------------------

    def initialize_variables(self):
        self.image_data = []
        #: The folder the user chose. Watched, including everything beneath it,
        #: until a shot lands.
        self.monitor_root = "."
        #: The folder shots are actually arriving in, discovered from the first
        #: one. None until then. Tethering software commonly files images into
        #: a dated subfolder that does not exist before the day's first shot,
        #: so the folder the user can pick is often the parent of the one that
        #: ends up holding the run.
        self.capture_directory = None
        self.csv_file = "image_data.csv"
        self.last_checked = time.time()
        self.session = None
        self.serial = SerialController()
        self.selected_rows = []
        self.prev_selected_rows = []

        paths.ensure_directories()
        self.redirector = OutputRedirector(paths.log_path())
        sys.stdout = self.redirector

    def setup_ui(self):
        self.setWindowIcon(QIcon(icon_path("app")))
        self.setWindowTitle("{} v{}".format(self.tr("PTMGenerator2"), __version__))

        self.table_view = QTableView()
        self.image_view = QLabel()

        # The directory field at the top shows what is being *watched*; shots
        # can land in a subfolder of it, so where they are actually going needs
        # its own line, next to the list of what has arrived.
        self.lblCaptureDirectory = QLabel()
        self.lblCaptureDirectory.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.lblCaptureDirectory.setWordWrap(True)

        self.capture_list_widget = QWidget()
        self.capture_list_layout = QVBoxLayout()
        self.capture_list_layout.setContentsMargins(0, 0, 0, 0)
        self.capture_list_widget.setLayout(self.capture_list_layout)
        self.capture_list_layout.addWidget(self.lblCaptureDirectory)
        self.capture_list_layout.addWidget(self.table_view)

        self.image_list_widget = QWidget()
        self.image_list_layout = QHBoxLayout()
        self.image_list_widget.setLayout(self.image_list_layout)
        self.image_list_layout.addWidget(self.capture_list_widget, 1)
        self.image_list_layout.addWidget(self.image_view, 4)

        self.image_model = QStandardItemModel()
        self.image_model.setHorizontalHeaderLabels([self.tr("Include"), self.tr("Filename")])
        self.table_view.setModel(self.image_model)
        header = require(self.table_view.horizontalHeader(), "table header")
        header.setSectionResizeMode(0, header.ResizeToContents)
        header.setSectionResizeMode(1, header.Stretch)
        self.selection().selectionChanged.connect(self.on_selection_changed)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.lblDirectory = QLabel(self.tr("Directory"))
        self.btnOpenDirectory = QPushButton(self.tr("Open Directory"))
        self.btnOpenDirectory.clicked.connect(self.on_action_open_directory_triggered)
        self.edtDirectory = QLineEdit()
        self.edtDirectory.setReadOnly(True)
        self.edtDirectory.setText(self.monitor_root)

        self.directory_widget = QWidget()
        self.directory_layout = QHBoxLayout()
        self.directory_widget.setLayout(self.directory_layout)
        self.directory_layout.addWidget(self.lblDirectory)
        self.directory_layout.addWidget(self.edtDirectory)
        self.directory_layout.addWidget(self.btnOpenDirectory)

        self.btnTestShot = QPushButton(self.tr("Test Shot"))
        self.btnTestShot.clicked.connect(self.test_shot)
        self.btnTakeAllPictures = QPushButton(self.tr("Take All Pictures"))
        self.btnTakeAllPictures.clicked.connect(self.take_all_pictures)
        self.btnRetakePicture = QPushButton(self.tr("Retake Picture"))
        self.btnRetakePicture.clicked.connect(self.on_retake_picture_triggered)
        self.btnPauseContinue = QPushButton(self.tr("Pause/Continue"))
        self.btnPauseContinue.clicked.connect(self.pause_continue_process)
        self.btnStop = QPushButton(self.tr("Stop"))
        self.btnStop.clicked.connect(self.stop_process)
        self.btnGeneratePTM = QPushButton(self.tr("Generate PTM"))
        self.btnGeneratePTM.clicked.connect(self.generatePTM)

        self.button_widget = QWidget()
        self.button_layout = QHBoxLayout()
        self.button_widget.setLayout(self.button_layout)
        for button in (
            self.btnTestShot,
            self.btnTakeAllPictures,
            self.btnRetakePicture,
            self.btnPauseContinue,
            self.btnStop,
            self.btnGeneratePTM,
        ):
            self.button_layout.addWidget(button)

        self.central_widget = QWidget()
        self.central_layout = QVBoxLayout()
        self.central_widget.setLayout(self.central_layout)
        self.central_layout.addWidget(self.directory_widget)
        self.central_layout.addWidget(self.image_list_widget)
        self.central_layout.addWidget(self.button_widget)
        self.setCentralWidget(self.central_widget)

        self.actionOpenDirectory = QAction(self.tr("Open Directory\tCtrl+O"), self)
        self.actionOpenDirectory.triggered.connect(self.on_action_open_directory_triggered)
        self.actionPreferences = QAction(self.tr("Preferences"), self)
        self.actionPreferences.triggered.connect(self.on_action_preferences_triggered)
        self.actionAbout = QAction(self.tr("About"), self)
        self.actionAbout.triggered.connect(self.on_action_about_triggered)

        self.main_menu = require(self.menuBar(), "menu bar")
        self.file_menu = require(self.main_menu.addMenu(self.tr("File")), "File menu")
        self.file_menu.addAction(self.actionOpenDirectory)
        self.edit_menu = require(self.main_menu.addMenu(self.tr("Edit")), "Edit menu")
        self.edit_menu.addAction(self.actionPreferences)
        self.help_menu = require(self.main_menu.addMenu(self.tr("Help")), "Help menu")
        self.help_menu.addAction(self.actionAbout)

        self.m_app = app()
        self.read_settings()

        self.update_capture_directory_label()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.take_picture_process)

    # -- settings -----------------------------------------------------------

    def read_settings(self):
        # The entry point opens the store and hands it to the application; a
        # window built by a test or a script gets one opened here.
        s = self.m_app.preferences()
        self.m_app.remember_geometry = prefs.value_to_bool(
            s.value("WindowGeometry/RememberGeometry", True)
        )
        if self.m_app.remember_geometry:
            self.setGeometry(
                to_rect(s.value("WindowGeometry/MainWindow"), QRect(100, 100, 1400, 800))
            )
            if prefs.value_to_bool(s.value("IsMaximized/MainWindow", False)):
                self.showMaximized()
            else:
                self.showNormal()
        else:
            self.setGeometry(QRect(100, 100, 1400, 800))

        self.m_app.serial_port = prefs.read_str(s, prefs.SERIAL_PORT)
        self.m_app.language = prefs.read_str(s, prefs.LANGUAGE)
        self.serial.port = self.m_app.serial_port
        self.ptm_fitter = prefs.read_str(s, prefs.PTM_FITTER)
        self.fitter = prefs.read_str(s, prefs.FITTER)
        self.number_of_LEDs = prefs.read_int(s, prefs.NUMBER_OF_LEDS)
        self.auto_retake_maximum = prefs.read_int(s, prefs.RETRY_COUNT)
        self.light_position_adjustment = prefs.read_int(s, prefs.LIGHT_POSITION_ADJUSTMENT)
        self.post_shutter_polling = prefs.read_float(s, prefs.POST_SHUTTER_POLLING)
        self.update_language(self.m_app.language)

    def save_settings(self):
        s = self.m_app.preferences()
        s.setValue("WindowGeometry/MainWindow", to_list(self.geometry()))
        s.setValue("IsMaximized/MainWindow", self.isMaximized())
        s.sync()

    # -- serial -------------------------------------------------------------

    def confirm_capture_without_controller(self, reason=None):
        """Ask whether to run a capture with no controller attached.

        Args:
            reason (str | None): Why the configured port could not be opened,
                if one was configured at all.

        Returns:
            bool: True if the user chose to go ahead anyway. Defaults to
            cancelling, since without the controller nothing is photographed.
        """
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        if reason:
            # A port is configured but the OS would not give it to us: the
            # board is unplugged, something else holds it, or the saved name is
            # stale. Naming the port and the reason is the difference between a
            # user fixing it and a user filing a bug.
            box.setWindowTitle(self.tr("Serial port unavailable"))
            box.setText(
                self.tr(
                    "{port} could not be opened, so the LEDs and the camera "
                    "shutter cannot be triggered. Nothing will be photographed.\n\n"
                    "{reason}\n\n"
                    "Check the controller is connected and not in use by another "
                    "program, or choose a different port in Edit › Preferences."
                ).format(port=self.serial.port, reason=reason)
            )
        else:
            box.setWindowTitle(self.tr("No serial port"))
            box.setText(
                self.tr(
                    "No serial port is configured, so the LEDs and the camera "
                    "shutter cannot be triggered. Nothing will be photographed.\n\n"
                    "Choose the controller's port in Edit › Preferences, or "
                    "continue anyway to try out the interface without hardware."
                )
            )
        proceed = box.addButton(self.tr("Continue anyway"), QMessageBox.AcceptRole)
        cancel = box.addButton(self.tr("Cancel"), QMessageBox.RejectRole)
        box.setDefaultButton(cancel)
        box.exec()
        return box.clickedButton() is proceed

    def ensure_serial_ready(self):
        """Open the controller's port, prompting the user if it is unusable."""
        if self.serial.open():
            return True
        reason = self.serial.last_error
        if reason:
            self.status_bar.showMessage(
                self.tr("Could not open {port}").format(port=self.serial.port), 5000
            )
        else:
            self.status_bar.showMessage(self.tr("No serial port configured"), 5000)
        return self.confirm_capture_without_controller(reason)

    # -- capture ------------------------------------------------------------

    def _start_session(self, indices):
        self.session = CaptureSession(
            indices,
            preparation_time=prefs.PREPARATION_TIME,
            polling_timeout=prefs.POLLING_TIMEOUT,
            max_retakes=self.auto_retake_maximum,
        )
        self.last_checked = time.time()
        self.btnPauseContinue.setText(self.tr("Pause"))
        self.timer.start(TICK_MS)

    def take_all_pictures(self):
        # Checked before clear_image_data() so a refused run leaves the
        # existing capture table untouched.
        if not self.ensure_serial_ready():
            return
        self.clear_image_data()
        # Rediscover where shots land. The dated subfolder changes daily, and a
        # run started after midnight must not keep writing into yesterday's.
        self.capture_directory = None
        self._start_session(range(self.number_of_LEDs))

    def on_retake_picture_triggered(self):
        if not self.selected_rows:
            return
        if not self.ensure_serial_ready():
            return
        self._start_session(sorted(self.selected_rows))

    def test_shot(self):
        if not self.ensure_serial_ready():
            return
        self.serial.shoot(0)
        time.sleep(1)
        new_image = None
        for _ in range(5):
            time.sleep(3)
            new_image = self.poll_for_image()
            if new_image is not None:
                break
        if new_image is None:
            self.status_bar.showMessage(self.tr("Failed to get image file"), 1000)
        else:
            self.status_bar.showMessage(f"New image detected: {new_image}", 1000)
        self.serial.close()

    def update_capture_directory_label(self):
        """Show where shots are going, and whether that is the watched folder."""
        if self.capture_directory is None:
            self.lblCaptureDirectory.setText(
                self.tr("Waiting for the first shot — watching {root} and below").format(
                    root=self.monitor_root
                )
            )
        else:
            self.lblCaptureDirectory.setText(
                self.tr("Capture folder: {directory}").format(directory=self.capture_directory)
            )

    @property
    def working_directory(self):
        """Where this run's files belong: the adopted folder, else the root."""
        return self.capture_directory or self.monitor_root

    def adopt_capture_directory(self, directory):
        """Treat `directory` as the working folder for the rest of the run."""
        if self.capture_directory == directory:
            return
        self.capture_directory = directory
        self.update_capture_directory_label()
        print(f"Capturing into {directory}")
        self.status_bar.showMessage(
            self.tr("Capturing into {directory}").format(directory=directory), 5000
        )

    def poll_for_image(self):
        """Look for a shot newer than the last one we accepted.

        Until the first shot of a run arrives there is no way to know which
        folder the camera software will file it into, so the whole tree under
        the monitored root is searched. After that the folder is known and the
        search narrows to it — this runs once a second, and walking a season's
        worth of dated subfolders every time would not.
        """
        time.sleep(self.post_shutter_polling)
        if self.capture_directory is None:
            path, mtime = image_data.find_newest_image(
                self.monitor_root, self.last_checked, recursive=True
            )
            if path is not None:
                self.adopt_capture_directory(os.path.dirname(path))
        else:
            path, mtime = image_data.find_newest_image(self.capture_directory, self.last_checked)
        if path is not None:
            self.last_checked = mtime
        return path

    def take_picture_process(self):
        """One capture tick, driven by the timer."""
        session = self.session
        if session is None:
            self.timer.stop()
            return

        index = session.current_index
        result = session.step(shoot=self.serial.shoot, poll=self.poll_for_image)

        if result.recorded is not None:
            led_index, path = result.recorded
            self.record_slot(led_index, path)

        self.status_bar.showMessage(
            "[#{}] {}".format(index + 1 if index is not None else "-", result.event), 1000
        )

        if result.finished:
            self.timer.stop()
            self.status_bar.showMessage(
                self.tr("All pictures ({}) taken").format(self.number_of_LEDs), 5000
            )
            self.update_csv()
            self.btnPauseContinue.setText(self.tr("Pause/Continue"))
            self.serial.close()
            self.session = None

    def record_slot(self, led_index, path):
        """Put a finished shot (or a missing one) into the table."""
        if path is None:
            directory, filename, include = MISSING, MISSING, False
        else:
            directory, filename = os.path.split(path)
            include = True

        checkbox_item = QStandardItem()
        checkbox_item.setCheckable(True)
        checkbox_item.setCheckState(Qt.CheckState.Checked if include else Qt.CheckState.Unchecked)
        filename_item = QStandardItem(filename)

        slot = CaptureSlot(led_index, directory, filename, include)
        if led_index < self.image_model.rowCount():
            self.image_model.setItem(led_index, 0, checkbox_item)
            self.image_model.setItem(led_index, 1, filename_item)
            self.image_data[led_index] = slot
        else:
            self.image_model.appendRow([checkbox_item, filename_item])
            self.image_data.append(slot)

        if path is not None:
            self.show_image(path)

    def pause_continue_process(self):
        if self.timer.isActive():
            self.timer.stop()
            self.status_bar.showMessage(self.tr("Paused"), 1000)
            self.btnPauseContinue.setText(self.tr("Continue"))
        else:
            self.timer.start()
            self.status_bar.showMessage(self.tr("Continued"), 1000)
            self.btnPauseContinue.setText(self.tr("Pause"))

    def stop_process(self):
        self.timer.stop()
        self.session = None
        self.serial.close()
        self.status_bar.showMessage(self.tr("Stopped"), 1000)

    # -- capture table ------------------------------------------------------

    def clear_image_data(self):
        self.image_data = []
        self.image_model.clear()
        self.image_model.setHorizontalHeaderLabels([self.tr("Include"), self.tr("Filename")])
        self.image_view.clear()
        self.selection().clearSelection()
        self.prev_selected_rows = []

    def load_csv_data(self):
        csv_path = os.path.join(self.edtDirectory.text(), self.csv_file)
        self.image_data = image_data.read_csv(csv_path)
        for slot in self.image_data:
            checkbox_item = QStandardItem()
            checkbox_item.setCheckable(True)
            checkbox_item.setCheckState(
                Qt.CheckState.Checked if slot.include else Qt.CheckState.Unchecked
            )
            self.image_model.appendRow([checkbox_item, QStandardItem(slot.filename)])
        self.table_view.selectRow(0)

    def load_image_files(self):
        slots = image_data.detect_irregular_intervals(self.working_directory)
        if len(slots) == self.number_of_LEDs:
            self.image_data.extend(slots)
            self.update_csv()
            self.load_csv_data()
        else:
            self.status_bar.showMessage(
                self.tr("Image files not found or not enough images in the directory."), 5000
            )

    def sync_checkbox_states_to_image_data(self):
        """Copy the table's checkboxes back into the capture table."""
        for row in range(self.image_model.rowCount()):
            checkbox_item = self.image_model.item(row, 0)
            if checkbox_item and row < len(self.image_data):
                slot = self.image_data[row]
                self.image_data[row] = slot._replace(
                    include=checkbox_item.checkState() == Qt.CheckState.Checked
                )

    def update_csv(self):
        self.sync_checkbox_states_to_image_data()
        image_data.write_csv(os.path.join(self.working_directory, self.csv_file), self.image_data)

    def selection(self):
        """The table's selection model.

        Optional in the stubs -- a view with no model has none -- but the model
        is set in `setup_ui` before anything here runs.
        """
        return require(self.table_view.selectionModel(), "selection model")

    def on_selection_changed(self, selected, deselected):
        self.selected_rows = sorted({index.row() for index in self.selection().selectedIndexes()})
        for row in self.selected_rows:
            if row not in self.prev_selected_rows and row < len(self.image_data):
                slot = self.image_data[row]
                if slot.captured:
                    self.show_image(os.path.join(slot.directory, slot.filename))
        self.prev_selected_rows = self.selected_rows

    def show_image(self, image_file):
        self.image_view.setPixmap(
            QPixmap(image_file).scaled(self.image_view.size(), Qt.AspectRatioMode.KeepAspectRatio)
        )

    # -- actions ------------------------------------------------------------

    def on_action_open_directory_triggered(self):
        directory = QFileDialog.getExistingDirectory(self, self.tr("Open Directory"))
        if not directory:
            return
        self.monitor_root = directory
        # A previous run's folder is not this run's folder.
        self.capture_directory = None
        self.edtDirectory.setText(directory)
        self.update_capture_directory_label()
        self.clear_image_data()
        if os.path.exists(os.path.join(directory, self.csv_file)):
            self.load_csv_data()
        else:
            self.load_image_files()

    def on_action_preferences_triggered(self):
        preferences = PreferencesWindow(self)
        preferences.exec()
        self.read_settings()

    def on_action_about_triggered(self):
        QMessageBox.about(
            self, self.tr("About"), "{} v{}".format(self.tr("PTMGenerator2"), __version__)
        )

    # -- PTM ----------------------------------------------------------------

    def generatePTM(self):
        """Ask where the .ptm goes, then fit it.

        Which fitter runs is a preference: the built-in one by default, or
        PTMfitter.exe for anyone who wants the old behaviour. See
        `core.settings.FITTER`.
        """
        self.sync_checkbox_states_to_image_data()

        ptm_filename, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save PTM file"),
            str(self.working_directory),
            "PTM files (*.ptm);;All files (*)",
        )
        if not ptm_filename:
            return

        vectors = light_vectors(self.light_position_adjustment)
        try:
            if self.fitter == prefs.FITTER_NATIVE:
                lp_path = self.generate_ptm_natively(vectors, ptm_filename)
            else:
                lp_path = ptm_builder.generate(
                    self.image_data, vectors, self.ptm_fitter, ptm_filename
                )
        except ptm_builder.PtmFitterNotFoundError as error:
            self.report_error(self.tr("PTM fitter not found: {path}").format(path=error))
        except ptm_builder.NoImagesToFitError:
            self.report_error(self.tr("No images to process."))
        except ptm_builder.PtmFitterFailedError as error:
            self.report_error(str(error))
        except ptm_fitter.FitError as error:
            self.report_error(
                self.tr("The images could not be fitted: {reason}").format(reason=error)
            )
        except PtmFitCancelledError:
            self.status_bar.showMessage(self.tr("PTM generation cancelled"), 5000)
        else:
            self.status_bar.showMessage(self.tr("Saved {path}").format(path=ptm_filename), 5000)
            print(f"Wrote {ptm_filename} (light positions: {lp_path})")

    def generate_ptm_natively(self, vectors, destination):
        """Fit in-process, showing progress.

        The fit reads every capture, which for fifty full-size images is tens
        of seconds -- long enough that the window must not simply freeze.

        The progress callback pumps the event loop rather than running the fit
        on a worker thread. That is the smaller change and it keeps the dialog
        responsive; a worker thread is the better answer and is in TODOs.md.
        """
        total = len(ptm_builder.usable_slots(self.image_data))
        dialog = QProgressDialog(self.tr("Fitting the PTM..."), self.tr("Cancel"), 0, total, self)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)

        def report(done, count):
            dialog.setValue(done)
            dialog.setLabelText(
                self.tr("Fitting the PTM: image {done} of {count}").format(done=done, count=count)
            )
            QApplication.processEvents()
            if dialog.wasCanceled():
                raise PtmFitCancelledError

        try:
            return ptm_builder.generate_native(
                self.image_data, vectors, destination, progress=report
            )
        finally:
            dialog.close()

    def report_error(self, message):
        print(message)
        self.status_bar.showMessage(message, 5000)
        QMessageBox.critical(self, self.tr("Error"), message)

    # -- i18n ---------------------------------------------------------------

    def update_language(self, language):
        if self.m_app.translator is not None:
            self.m_app.removeTranslator(self.m_app.translator)
            self.m_app.translator = None

        path = translation_path(language)
        if os.path.exists(path):
            translator = QTranslator()
            translator.load(path)
            self.m_app.installTranslator(translator)
            self.m_app.translator = translator

        self.setWindowTitle("{} v{}".format(self.tr("PTMGenerator2"), __version__))
        self.lblDirectory.setText(self.tr("Directory"))
        self.btnOpenDirectory.setText(self.tr("Open Directory"))
        self.btnTestShot.setText(self.tr("Test Shot"))
        self.btnTakeAllPictures.setText(self.tr("Take All Pictures"))
        self.btnRetakePicture.setText(self.tr("Retake Picture"))
        self.btnPauseContinue.setText(self.tr("Pause/Continue"))
        self.btnStop.setText(self.tr("Stop"))
        self.btnGeneratePTM.setText(self.tr("Generate PTM"))
        self.actionOpenDirectory.setText(self.tr("Open Directory\tCtrl+O"))
        self.actionPreferences.setText(self.tr("Preferences"))
        self.actionAbout.setText(self.tr("About"))
        self.file_menu.setTitle(self.tr("File"))
        self.edit_menu.setTitle(self.tr("Edit"))
        self.help_menu.setTitle(self.tr("Help"))
        self.image_model.setHorizontalHeaderLabels([self.tr("Include"), self.tr("Filename")])
        self.update_capture_directory_label()
        self.update()

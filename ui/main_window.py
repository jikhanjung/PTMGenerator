"""The main window: the capture table, the buttons and the capture loop."""

import os
import sys
import time

from PyQt5.QtCore import QObject, QRect, QSettings, Qt, QTimer, QTranslator, pyqtSignal
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
    QPushButton,
    QStatusBar,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from core import image_data, ptm_builder
from core import settings as prefs
from core.capture_session import CaptureSession
from core.image_data import MISSING, CaptureSlot
from core.light_positions import light_vectors
from core.resources import icon_path, translation_path
from core.serial_controller import SerialController
from ui.preferences_window import PreferencesWindow
from version import COMPANY_NAME, PROGRAM_NAME, __version__

#: One capture tick per second.
TICK_MS = 1000


class OutputRedirector(QObject):
    """Tees stdout to a log file so a --noconsole build still leaves a trace."""

    output_written = pyqtSignal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self.stdout = sys.stdout
        # Held open for the lifetime of the window and closed in close();
        # a context manager cannot express that.
        self.file = open(file_path, "w")  # noqa: SIM115

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
        self.current_directory = "."
        self.csv_file = "image_data.csv"
        self.last_checked = time.time()
        self.session = None
        self.serial = SerialController()
        self.selected_rows = []
        self.prev_selected_rows = []

        self.redirector = OutputRedirector("output.log")
        sys.stdout = self.redirector

    def setup_ui(self):
        self.setWindowIcon(QIcon(icon_path("app")))
        self.setWindowTitle("{} v{}".format(self.tr("PTMGenerator2"), __version__))

        self.table_view = QTableView()
        self.image_view = QLabel()

        self.image_list_widget = QWidget()
        self.image_list_layout = QHBoxLayout()
        self.image_list_widget.setLayout(self.image_list_layout)
        self.image_list_layout.addWidget(self.table_view, 1)
        self.image_list_layout.addWidget(self.image_view, 4)

        self.image_model = QStandardItemModel()
        self.image_model.setHorizontalHeaderLabels([self.tr("Include"), self.tr("Filename")])
        self.table_view.setModel(self.image_model)
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(0, header.ResizeToContents)
        header.setSectionResizeMode(1, header.Stretch)
        self.table_view.selectionModel().selectionChanged.connect(self.on_selection_changed)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

        self.lblDirectory = QLabel(self.tr("Directory"))
        self.btnOpenDirectory = QPushButton(self.tr("Open Directory"))
        self.btnOpenDirectory.clicked.connect(self.on_action_open_directory_triggered)
        self.edtDirectory = QLineEdit()
        self.edtDirectory.setReadOnly(True)
        self.edtDirectory.setText(self.current_directory)

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

        self.main_menu = self.menuBar()
        self.file_menu = self.main_menu.addMenu(self.tr("File"))
        self.file_menu.addAction(self.actionOpenDirectory)
        self.edit_menu = self.main_menu.addMenu(self.tr("Edit"))
        self.edit_menu.addAction(self.actionPreferences)
        self.help_menu = self.main_menu.addMenu(self.tr("Help"))
        self.help_menu.addAction(self.actionAbout)

        self.m_app = QApplication.instance()
        self.read_settings()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.take_picture_process)

    # -- settings -----------------------------------------------------------

    def read_settings(self):
        self.m_app.settings = QSettings(
            QSettings.IniFormat, QSettings.UserScope, COMPANY_NAME, PROGRAM_NAME
        )
        s = self.m_app.settings
        self.m_app.remember_geometry = prefs.value_to_bool(
            s.value("WindowGeometry/RememberGeometry", True)
        )
        if self.m_app.remember_geometry:
            self.setGeometry(s.value("WindowGeometry/MainWindow", QRect(100, 100, 1400, 800)))
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
        self.number_of_LEDs = prefs.read_int(s, prefs.NUMBER_OF_LEDS)
        self.auto_retake_maximum = prefs.read_int(s, prefs.RETRY_COUNT)
        self.light_position_adjustment = prefs.read_int(s, prefs.LIGHT_POSITION_ADJUSTMENT)
        self.post_shutter_polling = prefs.read_float(s, prefs.POST_SHUTTER_POLLING)
        self.update_language(self.m_app.language)

    def save_settings(self):
        self.m_app.settings.setValue("WindowGeometry/MainWindow", self.geometry())
        self.m_app.settings.setValue("IsMaximized/MainWindow", self.isMaximized())

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
            self.statusBar.showMessage(
                self.tr("Could not open {port}").format(port=self.serial.port), 5000
            )
        else:
            self.statusBar.showMessage(self.tr("No serial port configured"), 5000)
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
            self.statusBar.showMessage(self.tr("Failed to get image file"), 1000)
        else:
            self.statusBar.showMessage(f"New image detected: {new_image}", 1000)
        self.serial.close()

    def poll_for_image(self):
        """Look for a shot newer than the last one we accepted."""
        time.sleep(self.post_shutter_polling)
        path, mtime = image_data.find_newest_image(self.current_directory, self.last_checked)
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

        self.statusBar.showMessage(
            "[#{}] {}".format(index + 1 if index is not None else "-", result.event), 1000
        )

        if result.finished:
            self.timer.stop()
            self.statusBar.showMessage(
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
        checkbox_item.setCheckState(Qt.Checked if include else Qt.Unchecked)
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
            self.statusBar.showMessage(self.tr("Paused"), 1000)
            self.btnPauseContinue.setText(self.tr("Continue"))
        else:
            self.timer.start()
            self.statusBar.showMessage(self.tr("Continued"), 1000)
            self.btnPauseContinue.setText(self.tr("Pause"))

    def stop_process(self):
        self.timer.stop()
        self.session = None
        self.serial.close()
        self.statusBar.showMessage(self.tr("Stopped"), 1000)

    # -- capture table ------------------------------------------------------

    def clear_image_data(self):
        self.image_data = []
        self.image_model.clear()
        self.image_model.setHorizontalHeaderLabels([self.tr("Include"), self.tr("Filename")])
        self.image_view.clear()
        self.table_view.selectionModel().clearSelection()
        self.prev_selected_rows = []

    def load_csv_data(self):
        csv_path = os.path.join(self.edtDirectory.text(), self.csv_file)
        self.image_data = image_data.read_csv(csv_path)
        for slot in self.image_data:
            checkbox_item = QStandardItem()
            checkbox_item.setCheckable(True)
            checkbox_item.setCheckState(Qt.Checked if slot.include else Qt.Unchecked)
            self.image_model.appendRow([checkbox_item, QStandardItem(slot.filename)])
        self.table_view.selectRow(0)

    def load_image_files(self):
        slots = image_data.detect_irregular_intervals(self.current_directory)
        if len(slots) == self.number_of_LEDs:
            self.image_data.extend(slots)
            self.update_csv()
            self.load_csv_data()
        else:
            self.statusBar.showMessage(
                self.tr("Image files not found or not enough images in the directory."), 5000
            )

    def sync_checkbox_states_to_image_data(self):
        """Copy the table's checkboxes back into the capture table."""
        for row in range(self.image_model.rowCount()):
            checkbox_item = self.image_model.item(row, 0)
            if checkbox_item and row < len(self.image_data):
                slot = self.image_data[row]
                self.image_data[row] = slot._replace(
                    include=checkbox_item.checkState() == Qt.Checked
                )

    def update_csv(self):
        self.sync_checkbox_states_to_image_data()
        image_data.write_csv(os.path.join(self.current_directory, self.csv_file), self.image_data)

    def on_selection_changed(self, selected, deselected):
        self.selected_rows = sorted(
            {index.row() for index in self.table_view.selectionModel().selectedIndexes()}
        )
        for row in self.selected_rows:
            if row not in self.prev_selected_rows and row < len(self.image_data):
                slot = self.image_data[row]
                if slot.captured:
                    self.show_image(os.path.join(slot.directory, slot.filename))
        self.prev_selected_rows = self.selected_rows

    def show_image(self, image_file):
        self.image_view.setPixmap(
            QPixmap(image_file).scaled(self.image_view.size(), Qt.KeepAspectRatio)
        )

    # -- actions ------------------------------------------------------------

    def on_action_open_directory_triggered(self):
        directory = QFileDialog.getExistingDirectory(self, self.tr("Open Directory"))
        if not directory:
            return
        self.current_directory = directory
        self.edtDirectory.setText(directory)
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
        """Write the .lp file and hand it to PTMfitter."""
        if not os.path.exists(self.ptm_fitter):
            self.statusBar.showMessage(f"PTM fitter not found: {self.ptm_fitter}", 5000)
            QMessageBox.critical(self, self.tr("Error"), f"PTM fitter not found: {self.ptm_fitter}")
            return

        self.sync_checkbox_states_to_image_data()
        if not self.image_data:
            QMessageBox.critical(self, self.tr("Error"), self.tr("No images to process."))
            return

        vectors = light_vectors(self.light_position_adjustment)
        content = ptm_builder.build_lp_content(self.image_data, vectors)
        image_directory = self.image_data[0].directory
        lp_path = ptm_builder.lp_path_for(image_directory)
        ptm_builder.write_lp(lp_path, content)

        ptm_filename, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save PTM file"),
            str(self.current_directory),
            "PTM files (*.ptm);;All files (*)",
        )
        if ptm_filename:
            ptm_builder.run_fitter(self.ptm_fitter, lp_path, ptm_filename)

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
        self.update()

"""The Edit > Preferences dialog."""

import os

from PyQt5.QtCore import QRect, QSettings, QTranslator
from PyQt5.QtGui import QDoubleValidator, QIcon, QIntValidator
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from core import settings as prefs
from core.resources import icon_path, translation_path
from version import COMPANY_NAME, PROGRAM_NAME


class PreferencesWindow(QDialog):
    """Reads and writes the QSettings the rest of the app runs on.

    Everything here is stored under `PaleoBytes / PTMGenerator2`; see
    core.settings for the keys and their defaults.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initialize_variables(parent)
        self.setup_ui()

    def initialize_variables(self, parent):
        self.parent = parent
        self.m_app = QApplication.instance()
        self.current_translator = None
        self.settings = QSettings(
            QSettings.IniFormat, QSettings.UserScope, COMPANY_NAME, PROGRAM_NAME
        )

    def setup_ui(self):
        self.setWindowTitle(self.tr("Preferences"))
        self.setWindowIcon(QIcon(icon_path("app")))

        self.language_label = QLabel(self.tr("Language"))
        self.language_combobox = QComboBox()
        for label, code in prefs.SUPPORTED_LANGUAGES:
            self.language_combobox.addItem(label, code)

        self.lblSerialPort = QLabel(self.tr("Serial Port"))
        self.comboSerialPort = QComboBox()
        self._populate_serial_ports()

        self.lblPtmFitter = QLabel(self.tr("PTM Fitter"))
        self.edtPtmFitter = QLineEdit()
        self.btnPtmFitter = QPushButton(self.tr("Browse"))
        self.btnPtmFitter.clicked.connect(self.on_browse_ptm_fitter)

        self.ptmfitter_widget = QWidget()
        self.ptmfitter_layout = QHBoxLayout()
        self.ptmfitter_widget.setLayout(self.ptmfitter_layout)
        self.ptmfitter_layout.addWidget(self.edtPtmFitter)
        self.ptmfitter_layout.addWidget(self.btnPtmFitter)

        self.lblNumberOfLEDs = QLabel(self.tr("Number of LEDs"))
        self.edtNumberOfLEDs = QLineEdit()
        self.edtNumberOfLEDs.setValidator(QIntValidator())

        self.lblRetryCount = QLabel(self.tr("Retry Count"))
        self.edtRetryCount = QLineEdit()
        self.edtRetryCount.setValidator(QIntValidator())

        self.lblPostShutterPolling = QLabel(self.tr("Post Shutter Polling"))
        self.edtPostShutterPolling = QLineEdit()
        # Seconds, and fractions of one are the useful range -- an int
        # validator here made 0.5 impossible to type while the default
        # displayed as "1.0".
        self.edtPostShutterPolling.setValidator(QDoubleValidator(0.0, 60.0, 2))

        self.lblLightPositionAdjustment = QLabel(self.tr("Light Position Adjustment"))
        self.edtLightPositionAdjustment = QLineEdit()
        self.edtLightPositionAdjustment.setValidator(QIntValidator())

        self.btnOkay = QPushButton(self.tr("OK"))
        self.btnOkay.clicked.connect(self.Okay)

        self.layout = QFormLayout()
        self.layout.addRow(self.language_label, self.language_combobox)
        self.layout.addRow(self.lblSerialPort, self.comboSerialPort)
        self.layout.addRow(self.lblPtmFitter, self.ptmfitter_widget)
        self.layout.addRow(self.lblNumberOfLEDs, self.edtNumberOfLEDs)
        self.layout.addRow(self.lblRetryCount, self.edtRetryCount)
        self.layout.addRow(self.lblPostShutterPolling, self.edtPostShutterPolling)
        self.layout.addRow(self.lblLightPositionAdjustment, self.edtLightPositionAdjustment)
        self.layout.addRow(self.btnOkay)
        self.setLayout(self.layout)

        self.read_settings()

        self.language_combobox.currentIndexChanged.connect(
            self.language_combobox_currentIndexChanged
        )

        self.language_combobox.setCurrentIndex(self.language_combobox.findData(self.language))
        self.comboSerialPort.setCurrentIndex(self.comboSerialPort.findData(self.serial_port))
        self.edtPtmFitter.setText(self.ptm_fitter)
        self.edtNumberOfLEDs.setText(str(self.number_of_LEDs))
        self.edtRetryCount.setText(str(self.retry_count))
        self.edtLightPositionAdjustment.setText(str(self.light_position_adjustment))
        self.edtPostShutterPolling.setText(str(self.post_shutter_polling))

    def _populate_serial_ports(self):
        """List the ports present, or a single "None" entry if there are none."""
        import serial.tools.list_ports

        ports = list(serial.tools.list_ports.comports())
        for port in ports:
            self.comboSerialPort.addItem(f"{port.device} - {port.description}", port.device)
        if not ports:
            self.comboSerialPort.addItem("None", "None")

    def Okay(self):
        self.save_settings()
        self.accept()

    def on_browse_ptm_fitter(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, self.tr("Select PTM Fitter"), "", "Executable Files (*.exe)"
        )
        if filename:
            self.edtPtmFitter.setText(filename)

    def read_settings(self):
        self.m_app.settings = QSettings(
            QSettings.IniFormat, QSettings.UserScope, COMPANY_NAME, PROGRAM_NAME
        )
        s = self.m_app.settings
        self.remember_geometry = prefs.value_to_bool(
            s.value("WindowGeometry/RememberGeometry", True)
        )
        if self.remember_geometry:
            self.setGeometry(s.value("WindowGeometry/PreferencesWindow", QRect(100, 100, 500, 250)))
            if prefs.value_to_bool(s.value("IsMaximized/PreferencesWindow", False)):
                self.showMaximized()
            else:
                self.showNormal()
        else:
            self.setGeometry(QRect(100, 100, 500, 250))

        self.serial_port = prefs.read_str(s, prefs.SERIAL_PORT)
        self.ptm_fitter = prefs.read_str(s, prefs.PTM_FITTER)
        self.number_of_LEDs = prefs.read_int(s, prefs.NUMBER_OF_LEDS)
        self.retry_count = prefs.read_int(s, prefs.RETRY_COUNT)
        self.light_position_adjustment = prefs.read_int(s, prefs.LIGHT_POSITION_ADJUSTMENT)
        self.post_shutter_polling = prefs.read_float(s, prefs.POST_SHUTTER_POLLING)
        self.language = prefs.read_str(s, prefs.LANGUAGE)
        self.prev_language = self.language
        self.update_language(self.language)

    def save_settings(self):
        s = self.m_app.settings
        s.setValue("WindowGeometry/PreferencesWindow", self.geometry())
        s.setValue("IsMaximized/PreferencesWindow", self.isMaximized())
        s.setValue(prefs.LANGUAGE, self.language_combobox.currentData())
        s.setValue(prefs.SERIAL_PORT, self.comboSerialPort.currentData())
        s.setValue(prefs.PTM_FITTER, self.edtPtmFitter.text())
        s.setValue(prefs.NUMBER_OF_LEDS, str(self.edtNumberOfLEDs.text()))
        s.setValue(prefs.RETRY_COUNT, str(self.edtRetryCount.text()))
        s.setValue(prefs.LIGHT_POSITION_ADJUSTMENT, str(self.edtLightPositionAdjustment.text()))
        s.setValue(prefs.POST_SHUTTER_POLLING, str(self.edtPostShutterPolling.text()))

    def language_combobox_currentIndexChanged(self, index):
        self.language = self.language_combobox.currentData()
        self.update_language(self.language)

    def update_language(self, language):
        """Swap the application translator and re-label everything on screen."""
        if self.m_app.translator is not None:
            self.m_app.removeTranslator(self.m_app.translator)
            self.m_app.translator = None

        path = translation_path(language)
        if os.path.exists(path):
            translator = QTranslator()
            translator.load(path)
            self.m_app.installTranslator(translator)
            self.m_app.translator = translator

        self.setWindowTitle(self.tr("Preferences"))
        self.language_label.setText(self.tr("Language"))
        self.lblSerialPort.setText(self.tr("Serial Port"))
        self.lblPtmFitter.setText(self.tr("PTM Fitter"))
        self.btnPtmFitter.setText(self.tr("Browse"))
        self.lblNumberOfLEDs.setText(self.tr("Number of LEDs"))
        self.lblRetryCount.setText(self.tr("Retry Count"))
        # These two were left out, so switching language mid-session relabelled
        # every row but these.
        self.lblPostShutterPolling.setText(self.tr("Post Shutter Polling"))
        self.lblLightPositionAdjustment.setText(self.tr("Light Position Adjustment"))
        self.btnOkay.setText(self.tr("OK"))
        self.update()


__all__ = ["PreferencesWindow"]

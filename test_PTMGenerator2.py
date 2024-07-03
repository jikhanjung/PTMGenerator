import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from PyQt5.QtCore import QObject, pyqtSignal, QRect

from PTMGenerator2 import OutputRedirector, PTMGeneratorMainWindow, resource_path, PreferencesWindow

class ResourcePathTests(unittest.TestCase):
    def test_relative_path(self):
        # Test with a relative path
        result = resource_path("icons/open_directory.png")
        expected = os.path.join(os.path.abspath("."), "icons/open_directory.png")
        self.assertEqual(result, expected)

    def test_absolute_path(self):
        # Test with an absolute path
        result = resource_path("/path/to/file.txt")
        expected = "/path/to/file.txt"
        self.assertEqual(result, expected)

    def test_sys_meipass(self):
        # Test when sys._MEIPASS is defined
        sys._MEIPASS = "/path/to/meipass"
        result = resource_path("icons/open_directory.png")
        expected = os.path.join("/path/to/meipass", "icons/open_directory.png")
        self.assertEqual(result, expected)
        del sys._MEIPASS

    def test_exception(self):
        # Test when an exception is raised
        def raise_exception():
            raise Exception("Error")

        sys._MEIPASS = raise_exception
        result = resource_path("icons/open_directory.png")
        expected = os.path.join(os.path.abspath("."), "icons/open_directory.png")
        self.assertEqual(result, expected)
        del sys._MEIPASS

class OutputRedirectorTests(unittest.TestCase):
    def test_write(self):
        file_path = "test_output.log"
        redirector = OutputRedirector(file_path)
        redirector.stdout = MagicMock()
        redirector.file = MagicMock()

        message = "Test message"
        redirector.write(message)

        redirector.stdout.write.assert_called_once_with(message)
        redirector.file.write.assert_called_once_with(message)
        redirector.file.flush.assert_called_once()
        redirector.output_written.emit.assert_called_once_with(message)

    def test_flush(self):
        file_path = "test_output.log"
        redirector = OutputRedirector(file_path)
        redirector.stdout = MagicMock()
        redirector.file = MagicMock()

        redirector.flush()

        redirector.stdout.flush.assert_called_once()
        redirector.file.flush.assert_called_once()

    def test_close(self):
        file_path = "test_output.log"
        redirector = OutputRedirector(file_path)
        redirector.file = MagicMock()

        redirector.close()

        redirector.file.close.assert_called_once()

class PreferencesWindowTests(unittest.TestCase):
    def test_read_settings(self):
        # Create an instance of PreferencesWindow
        preferences_window = PreferencesWindow()

        # Set the values for the settings
        preferences_window.m_app.settings.setValue("WindowGeometry/RememberGeometry", True)
        preferences_window.m_app.settings.setValue("WindowGeometry/PreferencesWindow", QRect(100, 100, 500, 250))
        preferences_window.m_app.settings.setValue("IsMaximized/PreferencesWindow", False)
        preferences_window.m_app.settings.setValue("language", "en")
        preferences_window.m_app.settings.setValue("serial_port", "/dev/ttyUSB0")
        preferences_window.m_app.settings.setValue("ptm_fitter", "ptmfitter.exe")
        preferences_window.m_app.settings.setValue("Number_of_LEDs", "50")
        preferences_window.m_app.settings.setValue("RetryCount", "0")

        # Call the read_settings method
        preferences_window.read_settings()

        # Check if the values are correctly set
        self.assertEqual(preferences_window.remember_geometry, True)
        self.assertEqual(preferences_window.geometry(), QRect(100, 100, 500, 250))
        self.assertEqual(preferences_window.isMaximized(), False)
        self.assertEqual(preferences_window.language, "en")
        self.assertEqual(preferences_window.language_combobox.currentData(), "en")
        self.assertEqual(preferences_window.serial_port, "/dev/ttyUSB0")
        self.assertEqual(preferences_window.comboSerialPort.currentData(), "/dev/ttyUSB0")
        self.assertEqual(preferences_window.ptm_fitter, "ptmfitter.exe")
        self.assertEqual(preferences_window.edtPtmFitter.text(), "ptmfitter.exe")
        self.assertEqual(preferences_window.number_of_LEDs, 50)
        self.assertEqual(preferences_window.edtNumberOfLEDs.text(), "50")
        self.assertEqual(preferences_window.retry_count, 0)
        self.assertEqual(preferences_window.edtRetryCount.text(), "0")

if __name__ == "__main__":
    unittest.main()
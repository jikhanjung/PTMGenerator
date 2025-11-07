from PyQt5.QtWidgets import QMainWindow, QApplication, QMessageBox, QTableView, QAction, \
                            QStatusBar, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, \
                            QFileDialog, QDialog, QComboBox, QInputDialog, QWidget, QFormLayout
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem, QPixmap, QIntValidator
from PyQt5.QtCore import Qt, QRect, QSettings, QTimer, QTranslator, QObject, pyqtSignal

import serial
import serial.tools.list_ports

import sys, os, time, csv, math
from pathlib import Path
from datetime import datetime
import subprocess

COMPANY_NAME = "PaleoBytes"
PROGRAM_NAME = "PTMGenerator2"
PROGRAM_VERSION = "0.1.2"

POLAR_LIGHT_LIST = [[85, 330], [84, 108], [83, 245], [82, 23], [81, 160], [80, 298], [79, 76], [78, 213], [77, 351], [76, 128],
 [75, 266], [74, 43], [73, 181], [71, 318], [70, 96], [69, 233], [68, 11], [67, 148], [66, 286], [65, 63],
 [64, 201], [62, 338], [61, 116], [60, 253], [59, 31], [58, 168], [56, 306], [55, 83], [54, 221], [52, 358],
 [51, 136], [50, 273], [48, 51], [47, 188], [46, 326], [44, 103], [43, 241], [41, 18], [39, 156], [38, 293],
 [36, 71], [34, 208], [32, 346], [30, 123], [28, 261], [26, 38], [23, 176], [21, 313], [17, 91], [13, 228]]




def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def value_to_bool(value):
    return value.lower() == 'true' if isinstance(value, str) else bool(value)

ICON = {}
ICON['open_directory'] = resource_path('icons/open_directory.png')
PTM_IMAGE_COUNT = 50
AUTO_RETAKE_MAXIMUM = 0

class OutputRedirector(QObject):
    output_written = pyqtSignal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self.stdout = sys.stdout
        self.file = open(file_path, 'w')

    def write(self, message):
        if self.stdout is not None:
            self.stdout.write(message)
        #self.stdout.write(message)
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
    """
    Main window class for the PTMGenerator application.

    This class represents the main window of the PTMGenerator application. It contains various widgets and functionality
    for controlling the image capturing and PTM generation process.

    Attributes:
        selected_indices (list): A list of selected row indices in the image table.
        image_data (list): A list of image data containing the filename and other information.
        failed_list (list): A list of failed image captures.
        current_index (int): The index of the currently selected image.
        status (str): The current status of the application.
        second_counter (int): A counter for tracking the elapsed time.
        csv_file (str): The path to the CSV file for storing image data.
        last_checked (float): The timestamp of the last check for new images.
        current_directory (str): The current directory for image capture.
        preparation_time (int): The time in seconds for preparation before capturing an image.
        auto_retake (bool): Flag indicating whether to automatically retake failed images.
        auto_retake_maximum (int): The maximum number of retakes allowed for a single image.
        retake_counter (int): The counter for tracking the number of retakes for a single image.
        polling_timeout (int): The timeout in seconds for polling for new images.
        image_index_list (list): A list of indices of images to be captured.
        previous_index (int): The index of the previously selected image.
        serial_port (str): The serial port for communication with external devices.
        serial_exist (bool): Flag indicating whether a serial port is available.
        prev_selected_rows (list): A list of previously selected row indices in the image table.
        redirector (OutputRedirector): An instance of the OutputRedirector class for redirecting stdout.
        table_view (QTableView): The table view widget for displaying image data.
        image_view (QLabel): The label widget for displaying the selected image.
        image_list_widget (QWidget): The widget for containing the table view and image view.
        image_model (QStandardItemModel): The model for the image table view.
        statusBar (QStatusBar): The status bar widget.
        lblDirectory (QLabel): The label widget for displaying the current directory.
        btnOpenDirectory (QPushButton): The button widget for opening the directory.
        edtDirectory (QLineEdit): The line edit widget for displaying the current directory path.
        directory_widget (QWidget): The widget for containing the directory-related widgets.
        btnTestShot (QPushButton): The button widget for performing a test shot.
        btnTakeAllPictures (QPushButton): The button widget for capturing all images.
        btnRetakePicture (QPushButton): The button widget for retaking a single image.
        btnPauseContinue (QPushButton): The button widget for pausing/continuing the image capture process.
        btnStop (QPushButton): The button widget for stopping the image capture process.
        btnGeneratePTM (QPushButton): The button widget for generating the PTM.
        button_widget (QWidget): The widget for containing the buttons.
        central_widget (QWidget): The central widget of the main window.
        actionOpenDirectory (QAction): The action for opening the directory.
        actionPreferences (QAction): The action for opening the preferences dialog.
        actionAbout (QAction): The action for opening the about dialog.
        main_menu (QMenuBar): The main menu bar.
        file_menu (QMenu): The file menu.
        edit_menu (QMenu): The edit menu.
        help_menu (QMenu): The help menu.
        m_app (QApplication): The instance of the QApplication.
        timer (QTimer): The timer for capturing images at regular intervals.

    """

    def __init__(self):
        """
        Initializes the PTMGenerator2 class.

        Sets up the window properties, initializes instance variables, and sets up the user interface.
        """
        super().__init__()
        self.initialize_variables()
        self.setup_ui()

    def initialize_variables(self):
        self.selected_indices = []
        self.image_data = []
        self.failed_list = []
        self.current_index = -1
        self.status = "idle"
        self.second_counter = 0
        self.csv_file = 'image_data.csv'  # Change this to your desired CSV file path
        self.last_checked = time.time()
        self.current_directory = "."
        self.preparation_time = 2

        self.auto_retake = True
        self.auto_retake_maximum = AUTO_RETAKE_MAXIMUM
        self.retake_counter = 0
        self.polling_timeout = 5
        self.image_index_list = []
        self.previous_index = -1
        self.serial_port = None
        self.serial_exist = False
        self.prev_selected_rows = []

        self.redirector = OutputRedirector("output.log")
        sys.stdout = self.redirector

    def setup_ui(self):
        self.setWindowIcon(QIcon(resource_path('icons/PTMGenerator2.png')))
        self.setWindowTitle("{} v{}".format(self.tr("PTMGenerator2"), PROGRAM_VERSION))

        self.table_view = QTableView()
        self.image_view = QLabel()

        self.image_list_widget = QWidget()
        self.image_list_layout = QHBoxLayout()
        self.image_list_widget.setLayout(self.image_list_layout)
        self.image_list_layout.addWidget(self.table_view, 1)
        self.image_list_layout.addWidget(self.image_view, 4)

        self.image_model = QStandardItemModel()
        self.image_model.setHorizontalHeaderLabels([self.tr('Include'), self.tr('Filename')])
        self.table_view.setModel(self.image_model)
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(0, header.ResizeToContents)  # Include column
        header.setSectionResizeMode(1, header.Stretch)  # Filename column
        self.table_view.selectionModel().selectionChanged.connect(self.on_selection_changed)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

        self.lblDirectory = QLabel(self.tr("Directory"))
        self.btnOpenDirectory = QPushButton(self.tr("Open Directory"))
        self.btnOpenDirectory.setIcon(QIcon(resource_path(ICON['open_directory'])))
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
        self.button_layout.addWidget(self.btnTestShot)
        self.button_layout.addWidget(self.btnTakeAllPictures)
        self.button_layout.addWidget(self.btnRetakePicture)
        self.button_layout.addWidget(self.btnPauseContinue)
        self.button_layout.addWidget(self.btnStop)
        self.button_layout.addWidget(self.btnGeneratePTM)

        self.central_widget = QWidget()
        self.central_layout = QVBoxLayout()
        self.central_widget.setLayout(self.central_layout)
        self.central_layout.addWidget(self.directory_widget)
        self.central_layout.addWidget(self.image_list_widget)
        self.central_layout.addWidget(self.button_widget)

        self.setCentralWidget(self.central_widget)

        ''' setup actions '''
        self.actionOpenDirectory = QAction(QIcon(resource_path(ICON['open_directory'])), self.tr("Open Directory\tCtrl+O"), self)
        self.actionOpenDirectory.triggered.connect(self.on_action_open_directory_triggered)
        self.actionPreferences = QAction(self.tr("Preferences"), self)
        self.actionPreferences.triggered.connect(self.on_action_preferences_triggered)
        self.actionAbout = QAction(self.tr("About"), self)
        self.actionAbout.triggered.connect(self.on_action_about_triggered)

        ''' setup menu '''
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

    def read_settings(self):
        self.m_app.settings = QSettings(QSettings.IniFormat, QSettings.UserScope, COMPANY_NAME, PROGRAM_NAME)
        self.m_app.remember_geometry = value_to_bool(self.m_app.settings.value("WindowGeometry/RememberGeometry", True))
        if self.m_app.remember_geometry is True:
            self.setGeometry(self.m_app.settings.value("WindowGeometry/MainWindow", QRect(100, 100, 1400, 800)))
            is_maximized = value_to_bool(self.m_app.settings.value("IsMaximized/MainWindow", False))
            if is_maximized:
                self.showMaximized()
            else:
                self.showNormal()
        else:
            self.setGeometry(QRect(100, 100, 1400, 800))
        self.m_app.serial_port = self.m_app.settings.value("serial_port", None)
        self.m_app.language = self.m_app.settings.value("language", "en")
        #print("Serial port:", self.m_app.serial_port)
        self.ptm_fitter = self.m_app.settings.value("ptm_fitter", "ptmfitter.exe")
        if self.m_app.serial_port is not None:
            self.serial_exist = True
            self.serial_port = self.m_app.serial_port
            #self.openSerial()
        else:
            self.serial_exist = False
        self.number_of_LEDs = int(self.m_app.settings.value("Number_of_LEDs", PTM_IMAGE_COUNT))
        self.auto_retake_maximum = int(self.m_app.settings.value("RetryCount", AUTO_RETAKE_MAXIMUM))
        self.light_position_adjustment = int(self.m_app.settings.value("light_position_adjustment", 0))
        self.post_shutter_polling = float(self.m_app.settings.value("post_shutter_polling", 1))
        #print("read setting language:", self.m_app.language)
        self.update_language(self.m_app.language)
        

    def save_settings(self):
        self.m_app.settings.setValue("WindowGeometry/MainWindow", self.geometry())
        self.m_app.settings.setValue("IsMaximized/MainWindow", self.isMaximized())

    def pause_continue_process(self):
        if self.timer.isActive():
            self.timer.stop()
            self.statusBar.showMessage(self.tr("Paused"), 1000)
            self.btnPauseContinue.setText(self.tr("Continue"))
            #self.b.setEnabled(True)
        else:
            self.timer.start()
            self.statusBar.showMessage(self.tr("Continued"), 1000)
            self.btnPauseContinue.setText(self.tr("Pause"))

    def stop_process(self):
        self.timer.stop()
        self.image_index_list = []
        #self.sendSerial("OFF")
        self.closeSerial()
        self.statusBar.showMessage(self.tr("Stopped"), 1000)

    def test_shot(self):
        #self.turn_on_led(self.number_of_LEDs-1)
        #time.sleep(1)
        self.openSerial()
        self.take_shot()
        time.sleep(1)
        new_image = None
        count = 0
        while new_image is None and count < 5:
            time.sleep(3)
            new_image = self.get_incoming_image(self.current_directory)
            count += 1

        if new_image is None:
            print("Failed to get image file")
            self.statusBar.showMessage("Failed to get image file", 1000)
        else:
            print(f"New image detected: {new_image}")
            self.statusBar.showMessage(f"New image detected: {new_image}", 1000)

        self.closeSerial()


    def on_selection_changed(self,selected, deselected):
        # Iterate over selected indexes
        self.selected_rows = []
        for model_index in self.table_view.selectionModel().selectedRows():
            row = model_index.row()
            self.selected_rows.append(row)
            if row not in self.prev_selected_rows:
                self.last_selected_row = row
                # image_data structure: (index, directory, filename, include)
                self.show_image( os.path.join( self.image_data[row][1], self.image_data[row][2]) )
            print(f"Row {row} selected")
            #self.selected_indices.append(model_index)
        #print("Selected indices:", self.selected_indices)

        self.prev_selected_rows = self.selected_rows

    def on_action_open_directory_triggered(self):
        directory = QFileDialog.getExistingDirectory(self, self.tr("Open Directory"))
        if directory:
            self.current_directory = directory
            self.edtDirectory.setText(directory)
            self.clear_image_data()
            csv_path = os.path.join(self.current_directory, self.csv_file)
            if os.path.exists(self.current_directory):
                if os.path.exists(csv_path):
                    #self.clear_image_data()
                    self.load_csv_data()    
                else:
                    self.load_image_files()

    def load_image_files(self):
        image_data = self.detect_irregular_intervals(self.current_directory)

        if len(image_data) == self.number_of_LEDs:
            for i, directory, filename, include in image_data:
                self.image_data.append((i, directory, filename, include))
            self.update_csv()
            self.load_csv_data()
        else:
            print("Image files not found or not enough images in the directory.")
            self.statusBar.showMessage(self.tr("Image files not found or not enough images in the directory."), 5000)

    def on_action_preferences_triggered(self):
        preferences = PreferencesWindow(self)
        preferences.exec()
        self.read_settings()
        #self.update_language(self.m_app.language)

    def on_action_about_triggered(self):
        QMessageBox.about(self, self.tr("About"), "{} v{}".format(self.tr("PTMGenerator2"), PROGRAM_VERSION))

    def turn_on_led(self, led_index):
        msg = "ON," + str(led_index + 1)
        self.sendSerial(msg)

        print(f"Turning on LED {led_index+1}")

    def take_shot(self):
        msg = "SHOOT," + str(self.current_index + 1)
        ret_msg = self.sendSerial( msg )
        print("Taking a shot with the DSLR")

    def get_incoming_image(self, directory):
        print(f"Polling for incoming image files in {directory}...")
        newest_time = self.last_checked
        print(f"Last checked time: {newest_time}, sleeping for: {self.post_shutter_polling}")
        time.sleep(self.post_shutter_polling)

        newest_file = None
        base_path = Path(directory)

        # Define image extensions once
        IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff'}

        # Use glob pattern matching - much faster than checking each file
        # glob only checks the specified directory, not subdirectories
        for filepath in base_path.glob('*'):
            # Skip directories
            if not filepath.is_file():
                continue
                
            # Check extension using set lookup (faster than multiple endswith checks)
            if filepath.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
                
            file_time = filepath.stat().st_mtime
            if file_time > newest_time:
                newest_time = file_time
                newest_file = str(filepath)
                print(f"[#{self.current_index+1}-{self.retake_counter}] New image detected: {newest_file} ({newest_time})")

        if newest_file is not None:
            self.last_checked = newest_time
            return newest_file
        return None

    def take_picture_process(self):
        #self.second_counter += 1
        '''if self.status == "idle":
            self.status = "taking_picture"
            if self.current_index != self.previous_index:
                self.last_checked = time.time()
            self.statusBar.showMessage(f"[#{self.current_index+1}-{self.retake_counter}] Turning on LED #{self.current_index+1}...", 1000)
            self.turn_on_led(self.current_index)
            self.second_counter = 0
        el'''
        if self.status == "idle":
            self.status = "preparing picture"
            if self.current_index != self.previous_index:
                self.last_checked = time.time()
            print("Taking picture...", self.current_index+1, self.image_index_list)
            #if self.second_counter == 0:
            self.take_shot()
            self.statusBar.showMessage(f"[#{self.current_index+1}-{self.retake_counter}] [{self.second_counter}] Preparing picture...{self.second_counter}", 1000)
            self.second_counter += 1
        elif self.status == "preparing picture":
            if self.second_counter == self.preparation_time:
                self.status = "polling"
                self.statusBar.showMessage(f"[#{self.current_index+1}-{self.retake_counter}] [{self.second_counter}] Taking picture...{self.second_counter}", 1000)
            else:
                self.statusBar.showMessage(f"[#{self.current_index+1}-{self.retake_counter}] [{self.second_counter}] Preparing picture...{self.second_counter}", 1000)
            self.second_counter += 1
                #self.second_counter = 0
                #return
        elif self.status == "polling":
            self.statusBar.showMessage(f"[#{self.current_index+1}-{self.retake_counter}] [{self.second_counter}] Polling for image file...{self.second_counter}", 1000)
            new_image = self.get_incoming_image(self.current_directory)
            if new_image is None:
                if self.second_counter < self.polling_timeout:
                    self.second_counter += 1
                    return
                else:
                    # Failed to get image file
                    self.statusBar.showMessage(f"[#{self.current_index+1}-{self.retake_counter}] [{self.second_counter}] Failed to get image file", 1000)
                    print(f"[#{self.current_index+1}-{self.retake_counter}] Failed to get image file", self.current_index+1)

                    # Retake picture
                    if self.retake_counter < self.auto_retake_maximum:
                        self.retake_counter += 1
                        self.statusBar.showMessage(f"[#{self.current_index+1}-{self.retake_counter}] [{self.second_counter}] Retaking picture... retry {self.retake_counter}...", 1000)
                        self.second_counter = 0
                        self.status = "idle"
                        return

                    # failed to get an image and no more retake
                    name = "-"
                    checkbox_item = QStandardItem()
                    checkbox_item.setCheckable(True)
                    checkbox_item.setCheckState(Qt.Unchecked)  # Failed images unchecked by default
                    filename_item = QStandardItem(name)
                    if self.current_index < self.table_view.model().rowCount():
                        self.table_view.model().setItem(self.current_index, 0, checkbox_item)
                        self.table_view.model().setItem(self.current_index, 1, filename_item)
                        self.image_data[self.current_index] = (self.current_index, name, name, False)
                    else:
                        self.table_view.model().appendRow([checkbox_item, filename_item])
                        self.image_data.append((self.current_index, name, name, False))
            else:
                # got a new image!
                self.statusBar.showMessage(f"[#{self.current_index+1}-{self.retake_counter}] [{self.second_counter}] New image detected: {new_image}", 1000)
                print(f"[#{self.current_index+1}-{self.retake_counter}] [{self.second_counter}] New image detected: {new_image}")
                directory, filename = os.path.split(new_image)
                #self.add_imagefile(self.current_index, filename)
                checkbox_item = QStandardItem()
                checkbox_item.setCheckable(True)
                checkbox_item.setCheckState(Qt.Checked)  # Successful images checked by default
                filename_item = QStandardItem(filename)
                if self.current_index < self.table_view.model().rowCount():
                    self.table_view.model().setItem(self.current_index, 0, checkbox_item)
                    self.table_view.model().setItem(self.current_index, 1, filename_item)
                    self.image_data[self.current_index] = (self.current_index, directory, filename, True)
                else:
                    self.table_view.model().appendRow([checkbox_item, filename_item])
                    self.image_data.append((self.current_index, directory, filename, True))
                self.show_image(new_image)

            self.second_counter = 0
            self.retake_counter = 0
            self.status = "idle"
            self.previous_index = self.current_index
            if len(self.image_index_list) > 0:
                self.current_index = self.image_index_list.pop(0)
            else:
                self.timer.stop()
                self.statusBar.showMessage(f"All pictures ({self.number_of_LEDs}) taken", 5000)
                #self.label.setText("All pictures taken")
                self.status = "idle"
                self.update_csv()
                self.btnPauseContinue.setText(self.tr("Pause/Continue"))
                #self.sendSerial("OFF")
                self.closeSerial()


    def show_image(self, image_file):
        print("Showing image:", image_file)
        self.image_view.setPixmap(QPixmap(image_file).scaled(self.image_view.size(), Qt.KeepAspectRatio))

    def take_all_pictures(self):
        period = 1000
        self.last_checked = time.time()
        self.image_index_list = []
        self.btnPauseContinue.setText(self.tr("Pause"))
        self.clear_image_data()

        for i in range(self.number_of_LEDs):
            self.image_index_list.append(i)
            #self.image_data.append((i, "-"))
        self.image_list = []
        self.previous_index = -1
        self.openSerial()
        self.current_index = self.image_index_list.pop(0)
        self.timer.start(period)  # Poll every 1 second

    def clear_image_data(self):
        self.image_data = []
        self.image_model.clear()
        self.image_model.setHorizontalHeaderLabels([self.tr('Include'), self.tr('Filename')])
        self.image_view.clear()
        self.table_view.selectionModel().clearSelection()
        self.prev_selected_rows = []
        #self.update_csv()        

    def load_csv_data(self):
        self.path = self.edtDirectory.text()
        csv_path = os.path.join(self.path, self.csv_file)
        print("Loading data from CSV:", csv_path)
        if os.path.exists(csv_path):

            with open(csv_path, 'r', newline='') as csvfile:
                csvreader = csv.reader(csvfile)
                for row in csvreader:
                    print("Row:", row)
                    # Support both old format (3 elements) and new format (4 elements)
                    if len(row) == 3:
                        # Old format: (index, directory, filename) - default include=True
                        index, directory, filename = row
                        include = True
                    elif len(row) == 4:
                        # New format: (index, directory, filename, include)
                        index, directory, filename, include_str = row
                        include = include_str.lower() == 'true'
                    else:
                        continue  # Skip invalid rows

                    self.image_data.append((int(index), directory, filename, include))

                    # Add checkbox and filename to table
                    checkbox_item = QStandardItem()
                    checkbox_item.setCheckable(True)
                    checkbox_item.setCheckState(Qt.Checked if include else Qt.Unchecked)
                    filename_item = QStandardItem(filename)
                    self.image_model.appendRow([checkbox_item, filename_item])
            print(f"Loaded data from CSV: {self.image_data}")
        else:
            print("CSV file not found:", csv_path)
        self.table_view.selectRow(0)

    def add_imagefile(self, index, filename):
        csv_path = os.path.join(self.current_directory, self.csv_file)
        with open(csv_path, 'a', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow([index, filename])
        self.image_data.append((index, filename))
        print(f"Logged to CSV: Index [{index}], Filename - [{filename}]")

    def sync_checkbox_states_to_image_data(self):
        """Synchronize checkbox states from table to image_data"""
        for row in range(self.image_model.rowCount()):
            checkbox_item = self.image_model.item(row, 0)
            if checkbox_item and row < len(self.image_data):
                is_checked = checkbox_item.checkState() == Qt.Checked
                # Update include flag in image_data
                i, directory, image_name, _ = self.image_data[row]
                self.image_data[row] = (i, directory, image_name, is_checked)

    def update_csv(self):
        # Sync checkbox states before saving
        self.sync_checkbox_states_to_image_data()
        csv_path = os.path.join(self.current_directory, self.csv_file)
        with open(csv_path, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerows(self.image_data)

    def on_retake_picture_triggered(self):
        period = 1000
        self.image_index_list = []
        if len(self.selected_rows) == 0:
            return
        self.image_index_list = sorted(self.selected_rows)
        print("Retake picture list:", self.image_index_list)
        self.previous_index = -1
        self.current_index = self.image_index_list.pop(0)
        self.btnPauseContinue.setText(self.tr("Pause"))
        self.openSerial()
        self.timer.start(period)  # Poll every 1 second

    def openSerial(self):
        print("Opening serial port...") 
        if self.serial_exist == False:
            print("Serial port not found 1")
            return
        if self.serial_port is None or self.serial_port == "" or self.serial_port == "None":
            print("Serial port not found 2")
            self.serial_exist = False
            return
        print("Serial port:", self.serial_port)
        self.serial = serial.Serial(self.serial_port, 9600, timeout=2)
        time.sleep(2)

    def closeSerial(self):
        self.sendSerial("OFF")
        self.serial.close()

    def sendSerial(self,msg):
        msg = "<" + msg + ">"
        print( msg )
        self.serial.write( msg.encode() )

    def receiveSerial(self):
        return_msg = self.serial.readline()
        print( return_msg )
        return return_msg

    def detect_irregular_intervals(self,directory_path):
        """
        Detects image files with irregular time intervals in a directory, 
        first determining the typical interval from existing images.

        Args:
            directory_path (str): The path to the directory containing the images.

        Returns:
            list: A list of tuples (filename, actual_interval) for images with irregular intervals.
        """
        def get_file_creation_time(filename):
            """Helper function to get file creation time for sorting."""
            filepath = os.path.join(directory_path, filename)
            return os.path.getctime(filepath)

        image_files = [f for f in os.listdir(directory_path) if f.endswith(('.jpg', '.jpeg', '.png', '.tiff'))]
        # Sort files by creation time using the helper function
        image_files.sort(key=get_file_creation_time) 

        intervals = []
        for i in range(1, len(image_files)):
            try:
                filepath1 = os.path.join(directory_path, image_files[i - 1])
                filepath2 = os.path.join(directory_path, image_files[i])
                ctime1 = os.path.getctime(filepath1)
                ctime2 = os.path.getctime(filepath2)
                datetime1 = datetime.fromtimestamp(ctime1)
                datetime2 = datetime.fromtimestamp(ctime2)

                actual_interval = round((datetime2 - datetime1).total_seconds())
                intervals.append(actual_interval)
            except FileNotFoundError:
                print(f"Error: Image file not found: {image_files[i]}")

        if len(intervals) == 0:
            return []
        # Determine the most common interval (typical_interval)
        print(intervals)
        interval_counts = {}
        for interval in intervals:
            interval_counts[interval] = interval_counts.get(interval, 0) + 1
        typical_interval = max(interval_counts, key=interval_counts.get)  # Most frequent interval
        print("Typical interval:", typical_interval)

        image_data = []
        image_data.append( (0, directory_path, image_files[0], True) )  # Add include flag
        span = 0

        irregular_intervals = []
        for i, interval in enumerate(intervals):
            print(interval)
            if interval == 0:
                print(f"Image {image_files[i+1]} has an irregular interval of {interval} seconds.")
                span += 1
                continue
            if not (0.5 * typical_interval <= interval <= 1.5 * typical_interval):
                print("current:",interval, "typical:",typical_interval)
                if interval > 1.5 * typical_interval:
                    print(f"Image {image_files[i+1]} has an irregular interval of {interval} seconds.")
                    span_count = round(interval / typical_interval ) - 1
                    for j in range(span_count):
                        image_data.append( (i+j+1, "-", "-", False) )  # Missing images not included
                    span += span_count
            image_data.append( (i+span+1, directory_path, image_files[i+1], True) )  # Add include flag
        print(image_data)

        return image_data

        return image_files, typical_interval, irregular_intervals

    def generatePTM(self):
        # check ptmfitter exists
        if not os.path.exists(self.ptm_fitter):
            print("PTM fitter not found:", self.ptm_fitter)
            self.statusBar.showMessage(f"PTM fitter not found: {self.ptm_fitter}", 5000)
            # show error message
            QMessageBox.critical(self, self.tr("Error"), f"PTM fitter not found: {self.ptm_fitter}")
            return

        LIGHT_POSITION_LIST = self.prepare_light_positions()

        # Update image_data with current checkbox states from table
        self.sync_checkbox_states_to_image_data()

        #lp_list = []  # Placeholder for lp_list, should be filled appropriately
        ret_str = ""
        image_count = 0
        image_directory = None
        for image in self.image_data:
            i, directory, image_name, include = image
            if image_directory is None:
                image_directory = directory
            # Skip if image failed or not included
            if image_name == '-' or not include:
                continue
            image_count += 1
            # make image_name's extension as lowercase
            image_name = image_name.split('.')[0] + '.' + image_name.split('.')[1].lower()

            # Ensure absolute path for PTMfitter
            image_path = os.path.abspath(os.path.join(directory, image_name))
            ret_str += image_path + " " + " ".join([str(f) for f in LIGHT_POSITION_LIST[i]]) + "\n"
        ret_str = str(image_count) + "\n" + ret_str

        #check current directory
        print("Current directory:", self.current_directory)
        print("Image directory:", image_directory)
        #print("Current directory parts:", Path(self.current_directory).parts)
        if len(Path(self.current_directory).parts) == 0:
            print("Current directory not found")
            self.statusBar.showMessage("Current directory not found", 5000)
            QMessageBox.critical(self, self.tr("Error"), "Current directory not found")
            return
        #print(Path(self.current_directory).parts)
        
        netfilename = Path(image_directory).parts[-1]
        lpfilename = Path(image_directory, netfilename + ".lp")
        
        with open(str(lpfilename), 'w') as file:
            file.write(ret_str)
        
        saveoptions = QFileDialog.Options()
        #saveoptions |= QFileDialog.DontUseNativeDialog
        saveoptions = {
            'defaultextension': '.ptm',
            'filetypes': [('PTM files', '*.ptm'), ('All files', '*.*')],
            'initialdir': str(self.current_directory),
            'initialfile': netfilename + '.ptm'
        }
        
        ptmfilename, _ = QFileDialog.getSaveFileName(self, "Save PTM file", str(self.current_directory), 
                                                     "PTM files (*.ptm);;All files (*)")
        if ptmfilename:
            execute_string = " ".join([str(self.ptm_fitter), "-i", str(lpfilename), "-o", str(ptmfilename)])
            execute_list = [str(self.ptm_fitter), "-i", str(lpfilename), "-o", str(ptmfilename)]
            print("Executing:", execute_list)
            subprocess.call([str(self.ptm_fitter), "-i", str(lpfilename), "-o", str(ptmfilename)])

    def prepare_light_positions(self):
        LIGHT_POSITION_LIST = []

        for [ theta, phi ] in POLAR_LIGHT_LIST:
            phi_corrected = phi - 90 + self.light_position_adjustment
            x = math.cos(math.radians(phi_corrected-180)) * math.sin(math.radians(theta))
            y = math.sin(math.radians(phi_corrected-180)) * math.sin(math.radians(theta))
            z =  math.cos(math.radians(theta))
            LIGHT_POSITION_LIST.append( [x,y,z])
        print (LIGHT_POSITION_LIST)
        return LIGHT_POSITION_LIST

    def update_language(self, language):
        #print("main update language:", language)
        #translators = self.m_app.findChildren(QTranslator)
        #for translator in translators:
        #    print("Translator:", translator)
        
        if self.m_app.translator is not None:
            self.m_app.removeTranslator(self.m_app.translator)
            #print("removed translator")
            self.m_app.translator = None
        else:
            pass
            #print("no translator")

        translator = QTranslator()
        translator_path = resource_path("translations/PTMGenerator2_{}.qm".format(language))
        #print("translator_path:", translator_path)
        if os.path.exists(translator_path):
            #print("Loading new translator:", translator_path)
            #pass
            translator.load(translator_path)
            #translator.load('PTMGenerator2_{}.qm'.format(language))
            self.m_app.installTranslator(translator)
            self.m_app.translator = translator
        else:
            pass
            #print("Translator not found:", translator_path)

        self.setWindowTitle("{} v{}".format(self.tr(PROGRAM_NAME), PROGRAM_VERSION))
        file_text = self.tr("File")
        #print("file_text:", file_text)
        self.file_menu.setTitle(file_text)
        self.edit_menu.setTitle(self.tr("Edit"))
        self.help_menu.setTitle(self.tr("Help"))
        self.actionOpenDirectory.setText(self.tr("Open Directory"))
        self.actionPreferences.setText(self.tr("Preferences"))
        self.actionAbout.setText(self.tr("About"))
        #self.lblDirectory.setText(self.tr("Directory"))
        self.image_model.setHorizontalHeaderLabels([self.tr('Include'), self.tr('Filename')])
        self.lblDirectory.setText(self.tr("Directory"))
        self.btnOpenDirectory.setText(self.tr("Open Directory"))
        self.btnTestShot.setText(self.tr("Test Shot"))        
        self.btnTakeAllPictures.setText(self.tr("Take All Pictures"))
        self.btnRetakePicture.setText(self.tr("Retake Picture"))
        self.btnPauseContinue.setText(self.tr("Pause/Continue"))
        self.btnStop.setText(self.tr("Stop"))
        self.btnGeneratePTM.setText(self.tr("Generate PTM"))

class PreferencesWindow(QDialog):
    """
    A dialog window for managing preferences in the PTMGenerator application.

    Attributes:
        parent (QWidget): The parent widget of the dialog.
        m_app (QApplication): The instance of the QApplication.
        current_translator (QTranslator): The current translator for language localization.
        settings (QSettings): The settings object for storing and retrieving preferences.
        language_label (QLabel): The label for the language selection.
        language_combobox (QComboBox): The combobox for selecting the language.
        lblSerialPort (QLabel): The label for the serial port selection.
        comboSerialPort (QComboBox): The combobox for selecting the serial port.
        lblPtmFitter (QLabel): The label for the PTM fitter selection.
        edtPtmFitter (QLineEdit): The line edit for entering the PTM fitter path.
        btnPtmFitter (QPushButton): The button for browsing the PTM fitter executable.
        ptmfitter_widget (QWidget): The widget for containing the PTM fitter line edit and button.
        ptmfitter_layout (QHBoxLayout): The layout for the PTM fitter widget.
        lblNumberOfLEDs (QLabel): The label for the number of LEDs setting.
        edtNumberOfLEDs (QLineEdit): The line edit for entering the number of LEDs.
        lblRetryCount (QLabel): The label for the retry count setting.
        edtRetryCount (QLineEdit): The line edit for entering the retry count.
        btnOkay (QPushButton): The button for accepting the preferences and closing the dialog.
        layout (QFormLayout): The layout for arranging the preferences widgets.
    """

    def __init__(self, parent=None):
        """
        Initializes a new instance of the PreferencesWindow class.

        Args:
            parent (QWidget): The parent widget of the dialog.
        """
        super().__init__(parent)
        self.initialize_variables(parent)
        self.setup_ui()

    def initialize_variables(self, parent):
        """
        Initializes the variables required for the PreferencesWindow.

        Args:
            parent (QWidget): The parent widget of the dialog.
        """
        self.parent = parent
        self.m_app = QApplication.instance()
        self.current_translator = None
        self.settings = QSettings(QSettings.IniFormat, QSettings.UserScope, COMPANY_NAME, PROGRAM_NAME)

    def setup_ui(self):
        """
        Sets up the user interface of the PreferencesWindow.
        """
        self.setWindowTitle(self.tr("Preferences"))
        self.setWindowIcon(QIcon(resource_path('icons/PTMGenerator2.png')))

        self.language_label = QLabel(self.tr("Language"))
        self.language_combobox = QComboBox()
        self.language_combobox.addItem("English", "en")
        self.language_combobox.addItem("한국어", "ko")
        self.language_combobox.setCurrentIndex(self.language_combobox.findData(self.settings.value("language", "en")))


        self.lblSerialPort = QLabel(self.tr("Serial Port"))
        self.comboSerialPort = QComboBox()
        arduino_ports = []
        port_list = serial.tools.list_ports.comports()
        for p in port_list:
            #print(p, p.description, p.device)
            arduino_ports.append(p.device)
            self.comboSerialPort.addItem(p.device + " - " + p.description, p.device)

        #arduino_ports = [ p.device for p in serial.tools.list_ports.comports()]
        #arduino_ports = [ p.device for p in serial.tools.list_ports.comports() if 'CH340' in p.description ]
        if len(port_list) == 0:
        #    self.comboSerialPort.addItems(arduino_ports)
        #else:
            self.comboSerialPort.addItem("None","None")

        self.lblPtmFitter = QLabel(self.tr("PTM Fitter"))
        self.edtPtmFitter = QLineEdit()
        self.edtPtmFitter.setText(self.settings.value("ptm_fitter", "ptmfitter.exe"))
        self.btnPtmFitter = QPushButton(self.tr("Browse"))
        self.btnPtmFitter.clicked.connect(self.on_browse_ptm_fitter)

        self.ptmfitter_widget = QWidget()
        self.ptmfitter_layout = QHBoxLayout()
        self.ptmfitter_widget.setLayout(self.ptmfitter_layout)
        self.ptmfitter_layout.addWidget(self.edtPtmFitter)
        self.ptmfitter_layout.addWidget(self.btnPtmFitter)

        self.lblNumberOfLEDs = QLabel(self.tr("Number of LEDs"))
        self.edtNumberOfLEDs = QLineEdit()
        # integer validator for edtNumberofLEDs
        self.edtNumberOfLEDs.setValidator(QIntValidator())

        self.lblRetryCount = QLabel(self.tr("Retry Count"))
        self.edtRetryCount = QLineEdit()
        # integer validator for edtNumberofLEDs
        self.edtRetryCount.setValidator(QIntValidator())

        self.lblPostShutterPolling = QLabel(self.tr("Post Shutter Polling"))
        self.edtPostShutterPolling = QLineEdit()
        self.edtPostShutterPolling.setValidator(QIntValidator())

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

        self.language_combobox.currentIndexChanged.connect(self.language_combobox_currentIndexChanged)

        self.language_combobox.setCurrentIndex(self.language_combobox.findData(self.language))
        self.comboSerialPort.setCurrentIndex(self.comboSerialPort.findData(self.serial_port))
        self.edtNumberOfLEDs.setText(str(self.number_of_LEDs))
        self.edtRetryCount.setText(str(self.retry_count))
        self.edtLightPositionAdjustment.setText(str(self.light_position_adjustment))
        self.edtPostShutterPolling.setText(str(self.post_shutter_polling))

    def Okay(self):
        """
        Performs the necessary actions when the 'Okay' button is clicked.
        Saves the settings, accepts the changes, and closes the dialog.
        """
        #self.settings.setValue("ptm_fitter", self.edtPtmFitter.text())               
        #self.parent.update_language(self.language)
        self.save_settings()
        self.accept()

    def on_browse_ptm_fitter(self):
        """
        Opens a file dialog to select a PTM Fitter executable file and sets the selected file path to the edtPtmFitter QLineEdit.

        Parameters:
        - None

        Returns:
        - None
        """
        filename, _ = QFileDialog.getOpenFileName(self, self.tr("Select PTM Fitter"), "", "Executable Files (*.exe)")
        if filename:
            self.edtPtmFitter.setText(filename)

    def read_settings(self):
        """
        Reads the application settings from the QSettings object and applies them to the preferences window.

        This method retrieves various settings values such as window geometry, serial port, PTM fitter, number of LEDs,
        retry count, and language. It then updates the preferences window with the retrieved values.

        Returns:
            None
        """
        self.m_app.settings = QSettings(QSettings.IniFormat, QSettings.UserScope, COMPANY_NAME, PROGRAM_NAME)
        self.remember_geometry = value_to_bool(self.m_app.settings.value("WindowGeometry/RememberGeometry", True))
        if self.remember_geometry is True:
            self.setGeometry(self.m_app.settings.value("WindowGeometry/PreferencesWindow", QRect(100, 100, 500, 250)))
            is_maximized = value_to_bool(self.m_app.settings.value("IsMaximized/PreferencesWindow", False))
            if is_maximized:
                self.showMaximized()
            else:
                self.showNormal()
        else:
            self.setGeometry(QRect(100, 100, 500, 250))
        self.serial_port = self.m_app.settings.value("serial_port", None)
        #print("Serial port:", self.m_app.serial_port)
        self.ptm_fitter = self.m_app.settings.value("ptm_fitter", "ptmfitter.exe")
        self.number_of_LEDs = int(self.m_app.settings.value("Number_of_LEDs", 50))
        self.retry_count = int(self.m_app.settings.value("RetryCount", 3))
        self.light_position_adjustment = int(self.m_app.settings.value("light_position_adjustment", 0))
        self.post_shutter_polling = float(self.m_app.settings.value("post_shutter_polling", 1))
        self.language = self.m_app.settings.value("language", "en")
        self.prev_language = self.language
        self.update_language(self.language)

    def save_settings(self):
        """
        Saves the current settings of the application.

        This method saves the window geometry, maximized state, language selection,
        serial port, PTM fitter, number of LEDs, and retry count to the application settings.

        Returns:
            None
        """
        self.m_app.settings.setValue("WindowGeometry/PreferencesWindow", self.geometry())
        self.m_app.settings.setValue("IsMaximized/PreferencesWindow", self.isMaximized())
        self.m_app.settings.setValue("language", self.language_combobox.currentData())
        serial_port = self.comboSerialPort.currentData()
        #print("Serial port:", serial_port)
        self.m_app.settings.setValue("serial_port", serial_port)
        self.m_app.settings.setValue("ptm_fitter", self.edtPtmFitter.text())
        self.m_app.settings.setValue("Number_of_LEDs", str(self.edtNumberOfLEDs.text()))
        self.m_app.settings.setValue("RetryCount", str(self.edtRetryCount.text()))
        self.m_app.settings.setValue("light_position_adjustment", str(self.edtLightPositionAdjustment.text()))
        self.m_app.settings.setValue("post_shutter_polling", str(self.edtPostShutterPolling.text()))

    def language_combobox_currentIndexChanged(self, index):
        """
        This method is called when the index of the language_combobox is changed.
        It updates the selected language and calls the update_language method.

        Parameters:
        - index: The new index of the language_combobox.

        Returns:
        None
        """
        self.language = self.language_combobox.currentData()
        #self.settings.setValue("language", self.language_combobox.currentData())
        #print("language:", self.language)
        #self.accept()
        self.update_language(self.language)

    def update_language(self, language):
        """
        Update the language of the application.

        Args:
            language (str): The language to be set.

        Returns:
            None
        """
        if self.m_app.translator is not None:
            self.m_app.removeTranslator(self.m_app.translator)
            #print("removed translator")
            self.m_app.translator = None
        else:
            pass
            #print("no translator")
        #print("pref update language:", language)
        #print("update language:", language)
        translator = QTranslator()
        #translator.load('PTMGenerator2_{}.qm'.format(language))
        filename = "translations/PTMGenerator2_{}.qm".format(language)
        #print("filename:", filename)
        if os.path.exists(resource_path(filename)):
            #print('path exists:', resource_path(filename))
            #print("loading translator", resource_path(filename))
            ret = translator.load(resource_path(filename))
            #print("load result:", ret)
            ret = self.m_app.installTranslator(translator)
            self.m_app.translator = translator
            #print("install result:", ret)
        else:
            #print("not exist:", resource_path(filename))
            pass

        #print("language_label before:", self.language_label.text())
        lang_text = self.tr("Language")
        #print("lang_text:", lang_text)
        self.language_label.setText(lang_text)
        #print("language_label after:", self.language_label.text())
        self.lblSerialPort.setText(self.tr("Serial Port"))
        self.lblPtmFitter.setText(self.tr("PTM Fitter"))
        self.btnPtmFitter.setText(self.tr("Browse"))
        self.lblNumberOfLEDs.setText(self.tr("Number of LEDs"))
        self.lblRetryCount.setText(self.tr("Retry Count"))
        self.btnOkay.setText(self.tr("OK"))
        self.update()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.translator = None
    app.setWindowIcon(QIcon(resource_path('icons/PTMGenerator2.png')))
    app.settings = QSettings(QSettings.IniFormat, QSettings.UserScope, COMPANY_NAME, PROGRAM_NAME)

    translator = QTranslator()
    app.language = app.settings.value("language", "en")
    translator.load(resource_path("translations/PTMGenerator2_{}.qm".format(app.language)))
    app.installTranslator(translator)
    app.translator = translator

    myWindow = PTMGeneratorMainWindow()
    myWindow.show()

    sys.exit(app.exec_())


'''
pyinstaller --name "PTMGenerator2_v0.1.2_20251107.exe" --onefile --noconsole --add-data "icons/*.png;icons" --add-data "translations/*.qm;translations" --icon="icons/PTMGenerator2.png" PTMGenerator2.py

pylupdate5 PTMGenerator2.py -ts translations/PTMGenerator2_en.ts
pylupdate5 PTMGenerator2.py -ts translations/PTMGenerator2_ko.ts
pylupdate5 PTMGenerator2.py -ts translations/PTMGenerator2_ja.ts

linguist

'''
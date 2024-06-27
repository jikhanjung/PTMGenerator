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
PROGRAM_VERSION = "0.1.0"

POLAR_LIGHT_LIST = [[85, 330], [84, 108], [83, 245], [82, 23], [81, 160], [80, 298], [79, 76], [78, 213], [77, 351], [76, 128],
 [75, 266], [74, 43], [73, 181], [71, 318], [70, 96], [69, 233], [68, 11], [67, 148], [66, 286], [65, 63],
 [64, 201], [62, 338], [61, 116], [60, 253], [59, 31], [58, 168], [56, 306], [55, 83], [54, 221], [52, 358],
 [51, 136], [50, 273], [48, 51], [47, 188], [46, 326], [44, 103], [43, 241], [41, 18], [39, 156], [38, 293],
 [36, 71], [34, 208], [32, 346], [30, 123], [28, 261], [26, 38], [23, 176], [21, 313], [17, 91], [13, 228]]

LIGHT_POSITION_LIST = []
for [ theta, phi ] in POLAR_LIGHT_LIST:
    x = math.cos(math.radians(phi-180)) * math.sin(math.radians(theta))
    y = math.sin(math.radians(phi-180)) * math.sin(math.radians(theta))
    z =  math.cos(math.radians(theta))
    LIGHT_POSITION_LIST.append( [x,y,z])

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
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(resource_path('icons/PTMGenerator2.png')))
        self.setWindowTitle("{} v{}".format(self.tr("PTMGenerator2"), PROGRAM_VERSION))

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

        self.table_view = QTableView()
        self.image_view = QLabel()

        self.image_list_widget = QWidget()
        self.image_list_layout = QHBoxLayout()
        self.image_list_widget.setLayout(self.image_list_layout)
        self.image_list_layout.addWidget(self.table_view, 1)
        self.image_list_layout.addWidget(self.image_view, 4)

        self.image_model = QStandardItemModel()
        self.image_model.setHorizontalHeaderLabels(['Filename'])
        self.table_view.setModel(self.image_model)
        header = self.table_view.horizontalHeader()  
        header.setSectionResizeMode(header.Stretch)
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
        print("Serial port:", self.m_app.serial_port)
        self.ptm_fitter = self.m_app.settings.value("ptm_fitter", "ptmfitter.exe")
        if self.m_app.serial_port is not None:
            self.serial_exist = True
            self.serial_port = self.m_app.serial_port
            #self.openSerial()
        else:
            self.serial_exist = False
        self.number_of_LEDs = int(self.m_app.settings.value("Number_of_LEDs", PTM_IMAGE_COUNT))
        self.auto_retake_maximum = int(self.m_app.settings.value("RetryCount", AUTO_RETAKE_MAXIMUM))
        

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
        self.take_shot()
        time.sleep(1)
        new_image = None
        count = 0
        while new_image is None and count < 5:
            time.sleep(1)
            new_image = self.get_incoming_image(self.current_directory)
            count += 1
        
        if new_image is None:
            print("Failed to get image file")
            self.statusBar.showMessage("Failed to get image file", 1000)
        else:
            print(f"New image detected: {new_image}")
            self.statusBar.showMessage(f"New image detected: {new_image}", 1000)


    def on_selection_changed(self,selected, deselected):
        # Iterate over selected indexes
        self.selected_rows = []        
        for model_index in self.table_view.selectionModel().selectedRows():
            row = model_index.row()
            self.selected_rows.append(row)
            if row not in self.prev_selected_rows:
                self.last_selected_row = row
                self.show_image( os.path.join( self.current_directory, self.image_data[row][1]) )
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
            for i, filename in image_data:
                self.image_data.append((i, filename))
            self.update_csv()
            self.load_csv_data()
        else:
            print("Image files not found or not enough images in the directory.")
            self.statusBar.showMessage(self.tr("Image files not found or not enough images in the directory."), 5000)

    def on_action_preferences_triggered(self):
        preferences = PreferencesWindow(self)
        preferences.exec()
        self.read_settings()

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
        print("Polling for incoming image file...", directory)
        newest_time = self.last_checked
        print(f"Last checked time: {newest_time}")
        newest_file = None
        files = os.listdir(directory)
        #print(f"Files in directory: {files}")
        for file in files:
            if not file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff')):
                continue
            full_path = os.path.join(directory, file)
            if os.path.isfile(full_path):
                file_time = os.path.getmtime(full_path)
                if file_time > newest_time:
                    newest_time = file_time
                    newest_file = full_path
                    print(f"[#{self.current_index+1}-{self.retake_counter}] New image detected: {newest_file} ({newest_time})")

        if newest_file is not None:
            self.last_checked = newest_time
            return newest_file
        else:
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
                    item = QStandardItem(name)
                    if self.current_index < self.table_view.model().rowCount():
                        self.table_view.model().setItem(self.current_index, 0, item)
                        self.image_data[self.current_index] = (self.current_index, name)
                    else:
                        self.table_view.model().appendRow(item)
                        self.image_data.append((self.current_index, name))
            else:
                # got a new image!
                self.statusBar.showMessage(f"[#{self.current_index+1}-{self.retake_counter}] [{self.second_counter}] New image detected: {new_image}", 1000)
                print(f"[#{self.current_index+1}-{self.retake_counter}] [{self.second_counter}] New image detected: {new_image}")
                directory, filename = os.path.split(new_image)
                #self.add_imagefile(self.current_index, filename)
                item = QStandardItem(filename)
                if self.current_index < self.table_view.model().rowCount():
                    self.table_view.model().setItem(self.current_index, 0, item)
                    self.image_data[self.current_index] = (self.current_index, filename)
                else:
                    self.table_view.model().appendRow(item)
                    self.image_data.append((self.current_index, filename))
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
                    if len(row) == 2:
                        index, filename = row
                        self.image_data.append((int(index), filename))
                        #self.image_index = max(self.image_index, int(index))
                        self.image_model.appendRow(QStandardItem(filename))
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

    def update_csv(self):
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
        image_data.append( (0, image_files[0]) )
        span = 0

        irregular_intervals = []
        for i, interval in enumerate(intervals):
            print(interval)
            if not (0.5 * typical_interval <= interval <= 1.5 * typical_interval):
                print("current:",interval, "typical:",typical_interval)
                if interval > 1.5 * typical_interval:
                    print(f"Image {image_files[i+1]} has an irregular interval of {interval} seconds.")
                    span_count = round(interval / typical_interval ) - 1
                    for j in range(span_count):
                        image_data.append( (i+j+1, "-") )
                    span += span_count
            image_data.append( (i+span+1, image_files[i+1]) )
        print(image_data)

        return image_data

        return image_files, typical_interval, irregular_intervals

    def generatePTM(self):
       
        #lp_list = []  # Placeholder for lp_list, should be filled appropriately
        ret_str = ""
        image_count = 0
        for image in self.image_data:
            i, image_name = image
            if image_name == '-':
                continue
            image_count += 1
            # make image_name's extension as lowercase
            image_name = image_name.split('.')[0] + '.' + image_name.split('.')[1].lower()

            ret_str += os.path.join( self.current_directory, image_name ) + " " + " ".join([str(f) for f in LIGHT_POSITION_LIST[i]]) + "\n"
        ret_str = str(image_count) + "\n" + ret_str
        
        netfilename = Path(self.current_directory).parts[-1]
        lpfilename = Path(self.current_directory, netfilename + ".lp")
        
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


class PreferencesWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Preferences"))
        self.setWindowIcon(QIcon(resource_path('icons/PTMGenerator2.png')))


        self.m_app = QApplication.instance()

        self.settings = QSettings(QSettings.IniFormat, QSettings.UserScope, COMPANY_NAME, PROGRAM_NAME)

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

        self.btnOkay = QPushButton(self.tr("OK"))
        self.btnOkay.clicked.connect(self.Okay)

        self.layout = QFormLayout()

        self.layout.addRow(self.language_label, self.language_combobox)
        self.layout.addRow(self.lblSerialPort, self.comboSerialPort)
        self.layout.addRow(self.lblPtmFitter, self.ptmfitter_widget)
        self.layout.addRow(self.lblNumberOfLEDs, self.edtNumberOfLEDs)
        self.layout.addRow(self.lblRetryCount, self.edtRetryCount)
        self.layout.addRow(self.btnOkay)

        #self.layout.addWidget(self.language_label)
        #self.layout.addWidget(self.language_combobox)

        self.setLayout(self.layout)

        self.language_combobox.currentIndexChanged.connect(self.language_combobox_currentIndexChanged)

        self.read_settings()

        self.comboSerialPort.setCurrentIndex(self.comboSerialPort.findData(self.m_app.serial_port))
        self.edtNumberOfLEDs.setText(str(self.m_app.number_of_LEDs))
        self.edtRetryCount.setText(str(self.m_app.retry_count))


    def Okay(self):
        #self.settings.setValue("ptm_fitter", self.edtPtmFitter.text())
        self.save_settings()
        self.accept()

    def on_browse_ptm_fitter(self):
        filename, _ = QFileDialog.getOpenFileName(self, self.tr("Select PTM Fitter"), "", "Executable Files (*.exe)")
        if filename:
            self.edtPtmFitter.setText(filename)

    def read_settings(self):
        self.m_app.settings = QSettings(QSettings.IniFormat, QSettings.UserScope, COMPANY_NAME, PROGRAM_NAME)
        self.m_app.remember_geometry = value_to_bool(self.m_app.settings.value("WindowGeometry/RememberGeometry", True))
        if self.m_app.remember_geometry is True:
            self.setGeometry(self.m_app.settings.value("WindowGeometry/PreferencesWindow", QRect(100, 100, 500, 250)))
            is_maximized = value_to_bool(self.m_app.settings.value("IsMaximized/PreferencesWindow", False))
            if is_maximized:
                self.showMaximized()
            else:
                self.showNormal()
        else:
            self.setGeometry(QRect(100, 100, 500, 250))
        self.m_app.serial_port = self.m_app.settings.value("serial_port", None)
        #print("Serial port:", self.m_app.serial_port)
        self.m_app.ptm_fitter = self.m_app.settings.value("ptm_fitter", "ptmfitter.exe")
        self.m_app.number_of_LEDs = int(self.m_app.settings.value("Number_of_LEDs", 50))
        self.m_app.retry_count = int(self.m_app.settings.value("RetryCount", 0))




    def save_settings(self):
        self.m_app.settings.setValue("WindowGeometry/PreferencesWindow", self.geometry())
        self.m_app.settings.setValue("IsMaximized/PreferencesWindow", self.isMaximized())
        self.m_app.settings.setValue("language", self.language_combobox.currentData())
        serial_port = self.comboSerialPort.currentData()
        #print("Serial port:", serial_port)
        self.m_app.settings.setValue("serial_port", serial_port)
        self.m_app.settings.setValue("ptm_fitter", self.edtPtmFitter.text())
        self.m_app.settings.setValue("Number_of_LEDs", str(self.edtNumberOfLEDs.text()))
        self.m_app.settings.setValue("RetryCount", str(self.edtRetryCount.text()))

    def language_combobox_currentIndexChanged(self, index):
        self.settings.setValue("language", self.language_combobox.currentData())
        #self.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path('icons/PTMGenerator2.png')))
    app.settings = QSettings(QSettings.IniFormat, QSettings.UserScope, COMPANY_NAME, PROGRAM_NAME)

    translator = QTranslator()
    app.language = app.settings.value("language", "en")
    translator.load(resource_path("translations/PTMGenerator2_{}.qm".format(app.language)))
    app.installTranslator(translator)

    myWindow = PTMGeneratorMainWindow()
    myWindow.show()

    sys.exit(app.exec_())


'''
pyinstaller --name "PTMGenerator2_v0.1.0_20240627.exe" --onefile --noconsole --add-data "icons/*.png;icons" --add-data "translations/*.qm;translations" --icon="icons/PTMGenerator2.png" PTMGenerator2.py

pylupdate5 PTMGenerator2.py -ts translations/PTMGenerator2_en.ts
pylupdate5 PTMGenerator2.py -ts translations/PTMGenerator2_ko.ts
pylupdate5 PTMGenerator2.py -ts translations/PTMGenerator2_ja.ts

linguist

'''
from PyQt5.QtWidgets import QMainWindow, QApplication, QMessageBox, QTableView, QAction, \
                            QStatusBar, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, \
                            QFileDialog, QDialog, QComboBox, QInputDialog, QWidget, QFormLayout
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt, QRect, QSettings, QTimer, QTranslator

import serial
import serial.tools.list_ports

import sys, os, time, csv

COMPANY_NAME = "PaleoBytes"
PROGRAM_NAME = "PTMGenerator2"
PROGRAM_VERSION = "0.1.0"


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
PTM_IMAGE_COUNT = 5
AUTO_RETAKE_MAXIMUM = 1


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

        self.auto_retake = True
        self.auto_retake_maximum = AUTO_RETAKE_MAXIMUM
        self.retake_counter = 0
        self.polling_timeout = 5
        self.image_index_list = []
        self.previous_index = -1
        self.serial_port = None
        self.serial_exist = False

        self.table_view = QTableView()
        self.image_view = QLabel()

        self.image_list_widget = QWidget()
        self.image_list_layout = QHBoxLayout()
        self.image_list_widget.setLayout(self.image_list_layout)
        self.image_list_layout.addWidget(self.table_view, 1)
        self.image_list_layout.addWidget(self.image_view, 4)

        self.image_model = QStandardItemModel()
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

        self.button_widget = QWidget() 
        self.button_layout = QHBoxLayout()
        self.button_widget.setLayout(self.button_layout)
        self.button_layout.addWidget(self.btnTestShot)
        self.button_layout.addWidget(self.btnTakeAllPictures)
        self.button_layout.addWidget(self.btnRetakePicture)
        self.button_layout.addWidget(self.btnPauseContinue)
        self.button_layout.addWidget(self.btnStop)

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
        self.m_app.ptm_fitter = self.m_app.settings.value("ptm_fitter", "ptmfitter.exe")
        if self.m_app.serial_port is not None:
            self.serial_exist = True
            self.openSerial()
        else:
            self.serial_exist = False

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
        self.statusBar.showMessage(self.tr("Stopped"), 1000)

    def clear_image_data(self):
        self.image_data = []
        self.image_model.clear()
        self.update_csv()        

    def test_shot(self):
        self.turn_on_led(PTM_IMAGE_COUNT-1)
        time.sleep(1)
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
        selected_rows = self.table_view.selectionModel().selectedRows()
        for model_index in selected_rows:
            row = model_index.row()
            print(f"Row {row} selected")
            self.selected_indices.append(model_index)
        print("Selected indices:", self.selected_indices)

    def on_action_open_directory_triggered(self):
        directory = QFileDialog.getExistingDirectory(self, self.tr("Open Directory"))
        if directory:
            self.current_directory = directory
            self.edtDirectory.setText(directory)
            self.load_csv_data()

    def on_action_preferences_triggered(self):
        preferences = PreferencesWindow(self)
        preferences.exec()

    def on_action_about_triggered(self):
        QMessageBox.about(self, self.tr("About"), "{} v{}".format(self.tr("PTMGenerator2"), PROGRAM_VERSION))

    def turn_on_led(self, led_index):
        print(f"Turning on LED {led_index+1}")

    def take_shot(self):
        print("Taking a shot with the DSLR")

    def get_incoming_image(self, directory):
        print("Polling for incoming image file...", directory)
        newest_time = self.last_checked
        print(f"Last checked time: {newest_time}")
        newest_file = None
        files = os.listdir(directory)
        print(f"Files in directory: {files}")
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
        self.second_counter += 1
        if self.status == "idle":
            self.status = "taking_picture"
            if self.current_index != self.previous_index:
                self.last_checked = time.time()
            self.statusBar.showMessage(f"[#{self.current_index+1}-{self.retake_counter}] Turning on LED #{self.current_index+1}...", 1000)
            self.turn_on_led(self.current_index)
            self.second_counter = 0
        elif self.status == "taking_picture":
            print("Taking picture...", self.current_index+1, self.image_index_list)
            self.statusBar.showMessage(f"[#{self.current_index+1}-{self.retake_counter}] Taking picture...{self.second_counter}", 1000)
            if self.second_counter > 2:
                self.take_shot()
                self.status = "polling"
                self.second_counter = 0
        elif self.status == "polling":
            self.statusBar.showMessage(f"[#{self.current_index+1}-{self.retake_counter}] Polling for image file...{self.second_counter}", 1000)
            new_image = self.get_incoming_image(self.current_directory)
            if new_image is None:
                if self.second_counter <= self.polling_timeout:
                    return
                else:
                    self.statusBar.showMessage(f"[#{self.current_index+1}-{self.retake_counter}] Failed to get image file", 1000)
                    print(f"[#{self.current_index+1}-{self.retake_counter}] Failed to get image file", self.current_index+1)
                    if self.auto_retake and self.retake_counter < self.auto_retake_maximum:
                        self.retake_counter += 1
                        self.statusBar.showMessage(f"[#{self.current_index+1}-{self.retake_counter}] Retaking picture... retry {self.retake_counter}...", 1000)
                        #self.retake_picture(self.current_index)
                        self.status = "idle"
                        return
                    #self.failed_list.append(self.current_index)
                    name = "-"
                    item = QStandardItem(name)
                    if self.current_index < self.table_view.model().rowCount():
                        self.table_view.model().setItem(self.current_index, 0, item)
                        self.image_data[self.current_index] = (self.current_index, name)
                    else:
                        self.table_view.model().appendRow(item)
                        self.image_data.append((self.current_index, name))
            else:
                self.statusBar.showMessage(f"[#{self.current_index+1}-{self.retake_counter}] New image detected: {new_image}", 1000)
                print(f"[#{self.current_index+1}-{self.retake_counter}] New image detected: {new_image}")
                directory, filename = os.path.split(new_image)
                #self.add_imagefile(self.current_index, filename)
                item = QStandardItem(filename)
                if self.current_index < self.table_view.model().rowCount():
                    self.table_view.model().setItem(self.current_index, 0, item)
                    self.image_data[self.current_index] = (self.current_index, filename)
                else:
                    self.table_view.model().appendRow(item)
                    self.image_data.append((self.current_index, filename))

            self.second_counter = 0
            self.retake_counter = 0
            self.status = "idle"
            self.previous_index = self.current_index
            if len(self.image_index_list) > 0:
                self.current_index = self.image_index_list.pop(0)
            else:
                self.timer.stop()
                self.statusBar.showMessage(f"All pictures ({PTM_IMAGE_COUNT}) taken", 5000)
                #self.label.setText("All pictures taken")
                self.status = "idle"
                self.update_csv()
                self.btnPauseContinue.setText(self.tr("Pause/Continue"))

    def take_all_pictures(self):
        period = 1000
        self.last_checked = time.time()
        self.image_index_list = []
        self.btnPauseContinue.setText(self.tr("Pause"))

        for i in range(PTM_IMAGE_COUNT):
            self.image_index_list.append(i)
            #self.image_data.append((i, "-"))
        self.image_list = []
        self.previous_index = -1
        self.current_index = self.image_index_list.pop(0)
        self.timer.start(period)  # Poll every 1 second

    def load_csv_data(self):
        self.path = self.edtDirectory.text()
        self.image_data = []
        self.image_index = 0
        csv_path = os.path.join(self.path, self.csv_file)
        if os.path.exists(csv_path):
            with open(csv_path, 'r', newline='') as csvfile:
                csvreader = csv.reader(csvfile)
                for row in csvreader:
                    if len(row) == 2:
                        index, filename = row
                        self.image_data.append((int(index), filename))
                        self.image_index = max(self.image_index, int(index))
            prev_index = -1
            for index, filename in self.image_data:
                item = QStandardItem(filename)
                if index > prev_index + 1:
                    for i in range(prev_index+1, index):
                        #self.image_data.append((i, None))
                        self.image_model.appendRow(QStandardItem("-"))
                self.image_model.appendRow(item)
                prev_index = index
            if prev_index < PTM_IMAGE_COUNT - 1:
                for i in range(prev_index+1, PTM_IMAGE_COUNT):
                    #self.image_data.append((i, None))
                    self.image_model.appendRow(QStandardItem("-"))

            print(f"Loaded data from CSV: {self.image_data}")

    def add_imagefile(self, index, filename):
        csv_path = os.path.join(self.current_directory, self.csv_file)
        with open(csv_path, 'a', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow([index, filename])
        self.image_data.append((index, filename))
        print(f"Logged to CSV: Index [{index}], Filename - [{filename}]")

    def update_csv(self):
        with open(self.csv_file, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerows(self.image_data)

    def on_retake_picture_triggered(self):
        period = 1000
        self.image_index_list = []
        for index in self.selected_indices:
            row = index.row()
            if row not in self.image_index_list:
                self.image_index_list.append(row)
        print("Retake picture list:", self.image_index_list)
        self.previous_index = -1
        self.current_index = self.image_index_list.pop(0)
        self.btnPauseContinue.setText(self.tr("Pause"))
        self.timer.start(period)  # Poll every 1 second

    def openSerial(self):
        if self.serial_exist == False:
            return
        if self.serial_port is None or self.serial_port == "" or self.serial_port == "None":
            self.serial_exist = False
            return
        self.serial = serial.Serial(self.serial_port, 9600, timeout=2)
        time.sleep(2)

    def closeSerial(self):
        self.serial.close()

    def sendSerial(self,msg):
        msg = "<" + msg + ">"
        print( msg )
        self.serial.write( msg.encode() )

    def receiveSerial(self):
        return_msg = self.serial.readline()
        print( return_msg )
        return return_msg

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
        arduino_ports = [ p.device for p in serial.tools.list_ports.comports() if 'CH340' in p.description ]
        if len(arduino_ports) > 0:
            self.comboSerialPort.addItems(arduino_ports)
        else:
            self.comboSerialPort.addItem("None")

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

        self.btnOkay = QPushButton(self.tr("OK"))
        self.btnOkay.clicked.connect(self.Okay)

        self.layout = QFormLayout()

        self.layout.addRow(self.language_label, self.language_combobox)
        self.layout.addRow(self.lblSerialPort, self.comboSerialPort)
        self.layout.addRow(self.lblPtmFitter, self.ptmfitter_widget)
        self.layout.addRow(self.btnOkay)

        #self.layout.addWidget(self.language_label)
        #self.layout.addWidget(self.language_combobox)

        self.setLayout(self.layout)

        self.language_combobox.currentIndexChanged.connect(self.language_combobox_currentIndexChanged)

        self.read_settings()

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
        self.m_app.ptm_fitter = self.m_app.settings.value("ptm_fitter", "ptmfitter.exe")


    def save_settings(self):
        self.m_app.settings.setValue("WindowGeometry/PreferencesWindow", self.geometry())
        self.m_app.settings.setValue("IsMaximized/PreferencesWindow", self.isMaximized())
        self.m_app.settings.setValue("language", self.language_combobox.currentData())
        self.m_app.settings.setValue("serial_port", self.comboSerialPort.currentText())
        self.m_app.settings.setValue("ptm_fitter", self.edtPtmFitter.text())

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
pyinstaller --name "PTMGenerator2_v0.1.0.exe" --onefile --noconsole --add-data "icons/*.png;icons" --add-data "translations/*.qm;translations" --icon="icons/PTMGenerator2.png" PTMGenerator2.py

pylupdate5 PTMGenerator2.py -ts translations/PTMGenerator2_en.ts
pylupdate5 PTMGenerator2.py -ts translations/PTMGenerator2_ko.ts
pylupdate5 PTMGenerator2.py -ts translations/PTMGenerator2_ja.ts

linguist

'''
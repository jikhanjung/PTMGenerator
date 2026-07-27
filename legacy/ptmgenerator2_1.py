from PyQt5.QtWidgets import QMainWindow, QApplication, QMessageBox, QTableView, QAction, \
                            QStatusBar, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, \
                            QFileDialog, QDialog, QComboBox, QInputDialog, QWidget
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt, QRect, QSettings, QTimer, QTranslator

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
PTM_IMAGE_COUNT = 50


class PTMGeneratorMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(resource_path('icons/PTMGenerator2.png')))
        self.setWindowTitle("{} v{}".format(self.tr("PTMGenerator2"), PROGRAM_VERSION))

        self.image_data = []
        self.failed_list = []
        self.current_index = -1
        self.status = "idle"
        self.second_counter = 0
        self.csv_file = 'image_log.csv'  # Change this to your desired CSV file path
        self.last_checked = time.time()
        self.current_directory = "."

        self.list_view = QTableView()
        self.image_view = QLabel()

        self.image_list_widget = QWidget()
        self.image_list_layout = QHBoxLayout()
        self.image_list_widget.setLayout(self.image_list_layout)
        self.image_list_layout.addWidget(self.list_view, 1)
        self.image_list_layout.addWidget(self.image_view, 4)

        self.image_model = QStandardItemModel()
        self.list_view.setModel(self.image_model)

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

        self.btnTakeAllPictures = QPushButton(self.tr("Take All Pictures"))
        self.btnTakeAllPictures.clicked.connect(self.take_all_pictures)
        self.btnRetakePicture = QPushButton(self.tr("Retake Picture"))
        self.btnRetakePicture.clicked.connect(self.on_retake_picture_triggered)

        self.button_widget = QWidget() 
        self.button_layout = QHBoxLayout()
        self.button_widget.setLayout(self.button_layout)
        self.button_layout.addWidget(self.btnTakeAllPictures)
        self.button_layout.addWidget(self.btnRetakePicture)

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
        print(f"Turning on LED {led_index}")

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

        if newest_file is not None:
            self.last_checked = newest_time
            return newest_file
        else:
            return None

    def picture_process(self):
        self.second_counter += 1
        if self.status == "idle":
            self.status = "taking_picture"
            self.statusBar.showMessage("Turning on LED...", 1000)
            self.turn_on_led(self.current_index)
            self.second_counter = 0
        elif self.status == "taking_picture":
            self.statusBar.showMessage(f"Taking picture...{self.second_counter}", 1000)
            if self.second_counter > 2:
                self.take_shot()
                self.status = "polling"
                self.second_counter = 0
        elif self.status == "polling":
            self.statusBar.showMessage(f"Polling for image file...{self.second_counter}", 1000)
            new_image = self.get_incoming_image(self.current_directory)
            if new_image is None and self.second_counter < 3:
                return

            if self.second_counter > 3:
                self.statusBar.showMessage("Failed to get image file", 1000)
                print("Failed to get image file", self.current_index)
                self.failed_list.append(self.current_index)
                item = QStandardItem("-")
                self.list_view.model().appendRow(item)
            else:
                self.statusBar.showMessage(f"New image detected: {new_image}", 1000)
                print(f"New image detected: {new_image}")
                directory, filename = os.path.split(new_image)
                self.add_imagefile(self.current_index, filename)
                item = QStandardItem(filename)
                self.list_view.model().appendRow(item)
            self.second_counter = 0
            self.current_index += 1
            self.status = "idle"
            if self.current_index == PTM_IMAGE_COUNT:
                self.timer.stop()
                self.statusBar.showMessage("All pictures taken", 5000)
                self.label.setText("All pictures taken")
                self.status = "idle"

    def take_all_pictures(self):
        period = 1000
        self.last_checked = time.time()
        self.image_list = []
        self.failed_list = []
        self.current_index = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.picture_process)
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

    def retake_picture(self, index):
        if index < len(self.image_data):
            current_index, current_filename = self.image_data[index]
            if os.path.exists(current_filename):
                os.remove(current_filename)
            self.image_data[index] = (current_index, None)
            self.update_csv()
            self.label.setText(f"Retaking picture at index {index}...")

            self.turn_on_led(index)
            self.take_shot()

            newest_file = None
            newest_time = time.time()

            for file in os.listdir(self.edtDirectory.text()):
                # Check if the file is an image file
                if not file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff')):
                    continue
                filepath = os.path.join(self.edtDirectory.text(), file)
                if os.path.isfile(filepath):
                    file_time = os.path.getmtime(filepath)
                    if file_time > newest_time:
                        newest_time = file_time
                        newest_file = filepath

            if newest_file:
                self.image_data[index] = (current_index, newest_file)
                self.update_csv()
                self.label.setText(f"New image detected: {newest_file}")
                print(f"New image detected: {newest_file}")
            else:
                print("No new image detected after retake")

    def on_retake_picture_triggered(self):
        index, ok = QInputDialog.getInt(self, "Retake Picture", "Enter the index of the picture to retake:")
        if ok:
            self.retake_picture(index)

class PreferencesWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Preferences"))
        self.setWindowIcon(QIcon(resource_path('icons/PTMGenerator2.png')))
        self.settings = QSettings(QSettings.IniFormat, QSettings.UserScope, COMPANY_NAME, PROGRAM_NAME)

        self.language_label = QLabel(self.tr("Language"))
        self.language_combobox = QComboBox()
        self.language_combobox.addItem("English", "en")
        self.language_combobox.addItem("한국어", "ko")
        self.language_combobox.setCurrentIndex(self.language_combobox.findData(self.settings.value("language", "en")))

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.language_label)
        self.layout.addWidget(self.language_combobox)

        self.setLayout(self.layout)

        self.language_combobox.currentIndexChanged.connect(self.language_combobox_currentIndexChanged)

    def language_combobox_currentIndexChanged(self, index):
        self.settings.setValue("language", self.language_combobox.currentData())
        self.accept()


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


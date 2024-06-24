from PyQt5.QtWidgets import QMainWindow, QHeaderView, QApplication, QAbstractItemView, \
                            QMessageBox, QTreeView, QTableView, QSplitter, QAction, QMenu, \
                            QStatusBar, QInputDialog, QToolBar, QWidget, QPlainTextEdit, QVBoxLayout, QHBoxLayout, \
                            QPushButton, QListWidget, QLabel, QLineEdit, QFileDialog, QComboBox, QDialog

from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem, QKeySequence
from PyQt5.QtCore import Qt, QRect, QSortFilterProxyModel, QSettings, QSize, QTranslator, QItemSelectionModel

import sys, os

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


class PTMGeneratorMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(resource_path('icons/PTMGenerator2.png')))
        self.setWindowTitle("{} v{}".format(self.tr("PTMGenerator2"), PROGRAM_VERSION))

        self.list_view = QTableView()
        self.image_view = QLabel()

        self.image_list_widget = QWidget()
        self.image_list_layout = QHBoxLayout()
        self.image_list_widget.setLayout(self.image_list_layout)
        self.image_list_layout.addWidget(self.list_view,1)
        self.image_list_layout.addWidget(self.image_view,4)

        self.image_model = QStandardItemModel()
        self.list_view.setModel(self.image_model)

        for i in range(50):
            item = QStandardItem("Image {}".format(i+1))
            self.list_view.model().appendRow(item)

        self.lblDirectory = QLabel(self.tr("Directory"))
        self.btnOpenDirectory = QPushButton(self.tr("Open Directory"))
        self.edtDirectory = QLineEdit()
        self.edtDirectory.setReadOnly(True)

        self.directory_widget = QWidget()
        self.directory_layout = QHBoxLayout()
        self.directory_widget.setLayout(self.directory_layout)
        self.directory_layout.addWidget(self.lblDirectory)
        self.directory_layout.addWidget(self.edtDirectory)
        self.directory_layout.addWidget(self.btnOpenDirectory)

        self.central_widget = QWidget()
        self.central_layout = QVBoxLayout()
        self.central_widget.setLayout(self.central_layout)
        self.central_layout.addWidget(self.directory_widget)
        self.central_layout.addWidget(self.image_list_widget)

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
        #self.m_app.settings = QSettings(QSettings.IniFormat, QSettings.UserScope,mu.COMPANY_NAME, mu.PROGRAM_NAME)
        self.m_app.remember_geometry = value_to_bool(self.m_app.settings.value("WindowGeometry/RememberGeometry", True))
        if self.m_app.remember_geometry is True:
            #print('loading geometry', self.remember_geometry)
            self.setGeometry(self.m_app.settings.value("WindowGeometry/MainWindow", QRect(100, 100, 1400, 800)))
            is_maximized = value_to_bool(self.m_app.settings.value("IsMaximized/MainWindow", False))
            if is_maximized == True:
                #print("maximized true")
                self.showMaximized()
            else:
                #print("maximized false")
                self.showNormal()
                #pass
        else:
            self.setGeometry(QRect(100, 100, 1400, 800))


    def on_action_open_directory_triggered(self):
        directory = QFileDialog.getExistingDirectory(self, self.tr("Open Directory"))
        if directory:
            self.edtDirectory.setText(directory)
            self.load_images(directory)

    def on_action_preferences_triggered(self):
        preferences = PreferencesWindow(self)
        preferences.exec()

    def on_action_about_triggered(self):
        QMessageBox.about(self, self.tr("About"), "{} v{}".format(self.tr("PTMGenerator2"), PROGRAM_VERSION))


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
    #QApplication : 프로그램을 실행시켜주는 클래스
    #with open('log.txt', 'w') as f:
    #    f.write("hello\n")
    #    # current directory
    #    f.write("current directory 1:" + os.getcwd() + "\n")
    #    f.write("current directory 2:" + os.path.abspath(".") + "\n")
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path('icons/PTMGenerator2.png')))
    app.settings = QSettings(QSettings.IniFormat, QSettings.UserScope, COMPANY_NAME, PROGRAM_NAME)

    translator = QTranslator()
    app.language = app.settings.value("language", "en")
    translator.load(resource_path("translations/PTMGenerator2_{}.qm".format(app.language)))
    app.installTranslator(translator)

    #app.settings = 
    #app.preferences = QSettings("Modan", "Modan2")

    #WindowClass의 인스턴스 생성
    myWindow = PTMGeneratorMainWindow()

    #프로그램 화면을 보여주는 코드
    myWindow.show()
    #myWindow.activateWindow()

    #프로그램을 이벤트루프로 진입시키는(프로그램을 작동시키는) 코드
    app.exec_()

'''
pyinstaller --name "PTMGenerator2_v0.1.0.exe" --onefile --noconsole --add-data "icons/*.png;icons" --add-data "translations/*.qm;translations" --icon="icons/PTMGenerator2.png" PTMGenerator2.py

pylupdate5 PTMGenerator2.py -ts translations/PTMGenerator2_en.ts
pylupdate5 PTMGenerator2.py -ts translations/PTMGenerator2_ko.ts
pylupdate5 PTMGenerator2.py -ts translations/PTMGenerator2_ja.ts

linguist

'''
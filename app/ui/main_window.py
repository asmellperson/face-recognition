from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.database.db import Database
from app.services.face_service import FaceRecognitionService
from app.ui.pages.cameras_page import CamerasPage
from app.ui.pages.logs_page import LogsPage
from app.ui.pages.persons_page import PersonsPage
from app.ui.pages.realtime_page import RealtimePage
from app.ui.pages.settings_page import SettingsPage


class MainWindow(QMainWindow):
    def __init__(
        self, database: Database, face_service: FaceRecognitionService
    ) -> None:
        super().__init__()
        self.database = database
        self.face_service = face_service
        self.setWindowTitle("本地人脸识别系统")
        self.resize(1280, 800)
        self.setMinimumSize(QSize(1050, 680))

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(210)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(12, 0, 12, 18)
        brand = QLabel("人脸识别系统")
        brand.setObjectName("Brand")
        side_layout.addWidget(brand)

        self.stack = QStackedWidget()
        self.realtime_page = RealtimePage(database, face_service)
        self.persons_page = PersonsPage(database, face_service)
        self.cameras_page = CamerasPage(database)
        self.logs_page = LogsPage(database)
        self.settings_page = SettingsPage(database)
        pages = [
            ("实时识别", self.realtime_page),
            ("人员管理", self.persons_page),
            ("摄像头管理", self.cameras_page),
            ("识别记录", self.logs_page),
            ("系统设置", self.settings_page),
        ]
        self.nav_buttons: list[QPushButton] = []
        for index, (name, page) in enumerate(pages):
            self.stack.addWidget(page)
            button = QPushButton(name)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.clicked.connect(
                lambda _checked=False, i=index: self.switch_page(i)
            )
            side_layout.addWidget(button)
            self.nav_buttons.append(button)
        self.nav_buttons[0].setChecked(True)
        side_layout.addStretch()
        version = QLabel("本地 PoC · CPU")
        version.setStyleSheet("color:#64748b;padding:8px")
        side_layout.addWidget(version)

        layout.addWidget(sidebar)
        layout.addWidget(self.stack, 1)

        self.cameras_page.cameras_changed.connect(
            self.realtime_page.refresh_cameras
        )
        self.cameras_page.camera_deleting.connect(
            self.realtime_page.stop_if_camera
        )
        self.persons_page.persons_changed.connect(
            self.face_service.refresh_index
        )

    def switch_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        if index == 0:
            self.realtime_page.refresh_cameras()
        elif index == 3:
            self.logs_page.refresh()

    def closeEvent(self, event) -> None:
        self.realtime_page.shutdown()
        event.accept()

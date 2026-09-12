from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database.db import Database
from app.ui.dialogs import CameraDialog
from app.workers.recognition_worker import CameraTestThread


class CamerasPage(QWidget):
    cameras_changed = Signal()
    camera_deleting = Signal(int)

    def __init__(self, database: Database, parent=None) -> None:
        super().__init__(parent)
        self.database = database
        self._threads: list[CameraTestThread] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        header = QHBoxLayout()
        title = QLabel("摄像头管理")
        title.setObjectName("PageTitle")
        add_button = QPushButton("添加摄像头")
        add_button.clicked.connect(self.add_camera)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(add_button)
        layout.addLayout(header)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["摄像头名称", "IP", "RTSP 地址", "状态", "操作"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )
        layout.addWidget(self.table)
        self.refresh()

    def refresh(self) -> None:
        rows = self.database.list_cameras()
        self.table.setRowCount(len(rows))
        for index, camera in enumerate(rows):
            for col, value in enumerate(
                [
                    camera["name"],
                    camera["ip"],
                    camera["rtsp_url"],
                    camera["status"],
                ]
            ):
                self.table.setItem(index, col, QTableWidgetItem(str(value)))
            actions = QWidget()
            row_layout = QHBoxLayout(actions)
            row_layout.setContentsMargins(3, 2, 3, 2)
            test = QPushButton("测试")
            test.clicked.connect(
                lambda _=False, c=dict(camera), b=test: self.test_camera(c, b)
            )
            edit = QPushButton("编辑")
            edit.setProperty("secondary", True)
            edit.clicked.connect(
                lambda _=False, c=dict(camera): self.edit_camera(c)
            )
            delete = QPushButton("删除")
            delete.setProperty("danger", True)
            delete.clicked.connect(
                lambda _=False, c=dict(camera): self.delete_camera(c)
            )
            row_layout.addWidget(test)
            row_layout.addWidget(edit)
            row_layout.addWidget(delete)
            self.table.setCellWidget(index, 4, actions)
            self.table.setRowHeight(index, 48)

    def add_camera(self) -> None:
        dialog = CameraDialog(parent=self)
        if dialog.exec():
            try:
                name, url, ip = dialog.values()
                self.database.add_camera(name, url, ip)
                self.refresh()
                self.cameras_changed.emit()
            except Exception as exc:
                QMessageBox.critical(self, "保存失败", str(exc))

    def edit_camera(self, camera: dict) -> None:
        dialog = CameraDialog(camera, self)
        if dialog.exec():
            try:
                name, url, ip = dialog.values()
                self.database.update_camera(int(camera["id"]), name, url, ip)
                self.refresh()
                self.cameras_changed.emit()
            except Exception as exc:
                QMessageBox.critical(self, "保存失败", str(exc))

    def test_camera(self, camera: dict, button: QPushButton) -> None:
        button.setEnabled(False)
        button.setText("测试中")
        thread = CameraTestThread(camera["rtsp_url"], self)
        self._threads.append(thread)

        def completed(ok: bool, message: str) -> None:
            button.setEnabled(True)
            button.setText("测试")
            self.database.set_camera_status(
                int(camera["id"]), "在线" if ok else "离线"
            )
            self.refresh()
            QMessageBox.information(
                self, "测试结果", message
            ) if ok else QMessageBox.warning(self, "测试结果", message)
            self._threads.remove(thread)

        thread.completed.connect(completed)
        thread.start()

    def delete_camera(self, camera: dict) -> None:
        answer = QMessageBox.question(
            self,
            "确认删除",
            f"确定删除摄像头“{camera['name']}”吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        camera_id = int(camera["id"])
        self.camera_deleting.emit(camera_id)
        try:
            self.database.delete_camera(camera_id)
            self.refresh()
            self.cameras_changed.emit()
        except Exception as exc:
            QMessageBox.critical(self, "删除失败", str(exc))

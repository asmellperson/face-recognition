from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database.db import Database
from app.services.face_service import FaceRecognitionService
from app.ui.dialogs import PersonDialog
from app.workers.recognition_worker import RegistrationWorker


class PersonsPage(QWidget):
    persons_changed = Signal()

    def __init__(
        self, database: Database, face_service: FaceRecognitionService, parent=None
    ) -> None:
        super().__init__(parent)
        self.database = database
        self.face_service = face_service
        self._worker: RegistrationWorker | None = None
        self._progress: QProgressDialog | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        header = QHBoxLayout()
        title = QLabel("人员管理 / 人脸库")
        title.setObjectName("PageTitle")
        add_button = QPushButton("添加人员")
        add_button.clicked.connect(self.add_person)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(add_button)
        layout.addLayout(header)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["头像", "姓名", "工号", "人脸照片数", "创建时间", "操作"]
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
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.ResizeToContents
        )
        layout.addWidget(self.table)
        self.refresh()

    def refresh(self) -> None:
        rows = self.database.list_persons()
        self.table.setRowCount(len(rows))
        for row_index, person in enumerate(rows):
            avatar = QLabel("无")
            avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            avatar.setFixedSize(64, 54)
            path = person["avatar_path"]
            if path and Path(path).exists():
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    avatar.setPixmap(
                        pixmap.scaled(
                            52,
                            48,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
            self.table.setCellWidget(row_index, 0, avatar)
            self.table.setItem(row_index, 1, QTableWidgetItem(person["name"]))
            self.table.setItem(
                row_index, 2, QTableWidgetItem(person["employee_no"])
            )
            self.table.setItem(
                row_index, 3, QTableWidgetItem(str(person["face_count"]))
            )
            self.table.setItem(
                row_index, 4, QTableWidgetItem(person["created_at"])
            )
            actions = QWidget()
            action_layout = QHBoxLayout(actions)
            action_layout.setContentsMargins(4, 2, 4, 2)
            edit = QPushButton("编辑")
            edit.setProperty("secondary", True)
            edit.clicked.connect(
                lambda _=False, p=dict(person): self.edit_person(p)
            )
            delete = QPushButton("删除")
            delete.setProperty("danger", True)
            delete.clicked.connect(
                lambda _=False, p=dict(person): self.delete_person(p)
            )
            action_layout.addWidget(edit)
            action_layout.addWidget(delete)
            self.table.setCellWidget(row_index, 5, actions)
            self.table.setRowHeight(row_index, 64)

    def add_person(self) -> None:
        dialog = PersonDialog(parent=self)
        if dialog.exec():
            name, employee_no, paths = dialog.values()
            self._start_save(name, employee_no, paths, None)

    def edit_person(self, person: dict) -> None:
        dialog = PersonDialog(person, self)
        if dialog.exec():
            name, employee_no, paths = dialog.values()
            self._start_save(name, employee_no, paths, int(person["id"]))

    def _start_save(
        self,
        name: str,
        employee_no: str,
        paths: list[str],
        person_id: int | None,
    ) -> None:
        self._progress = QProgressDialog(
            "正在检测人脸并提取特征…", None, 0, 0, self
        )
        self._progress.setWindowTitle("请稍候")
        self._progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress.setCancelButton(None)
        self._progress.show()
        self._worker = RegistrationWorker(
            self.face_service, name, employee_no, paths, person_id, self
        )
        self._worker.completed.connect(self._save_completed)
        self._worker.failed.connect(self._save_failed)
        self._worker.start()

    def _save_completed(self, result: dict) -> None:
        if self._progress:
            self._progress.close()
        message = f"保存成功，新增 {result['added_count']} 张有效人脸照片。"
        if result["errors"]:
            message += "\n\n以下照片已跳过：\n" + "\n".join(
                result["errors"]
            )
        QMessageBox.information(self, "完成", message)
        self.refresh()
        self.persons_changed.emit()

    def _save_failed(self, message: str) -> None:
        if self._progress:
            self._progress.close()
        if "UNIQUE constraint failed" in message:
            message = "该工号已存在，请更换工号。"
        QMessageBox.critical(self, "保存失败", message)

    def delete_person(self, person: dict) -> None:
        answer = QMessageBox.question(
            self,
            "确认删除",
            f"确定删除{person['name']}及其全部人脸数据吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.face_service.delete_person(int(person["id"]))
            self.refresh()
            self.persons_changed.emit()
        except Exception as exc:
            QMessageBox.critical(self, "删除失败", str(exc))

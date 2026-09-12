from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.services.camera_service import extract_ip
from app.workers.recognition_worker import CameraTestThread


class PersonDialog(QDialog):
    def __init__(self, person=None, parent=None) -> None:
        super().__init__(parent)
        self.person = person
        self.image_paths: list[str] = []
        self.setWindowTitle("编辑人员" if person else "添加人员")
        self.resize(520, 460)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.employee_edit = QLineEdit()
        if person:
            self.name_edit.setText(person["name"])
            self.employee_edit.setText(person["employee_no"])
        form.addRow("姓名：", self.name_edit)
        form.addRow("工号：", self.employee_edit)
        layout.addLayout(form)

        hint = QLabel(
            "请选择清晰正脸照片；每张照片只能包含一张人脸。"
            if not person
            else "可修改信息，也可继续追加人脸照片。"
        )
        hint.setStyleSheet("color:#64748b")
        layout.addWidget(hint)
        self.file_list = QListWidget()
        layout.addWidget(self.file_list, 1)

        button_row = QHBoxLayout()
        choose = QPushButton("选择照片")
        choose.clicked.connect(self.choose_images)
        remove = QPushButton("移除选中")
        remove.setProperty("secondary", True)
        remove.clicked.connect(self.remove_selected)
        button_row.addWidget(choose)
        button_row.addWidget(remove)
        button_row.addStretch()
        layout.addLayout(button_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def choose_images(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择人脸照片", "", "图片 (*.jpg *.jpeg *.png)"
        )
        for path in paths:
            if path not in self.image_paths:
                self.image_paths.append(path)
                self.file_list.addItem(Path(path).name)

    def remove_selected(self) -> None:
        row = self.file_list.currentRow()
        if row >= 0:
            self.file_list.takeItem(row)
            self.image_paths.pop(row)

    def _validate(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "提示", "请输入姓名")
            return
        if not self.employee_edit.text().strip():
            QMessageBox.warning(self, "提示", "请输入工号")
            return
        if not self.person and not self.image_paths:
            QMessageBox.warning(self, "提示", "新增人员时至少选择一张人脸照片")
            return
        self.accept()

    def values(self) -> tuple[str, str, list[str]]:
        return (
            self.name_edit.text().strip(),
            self.employee_edit.text().strip(),
            list(self.image_paths),
        )


class CameraDialog(QDialog):
    def __init__(self, camera=None, parent=None) -> None:
        super().__init__(parent)
        self.camera = camera
        self._test_thread: CameraTestThread | None = None
        self.setWindowTitle("编辑摄像头" if camera else "添加摄像头")
        self.resize(580, 260)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText(
            "rtsp://admin:password@192.168.1.100:554/Streaming/Channels/101"
        )
        if camera:
            self.name_edit.setText(camera["name"])
            self.url_edit.setText(camera["rtsp_url"])
        form.addRow("摄像头名称：", self.name_edit)
        form.addRow("RTSP 地址：", self.url_edit)
        layout.addLayout(form)

        self.result_label = QLabel("尚未测试")
        self.result_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.result_label)

        buttons_row = QHBoxLayout()
        test_button = QPushButton("测试连接")
        test_button.setProperty("secondary", True)
        test_button.clicked.connect(lambda: self.test_connection(test_button))
        buttons_row.addWidget(test_button)
        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def test_connection(self, button: QPushButton) -> None:
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "提示", "请输入 RTSP 地址")
            return
        button.setEnabled(False)
        self.result_label.setText("正在连接，请稍候…")
        self._test_thread = CameraTestThread(url, self)
        self._test_thread.completed.connect(
            lambda ok, msg: self._test_finished(ok, msg, button)
        )
        self._test_thread.start()

    def _test_finished(self, ok: bool, message: str, button: QPushButton) -> None:
        button.setEnabled(True)
        color = "#15803d" if ok else "#dc2626"
        self.result_label.setStyleSheet(f"color:{color};font-weight:600")
        self.result_label.setText(message)

    def _validate(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "提示", "请输入摄像头名称")
            return
        if not self.url_edit.text().strip():
            QMessageBox.warning(self, "提示", "请输入 RTSP 地址")
            return
        self.accept()

    def values(self) -> tuple[str, str, str]:
        url = self.url_edit.text().strip()
        return self.name_edit.text().strip(), url, extract_ip(url)

    def reject(self) -> None:
        if self._test_thread and self._test_thread.isRunning():
            QMessageBox.information(self, "提示", "连接测试正在进行，请等待测试结束。")
            return
        super().reject()

    def closeEvent(self, event) -> None:
        if self._test_thread and self._test_thread.isRunning():
            QMessageBox.information(self, "提示", "连接测试正在进行，请等待测试结束。")
            event.ignore()
            return
        super().closeEvent(event)

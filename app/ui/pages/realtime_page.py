from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.database.db import Database
from app.services.face_service import FaceRecognitionService
from app.workers.recognition_worker import RecognitionWorker


class RealtimePage(QWidget):
    def __init__(
        self, database: Database, face_service: FaceRecognitionService, parent=None
    ) -> None:
        super().__init__(parent)
        self.database = database
        self.face_service = face_service
        self.worker: RecognitionWorker | None = None
        self.current_camera_id: int | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        title = QLabel("实时识别")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("摄像头："))
        self.camera_combo = QComboBox()
        self.camera_combo.setMinimumWidth(280)
        controls.addWidget(self.camera_combo)
        self.start_button = QPushButton("启动识别")
        self.stop_button = QPushButton("停止识别")
        self.stop_button.setProperty("danger", True)
        self.stop_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_recognition)
        self.stop_button.clicked.connect(self.stop_recognition)
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        controls.addStretch()
        root.addLayout(controls)

        body = QHBoxLayout()
        self.video_label = QLabel("请选择摄像头并点击“启动识别”")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(780, 520)
        self.video_label.setStyleSheet(
            "background:#111827;color:#94a3b8;border-radius:8px;font-size:18px"
        )
        body.addWidget(self.video_label, 1)

        panel = QFrame()
        panel.setObjectName("Card")
        panel.setFixedWidth(285)
        panel_layout = QVBoxLayout(panel)
        panel_title = QLabel("运行状态")
        panel_title.setStyleSheet("font-size:18px;font-weight:700")
        panel_layout.addWidget(panel_title)
        grid = QGridLayout()
        grid.addWidget(QLabel("当前摄像头"), 0, 0)
        self.camera_value = QLabel("-")
        grid.addWidget(self.camera_value, 0, 1)
        grid.addWidget(QLabel("识别状态"), 1, 0)
        self.status_value = QLabel("已停止")
        grid.addWidget(self.status_value, 1, 1)
        grid.addWidget(QLabel("检测人脸数"), 2, 0)
        self.face_count_value = QLabel("0")
        grid.addWidget(self.face_count_value, 2, 1)
        panel_layout.addLayout(grid)
        panel_layout.addSpacing(16)
        recent_title = QLabel("最近检测")
        recent_title.setStyleSheet("font-weight:700")
        panel_layout.addWidget(recent_title)
        self.recent_label = QLabel("暂无")
        self.recent_label.setWordWrap(True)
        self.recent_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.recent_label.setStyleSheet(
            "background:#f8fafc;border:1px solid #e2e8f0;"
            "border-radius:6px;padding:10px;min-height:180px"
        )
        panel_layout.addWidget(self.recent_label)
        panel_layout.addStretch()
        body.addWidget(panel)
        root.addLayout(body, 1)
        self.refresh_cameras()

    def refresh_cameras(self) -> None:
        selected = self.camera_combo.currentData()
        self.camera_combo.clear()
        for camera in self.database.list_cameras():
            self.camera_combo.addItem(camera["name"], int(camera["id"]))
        if selected is not None:
            index = self.camera_combo.findData(selected)
            if index >= 0:
                self.camera_combo.setCurrentIndex(index)

    def start_recognition(self) -> None:
        camera_id = self.camera_combo.currentData()
        if camera_id is None:
            QMessageBox.warning(self, "提示", "请先在摄像头管理中添加摄像头")
            return
        camera = self.database.get_camera(int(camera_id))
        if not camera:
            QMessageBox.warning(self, "提示", "摄像头已不存在，请刷新后重试")
            self.refresh_cameras()
            return
        threshold = float(
            self.database.get_setting("recognition_threshold", "0.45")
        )
        frame_interval = int(self.database.get_setting("frame_interval", "3"))
        cooldown = int(
            self.database.get_setting("recognition_cooldown", "10")
        )
        self.worker = RecognitionWorker(
            self.database,
            self.face_service,
            dict(camera),
            threshold,
            frame_interval,
            cooldown,
            self,
        )
        self.worker.frame_ready.connect(self.update_frame)
        self.worker.status_changed.connect(self.status_value.setText)
        self.worker.face_count_changed.connect(
            lambda count: self.face_count_value.setText(str(count))
        )
        self.worker.recognition_event.connect(self.show_recognition)
        self.worker.error_occurred.connect(self.show_error)
        self.worker.finished.connect(self._worker_finished)
        self.current_camera_id = int(camera_id)
        self.camera_value.setText(camera["name"])
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.camera_combo.setEnabled(False)
        self.worker.start()

    def stop_recognition(self) -> None:
        if self.worker and self.worker.isRunning():
            self.status_value.setText("正在停止…")
            self.worker.stop()
            if not self.worker.wait(5000):
                QMessageBox.warning(
                    self, "提示", "视频线程正在等待底层连接释放，请稍候。"
                )
        self._worker_finished()

    def stop_if_camera(self, camera_id: int) -> None:
        if self.current_camera_id == camera_id:
            self.stop_recognition()

    def _worker_finished(self) -> None:
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.camera_combo.setEnabled(True)
        self.status_value.setText("已停止")
        self.current_camera_id = None
        self.worker = None

    def update_frame(self, image: QImage) -> None:
        pixmap = QPixmap.fromImage(image)
        self.video_label.setPixmap(
            pixmap.scaled(
                self.video_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def show_recognition(self, result: dict) -> None:
        employee = (
            f"\n工号：{result['employee_no']}" if result["employee_no"] else ""
        )
        self.recent_label.setText(
            f"{result['name']}{employee}\n相似度：{result['similarity']:.3f}"
        )

    def show_error(self, message: str) -> None:
        QMessageBox.warning(self, "识别异常", message)

    def shutdown(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(6000)

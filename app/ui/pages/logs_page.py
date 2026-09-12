from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
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


class LogsPage(QWidget):
    def __init__(self, database: Database, parent=None) -> None:
        super().__init__(parent)
        self.database = database
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        header = QHBoxLayout()
        title = QLabel("识别记录")
        title.setObjectName("PageTitle")
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self.refresh)
        clear = QPushButton("清空记录")
        clear.setProperty("danger", True)
        clear.clicked.connect(self.clear_logs)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(refresh)
        header.addWidget(clear)
        layout.addLayout(header)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["截图", "摄像头", "人员", "相似度", "识别时间"]
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
        layout.addWidget(self.table)
        self.refresh()

    def refresh(self) -> None:
        rows = self.database.list_recognition_logs()
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            snapshot = QLabel("无")
            snapshot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            snapshot.setFixedSize(90, 62)
            path = row["snapshot_path"]
            if path and Path(path).exists():
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    snapshot.setPixmap(
                        pixmap.scaled(
                            84,
                            58,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
            self.table.setCellWidget(index, 0, snapshot)
            self.table.setItem(
                index, 1, QTableWidgetItem(row["camera_name"])
            )
            self.table.setItem(index, 2, QTableWidgetItem(row["person_name"]))
            self.table.setItem(
                index, 3, QTableWidgetItem(f"{row['similarity']:.3f}")
            )
            self.table.setItem(
                index, 4, QTableWidgetItem(row["recognized_at"])
            )
            self.table.setRowHeight(index, 68)

    def clear_logs(self) -> None:
        answer = QMessageBox.question(
            self,
            "确认清空",
            "确定清空全部识别记录吗？截图文件将保留。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.database.clear_recognition_logs()
            self.refresh()

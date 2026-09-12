from __future__ import annotations

from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.database.db import Database


class SettingsPage(QWidget):
    def __init__(self, database: Database, parent=None) -> None:
        super().__init__(parent)
        self.database = database
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        title = QLabel("系统设置")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(620)
        card_layout = QVBoxLayout(card)
        form = QFormLayout()
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0.2, 0.8)
        self.threshold.setDecimals(2)
        self.threshold.setSingleStep(0.01)
        self.threshold.setValue(
            float(database.get_setting("recognition_threshold", "0.45"))
        )
        self.frame_interval = QSpinBox()
        self.frame_interval.setRange(1, 30)
        self.frame_interval.setValue(
            int(database.get_setting("frame_interval", "3"))
        )
        self.cooldown = QSpinBox()
        self.cooldown.setRange(1, 300)
        self.cooldown.setSuffix(" 秒")
        self.cooldown.setValue(
            int(database.get_setting("recognition_cooldown", "10"))
        )
        form.addRow("识别阈值（0.2～0.8）：", self.threshold)
        form.addRow("识别帧间隔：", self.frame_interval)
        form.addRow("同人记录冷却：", self.cooldown)
        card_layout.addLayout(form)
        note = QLabel(
            "阈值越高越严格。CPU 设备可增大帧间隔以降低占用。"
            "设置会在下一次启动识别时生效。"
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#64748b")
        card_layout.addWidget(note)
        row = QHBoxLayout()
        save = QPushButton("保存设置")
        save.clicked.connect(self.save)
        row.addStretch()
        row.addWidget(save)
        card_layout.addLayout(row)
        layout.addWidget(card)
        layout.addStretch()

    def save(self) -> None:
        self.database.set_setting(
            "recognition_threshold", f"{self.threshold.value():.2f}"
        )
        self.database.set_setting("frame_interval", self.frame_interval.value())
        self.database.set_setting("recognition_cooldown", self.cooldown.value())
        QMessageBox.information(self, "完成", "设置已保存")

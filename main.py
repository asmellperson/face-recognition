import os

# 必须在所有可能间接 import cv2 的模块之前
os.environ[
    "OPENCV_FFMPEG_CAPTURE_OPTIONS"
] = "rtsp_transport;tcp"

import logging
import sys

from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
)

from app.config import (
    APP_NAME,
    ensure_directories,
)

from app.database.db import Database

from app.services.face_service import (
    FaceRecognitionService,
)

from app.ui.main_window import (
    MainWindow,
)

from app.ui.style import (
    APP_STYLE,
)


def configure_logging() -> None:

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s "
            "[%(levelname)s] "
            "%(name)s: %(message)s"
        ),
        handlers=[
            logging.FileHandler(
                "logs/app.log",
                encoding="utf-8",
            ),
            logging.StreamHandler(),
        ],
    )


def main() -> int:

    ensure_directories()

    configure_logging()

    app = QApplication(
        sys.argv
    )

    app.setApplicationName(
        APP_NAME
    )

    app.setStyleSheet(
        APP_STYLE
    )

    try:

        database = Database()

        database.initialize()

        face_service = (
            FaceRecognitionService(
                database
            )
        )

        window = MainWindow(
            database,
            face_service,
        )

        window.show()

        return app.exec()

    except Exception as exc:

        logging.exception(
            "程序启动失败"
        )

        QMessageBox.critical(
            None,
            "启动失败",
            f"程序启动失败：\n{exc}",
        )

        return 1


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
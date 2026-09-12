from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from app.config import SNAPSHOTS_DIR
from app.database.db import Database
from app.services.camera_service import test_rtsp
from app.services.face_service import FaceRecognitionService
from app.utils.image_utils import save_cv_image

logger = logging.getLogger(__name__)


class CameraTestThread(QThread):
    completed = Signal(bool, str)

    def __init__(self, url: str, parent=None) -> None:
        super().__init__(parent)
        self.url = url

    def run(self) -> None:
        result = test_rtsp(self.url)
        self.completed.emit(result.success, result.message)


class RegistrationWorker(QThread):
    completed = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        service: FaceRecognitionService,
        name: str,
        employee_no: str,
        paths: list[str],
        person_id: int | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.name = name
        self.employee_no = employee_no
        self.paths = paths
        self.person_id = person_id

    def run(self) -> None:
        try:
            result = self.service.register_or_update_person(
                self.name,
                self.employee_no,
                self.paths,
                self.person_id,
            )
            self.completed.emit(result)

        except Exception as exc:
            logger.exception("人员保存失败")
            self.failed.emit(str(exc))


class RecognitionWorker(QThread):

    frame_ready = Signal(QImage)
    status_changed = Signal(str)
    face_count_changed = Signal(int)
    recognition_event = Signal(dict)
    error_occurred = Signal(str)

    # 前端最高显示 15 FPS，避免 QImage/Pillow 白白占用 CPU
    DISPLAY_FPS = 15.0

    def __init__(
        self,
        database: Database,
        face_service: FaceRecognitionService,
        camera: dict[str, Any],
        threshold: float,
        frame_interval: int,
        cooldown: int,
        parent=None,
    ) -> None:

        super().__init__(parent)

        self.database = database
        self.face_service = face_service
        self.camera = camera

        self.threshold = threshold
        self.frame_interval = max(1, frame_interval)
        self.cooldown = max(1, cooldown)

        self._stop_event = threading.Event()

        # ----------------------------
        # 最新识别结果
        # ----------------------------

        self._results_lock = threading.Lock()

        self._last_results: list[dict[str, Any]] = []

        # ----------------------------
        # AI推理最新帧
        # ----------------------------

        self._inference_lock = threading.Lock()

        self._inference_event = threading.Event()

        self._pending_inference_frame: np.ndarray | None = None

        self._inference_thread: threading.Thread | None = None

        # ----------------------------
        # 告警冷却
        # ----------------------------

        self._last_logged: dict[int, float] = {}

        # ----------------------------
        # 性能统计
        # ----------------------------

        self._stats_lock = threading.Lock()

        self._last_inference_ms = 0.0

        self._inference_count = 0

    def stop(self) -> None:

        self._stop_event.set()

        # 唤醒可能正在等待的AI线程
        self._inference_event.set()

    # =========================================================
    # RTSP采集线程
    # =========================================================

    def run(self) -> None:

        try:
            import cv2

        except ImportError:

            self.error_occurred.emit(
                "未安装 OpenCV，请先运行 install.bat"
            )

            return

        cap = None

        frame_number = 0

        consecutive_failures = 0

        last_display_at = 0.0

        stats_started_at = time.monotonic()

        stats_capture_frames = 0

        try:

            self.status_changed.emit("正在连接")

            params = [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
                5000,
                cv2.CAP_PROP_READ_TIMEOUT_MSEC,
                5000,
            ]

            try:

                cap = cv2.VideoCapture(
                    self.camera["rtsp_url"],
                    cv2.CAP_FFMPEG,
                    params,
                )

            except TypeError:

                cap = cv2.VideoCapture()

                cap.set(
                    cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
                    5000,
                )

                cap.set(
                    cv2.CAP_PROP_READ_TIMEOUT_MSEC,
                    5000,
                )

                cap.open(
                    self.camera["rtsp_url"],
                    cv2.CAP_FFMPEG,
                )

            # 尽量减少缓存
            cap.set(
                cv2.CAP_PROP_BUFFERSIZE,
                1,
            )

            if not cap.isOpened():

                raise RuntimeError(
                    "无法打开视频流，请检查 RTSP 地址、账号和网络"
                )

            # ----------------------------
            # 打印RTSP信息
            # ----------------------------

            try:
                backend = cap.getBackendName()
            except Exception:
                backend = "unknown"

            width = int(
                cap.get(
                    cv2.CAP_PROP_FRAME_WIDTH
                ) or 0
            )

            height = int(
                cap.get(
                    cv2.CAP_PROP_FRAME_HEIGHT
                ) or 0
            )

            source_fps = float(
                cap.get(
                    cv2.CAP_PROP_FPS
                ) or 0
            )

            logger.info(
                "RTSP已打开 backend=%s resolution=%sx%s "
                "source_fps=%.2f frame_interval=%s",
                backend,
                width,
                height,
                source_fps,
                self.frame_interval,
            )

            self.database.set_camera_status(
                self.camera["id"],
                "在线",
            )

            self.status_changed.emit(
                "识别中"
            )

            # =================================================
            # 启动独立AI线程
            # =================================================

            self._inference_thread = threading.Thread(
                target=self._inference_loop,
                name=f"FaceInference-{self.camera['id']}",
                daemon=True,
            )

            self._inference_thread.start()

            # =================================================
            # RTSP持续读取
            # =================================================

            while not self._stop_event.is_set():

                ok, frame = cap.read()

                if not ok or frame is None:

                    consecutive_failures += 1

                    if consecutive_failures >= 20:

                        raise RuntimeError(
                            "视频流已中断，连续多次未读取到画面"
                        )

                    self.msleep(20)

                    continue

                consecutive_failures = 0

                frame_number += 1

                stats_capture_frames += 1

                # =================================================
                # 到达识别间隔
                #
                # 注意：
                # 不执行InsightFace
                #
                # 这里只把最新图片给AI线程
                # =================================================

                if frame_number % self.frame_interval == 0:

                    with self._inference_lock:

                        # 直接覆盖旧帧
                        # 永远不排队
                        self._pending_inference_frame = frame.copy()

                    self._inference_event.set()

                # =================================================
                # UI显示
                # =================================================

                now = time.monotonic()

                if (
                    now - last_display_at
                    >= 1.0 / self.DISPLAY_FPS
                ):

                    last_display_at = now

                    with self._results_lock:

                        results = [
                            dict(item)
                            for item in self._last_results
                        ]

                    # 画框不能修改RTSP原始帧
                    display_frame = frame.copy()

                    self._draw_results(
                        display_frame,
                        results,
                    )

                    rgb = cv2.cvtColor(
                        display_frame,
                        cv2.COLOR_BGR2RGB,
                    )

                    height, width, channels = rgb.shape

                    image = QImage(
                        rgb.data,
                        width,
                        height,
                        channels * width,
                        QImage.Format.Format_RGB888,
                    ).copy()

                    self.frame_ready.emit(
                        image
                    )

                # =================================================
                # 每5秒输出一次性能
                # =================================================

                if now - stats_started_at >= 5.0:

                    elapsed = (
                        now - stats_started_at
                    )

                    capture_fps = (
                        stats_capture_frames
                        / elapsed
                    )

                    with self._stats_lock:

                        inference_ms = (
                            self._last_inference_ms
                        )

                        inference_count = (
                            self._inference_count
                        )

                        self._inference_count = 0

                    inference_fps = (
                        inference_count
                        / elapsed
                    )

                    logger.info(
                        "性能 capture_fps=%.2f "
                        "inference_fps=%.2f "
                        "last_inference_ms=%.1f CPU",
                        capture_fps,
                        inference_fps,
                        inference_ms,
                    )

                    stats_started_at = now

                    stats_capture_frames = 0

        except Exception as exc:

            logger.exception(
                "实时识别异常"
            )

            try:

                self.database.set_camera_status(
                    self.camera["id"],
                    "离线",
                )

            except Exception:

                logger.exception(
                    "更新摄像头状态失败"
                )

            self.error_occurred.emit(
                str(exc)
            )

        finally:

            self._stop_event.set()

            self._inference_event.set()

            if cap is not None:

                cap.release()

            if (
                self._inference_thread
                and self._inference_thread.is_alive()
            ):

                self._inference_thread.join(
                    timeout=3.0
                )

            self.status_changed.emit(
                "已停止"
            )

    # =========================================================
    # 独立InsightFace线程
    # =========================================================

    def _inference_loop(self) -> None:

        while not self._stop_event.is_set():

            if not self._inference_event.wait(
                timeout=0.5
            ):
                continue

            if self._stop_event.is_set():
                break

            # =================================================
            # 永远只拿最新帧
            # =================================================

            with self._inference_lock:

                frame = (
                    self._pending_inference_frame
                )

                self._pending_inference_frame = None

                self._inference_event.clear()

            if frame is None:
                continue

            started = time.perf_counter()

            try:

                # =================================================
                # InsightFace只在这里执行
                # =================================================

                results = (
                    self.face_service.analyze_frame(
                        frame,
                        self.threshold,
                    )
                )

                with self._results_lock:

                    self._last_results = [
                        dict(item)
                        for item in results
                    ]

                self.face_count_changed.emit(
                    len(results)
                )

                self._handle_logs(
                    frame,
                    results,
                )

            except Exception as exc:

                logger.exception(
                    "人脸推理失败"
                )

                self.error_occurred.emit(
                    str(exc)
                )

                self._stop_event.set()

                self._inference_event.set()

                break

            finally:

                inference_ms = (
                    time.perf_counter()
                    - started
                ) * 1000.0

                with self._stats_lock:

                    self._last_inference_ms = (
                        inference_ms
                    )

                    self._inference_count += 1

    # =========================================================
    # 画检测结果
    # =========================================================

    def _draw_results(
        self,
        frame: np.ndarray,
        results: list[dict[str, Any]],
    ) -> None:

        import cv2

        # 先画人脸框

        for result in results:

            x1, y1, x2, y2 = result[
                "bbox"
            ]

            matched = result[
                "matched"
            ]

            color = (
                (30, 190, 80)
                if matched
                else (40, 80, 230)
            )

            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                color,
                2,
            )

        # =====================================================
        # 中文姓名
        # =====================================================

        try:

            from PIL import (
                Image,
                ImageDraw,
                ImageFont,
            )

            rgb = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB,
            )

            pil_image = Image.fromarray(
                rgb
            )

            painter = ImageDraw.Draw(
                pil_image
            )

            font_path = Path(
                "C:/Windows/Fonts/msyh.ttc"
            )

            font = ImageFont.truetype(
                str(font_path),
                22,
            )

            for result in results:

                x1, y1, _x2, _y2 = (
                    result["bbox"]
                )

                text = (
                    f"{result['name']}  "
                    f"{result['similarity']:.2f}"
                )

                top = max(
                    0,
                    y1 - 32,
                )

                painter.rectangle(
                    (
                        x1,
                        top,
                        x1
                        + max(
                            150,
                            len(text) * 18,
                        ),
                        y1,
                    ),
                    fill=(15, 23, 42),
                )

                painter.text(
                    (
                        x1 + 4,
                        top + 2,
                    ),
                    text,
                    font=font,
                    fill=(
                        255,
                        255,
                        255,
                    ),
                )

            frame[:] = cv2.cvtColor(
                np.asarray(
                    pil_image
                ),
                cv2.COLOR_RGB2BGR,
            )

        except Exception:

            # Pillow失败则用OpenCV英文显示

            for result in results:

                x1, y1, _x2, _y2 = (
                    result["bbox"]
                )

                fallback = (
                    f"{result['employee_no']} "
                    f"{result['similarity']:.2f}"
                    if result["matched"]
                    else
                    f"Unknown "
                    f"{result['similarity']:.2f}"
                )

                cv2.putText(
                    frame,
                    fallback,
                    (
                        x1,
                        max(
                            24,
                            y1 - 8,
                        ),
                    ),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (
                        (30, 190, 80)
                        if result["matched"]
                        else (40, 80, 230)
                    ),
                    2,
                    cv2.LINE_AA,
                )

    # =========================================================
    # 识别日志
    # =========================================================

    def _handle_logs(
        self,
        frame: np.ndarray,
        results: list[dict[str, Any]],
    ) -> None:

        now = time.monotonic()

        for result in results:

            self.recognition_event.emit(
                result
            )

            if not result[
                "matched"
            ]:
                continue

            person_id = int(
                result["person_id"]
            )

            if (
                now
                - self._last_logged.get(
                    person_id,
                    0.0,
                )
                < self.cooldown
            ):
                continue

            self._last_logged[
                person_id
            ] = now

            timestamp = (
                datetime.now()
                .strftime(
                    "%Y%m%d_%H%M%S_%f"
                )
            )

            path = (
                SNAPSHOTS_DIR
                / (
                    f"camera_"
                    f"{self.camera['id']}"
                    f"_person_"
                    f"{person_id}_"
                    f"{timestamp}.jpg"
                )
            )

            try:

                snapshot_path = (
                    save_cv_image(
                        path,
                        frame,
                    )
                )

                self.database.add_recognition_log(
                    self.camera["id"],
                    person_id,
                    result["name"],
                    result["similarity"],
                    snapshot_path,
                )

            except Exception:

                logger.exception(
                    "保存识别记录失败"
                )

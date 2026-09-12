from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class CameraTestResult:
    success: bool
    message: str


def extract_ip(rtsp_url: str) -> str:
    match = re.match(r"^rtsp://(?:[^@/]+@)?([^:/]+)", rtsp_url.strip(), re.I)
    return match.group(1) if match else ""


def test_rtsp(rtsp_url: str, timeout_ms: int = 8000) -> CameraTestResult:
    if not rtsp_url.lower().startswith(("rtsp://", "http://", "https://")):
        return CameraTestResult(False, "地址格式不正确，应以 rtsp:// 开头")
    try:
        import cv2
    except ImportError:
        return CameraTestResult(False, "未安装 OpenCV，请先运行 install.bat")
    cap = None
    try:
        params = [
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
            timeout_ms,
            cv2.CAP_PROP_READ_TIMEOUT_MSEC,
            timeout_ms,
        ]
        try:
            cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG, params)
        except TypeError:
            cap = cv2.VideoCapture()
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms)
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_ms)
            cap.open(rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            return CameraTestResult(False, "连接失败：无法打开视频流，请检查地址、账号和密码")
        ok, frame = cap.read()
        if not ok or frame is None:
            return CameraTestResult(False, "连接已建立，但未读取到视频画面")
        return CameraTestResult(True, "连接成功")
    except Exception as exc:
        return CameraTestResult(False, f"连接失败：{exc}")
    finally:
        if cap is not None:
            cap.release()

from __future__ import annotations

from pathlib import Path

import numpy as np


def save_cv_image(path: Path, image: np.ndarray) -> str:
    import cv2

    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix or ".jpg"
    ok, encoded = cv2.imencode(suffix, image)
    if not ok:
        raise RuntimeError("截图编码失败")
    encoded.tofile(str(path))
    return str(path)

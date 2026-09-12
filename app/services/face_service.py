from __future__ import annotations

import logging
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any

import numpy as np

from app.config import FACES_DIR, MODEL_DIR
from app.database.db import Database

logger = logging.getLogger(__name__)


class FaceRecognitionService:
    """InsightFace 模型及本地人脸模板索引。模型在进程内仅初始化一次。"""

    def __init__(self, database: Database) -> None:
        self.database = database
        self._model: Any = None
        self._init_lock = threading.Lock()

        # 防止实时识别和人员注册同时调用 InsightFace
        self._model_lock = threading.Lock()

        self._index_lock = threading.RLock()
        self._templates: list[tuple[int, str, str, np.ndarray]] = []
        self.refresh_index()

    @property
    def is_initialized(self) -> bool:
        return self._model is not None

    def initialize(self) -> None:
        if self._model is not None:
            return
        with self._init_lock:
            if self._model is not None:
                return
            try:
                from insightface.app import FaceAnalysis
            except ImportError as exc:
                raise RuntimeError(
                    "未安装 InsightFace。请先运行 install.bat 安装依赖。"
                ) from exc
            try:
                logger.info(
                    "正在初始化 InsightFace buffalo_l 模型（CPU优化）"
                )

                model = FaceAnalysis(
                    name="buffalo_l",
                    root=str(MODEL_DIR),
                    allowed_modules=[
                        "detection",
                        "recognition",
                    ],
                    providers=[
                        "CPUExecutionProvider"
                    ],
                )

                model.prepare(
                    ctx_id=-1,
                    det_thresh=0.5,
                    det_size=(480, 480),
                )
                self._model = model
                logger.info("InsightFace 模型初始化完成")
            except Exception as exc:
                raise RuntimeError(
                    "InsightFace 模型初始化失败。首次使用需联网下载 buffalo_l 模型，"
                    f"请检查网络或模型目录。详细信息：{exc}"
                ) from exc

    @staticmethod
    def read_image(path: str | Path) -> np.ndarray:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("未安装 OpenCV，请先运行 install.bat。") from exc
        try:
            raw = np.fromfile(str(path), dtype=np.uint8)
            image = cv2.imdecode(raw, cv2.IMREAD_COLOR)
        except Exception as exc:
            raise ValueError(f"图片读取失败：{Path(path).name}（{exc}）") from exc
        if image is None:
            raise ValueError(f"图片损坏或格式不支持：{Path(path).name}")
        return image

    def extract_single_face(self, image_path: str | Path) -> np.ndarray:
        self.initialize()
        image = self.read_image(image_path)
        try:
            with self._model_lock:
                faces = self._model.get(image)
        except Exception as exc:
            raise RuntimeError(f"人脸分析失败：{Path(image_path).name}（{exc}）") from exc
        if not faces:
            raise ValueError(f"{Path(image_path).name}：该照片未检测到人脸")
        if len(faces) > 1:
            raise ValueError(f"{Path(image_path).name}：注册照片只能包含一张人脸")
        embedding = np.asarray(faces[0].normed_embedding, dtype=np.float32)
        norm = float(np.linalg.norm(embedding))
        if norm == 0:
            raise ValueError(f"{Path(image_path).name}：无法提取有效人脸特征")
        return embedding / norm

    def extract_images(
        self, image_paths: list[str]
    ) -> tuple[list[tuple[str, np.ndarray]], list[str]]:
        valid: list[tuple[str, np.ndarray]] = []
        errors: list[str] = []
        for path in image_paths:
            try:
                valid.append((path, self.extract_single_face(path)))
            except Exception as exc:
                errors.append(str(exc))
        return valid, errors

    def register_or_update_person(
        self,
        name: str,
        employee_no: str,
        image_paths: list[str],
        person_id: int | None = None,
    ) -> dict[str, Any]:
        name = name.strip()
        employee_no = employee_no.strip()
        if not name or not employee_no:
            raise ValueError("姓名和工号不能为空")
        valid: list[tuple[str, np.ndarray]] = []
        errors: list[str] = []
        if image_paths:
            valid, errors = self.extract_images(image_paths)
            if not valid:
                raise ValueError("\n".join(errors) or "没有可用的人脸照片")
        if person_id is None and not valid:
            raise ValueError("新增人员时至少选择一张人脸照片")

        created = person_id is None
        if created:
            person_id = self.database.add_person(name, employee_no)
        else:
            self.database.update_person(person_id, name, employee_no)

        copied: list[tuple[str, np.ndarray]] = []
        person_dir = FACES_DIR / str(person_id)
        try:
            if valid:
                person_dir.mkdir(parents=True, exist_ok=True)
                for source, embedding in valid:
                    suffix = Path(source).suffix.lower() or ".jpg"
                    target = person_dir / f"{uuid.uuid4().hex}{suffix}"
                    shutil.copy2(source, target)
                    copied.append((str(target), embedding))
                self.database.add_person_faces(person_id, copied)
            self.refresh_index()
            return {
                "person_id": person_id,
                "added_count": len(copied),
                "errors": errors,
            }
        except Exception:
            for path, _ in copied:
                Path(path).unlink(missing_ok=True)
            if created and person_id is not None:
                self.database.delete_person(person_id)
            raise

    def delete_person(self, person_id: int) -> None:
        image_paths = self.database.delete_person(person_id)
        for image_path in image_paths:
            try:
                Path(image_path).unlink(missing_ok=True)
            except OSError:
                logger.warning("无法删除人脸图片：%s", image_path)
        person_dir = FACES_DIR / str(person_id)
        if person_dir.exists():
            shutil.rmtree(person_dir, ignore_errors=True)
        self.refresh_index()

    def refresh_index(self) -> None:
        templates = self.database.get_face_templates()
        with self._index_lock:
            self._templates = templates

    def match(
        self, face_embedding: np.ndarray, threshold: float
    ) -> dict[str, Any]:
        embedding = np.asarray(face_embedding, dtype=np.float32)
        norm = float(np.linalg.norm(embedding))
        if norm > 0:
            embedding = embedding / norm
        with self._index_lock:
            templates = list(self._templates)
        if not templates:
            return {
                "person_id": None,
                "name": "未知人员",
                "employee_no": "",
                "similarity": 0.0,
                "matched": False,
            }
        scores = [float(np.dot(embedding, item[3])) for item in templates]
        best_index = int(np.argmax(scores))
        person_id, name, employee_no, _ = templates[best_index]
        score = scores[best_index]
        matched = score >= threshold
        return {
            "person_id": person_id if matched else None,
            "name": name if matched else "未知人员",
            "employee_no": employee_no if matched else "",
            "similarity": score,
            "matched": matched,
        }

    def analyze_frame(
            self,
            frame: np.ndarray,
            threshold: float,
    ) -> list[dict[str, Any]]:

        self.initialize()

        # 同一时刻只允许一次InsightFace推理
        with self._model_lock:
            faces = self._model.get(
                frame
            )

        results = []

        for face in faces:
            matched = self.match(
                face.normed_embedding,
                threshold,
            )

            bbox = np.asarray(
                face.bbox,
                dtype=int,
            ).tolist()

            matched["bbox"] = bbox

            results.append(
                matched
            )

        return results

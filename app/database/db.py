from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

import numpy as np

from app.config import DB_PATH, DEFAULT_SETTINGS


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Database:
    def __init__(self, path: Path | str = DB_PATH) -> None:
        self.path = Path(path)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.path), timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connection() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS persons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    employee_no TEXT NOT NULL UNIQUE,
                    template_embedding BLOB,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS person_faces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_id INTEGER NOT NULL,
                    image_path TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(person_id) REFERENCES persons(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS cameras (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    ip TEXT NOT NULL DEFAULT '',
                    rtsp_url TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT '未测试',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS recognition_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    camera_id INTEGER,
                    person_id INTEGER,
                    person_name TEXT NOT NULL,
                    similarity REAL NOT NULL,
                    recognized_at TEXT NOT NULL,
                    snapshot_path TEXT,
                    FOREIGN KEY(camera_id) REFERENCES cameras(id) ON DELETE SET NULL,
                    FOREIGN KEY(person_id) REFERENCES persons(id) ON DELETE SET NULL
                );

                CREATE INDEX IF NOT EXISTS idx_faces_person ON person_faces(person_id);
                CREATE INDEX IF NOT EXISTS idx_logs_time ON recognition_logs(recognized_at DESC);
                """
            )
            for key, value in DEFAULT_SETTINGS.items():
                conn.execute(
                    "INSERT OR IGNORE INTO settings(key, value, updated_at) VALUES(?, ?, ?)",
                    (key, value, _now()),
                )

    @staticmethod
    def embedding_to_blob(embedding: np.ndarray) -> bytes:
        return np.asarray(embedding, dtype=np.float32).tobytes()

    @staticmethod
    def blob_to_embedding(blob: bytes | None) -> Optional[np.ndarray]:
        if not blob:
            return None
        return np.frombuffer(blob, dtype=np.float32).copy()

    def list_persons(self) -> list[sqlite3.Row]:
        with self.connection() as conn:
            return list(
                conn.execute(
                    """
                    SELECT p.*, COUNT(f.id) AS face_count,
                           MIN(f.image_path) AS avatar_path
                    FROM persons p
                    LEFT JOIN person_faces f ON f.person_id = p.id
                    GROUP BY p.id
                    ORDER BY p.id DESC
                    """
                )
            )

    def get_person(self, person_id: int) -> Optional[sqlite3.Row]:
        with self.connection() as conn:
            return conn.execute(
                "SELECT * FROM persons WHERE id = ?", (person_id,)
            ).fetchone()

    def add_person(self, name: str, employee_no: str) -> int:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO persons(name, employee_no, created_at, updated_at)
                VALUES(?, ?, ?, ?)
                """,
                (name.strip(), employee_no.strip(), _now(), _now()),
            )
            return int(cursor.lastrowid)

    def update_person(self, person_id: int, name: str, employee_no: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "UPDATE persons SET name=?, employee_no=?, updated_at=? WHERE id=?",
                (name.strip(), employee_no.strip(), _now(), person_id),
            )

    def add_person_faces(
        self, person_id: int, face_items: Iterable[tuple[str, np.ndarray]]
    ) -> None:
        with self.connection() as conn:
            for image_path, embedding in face_items:
                conn.execute(
                    """
                    INSERT INTO person_faces(person_id, image_path, embedding, created_at)
                    VALUES(?, ?, ?, ?)
                    """,
                    (
                        person_id,
                        image_path,
                        self.embedding_to_blob(embedding),
                        _now(),
                    ),
                )
            self._rebuild_template(conn, person_id)

    def _rebuild_template(self, conn: sqlite3.Connection, person_id: int) -> None:
        rows = conn.execute(
            "SELECT embedding FROM person_faces WHERE person_id=?", (person_id,)
        ).fetchall()
        if not rows:
            conn.execute(
                "UPDATE persons SET template_embedding=NULL, updated_at=? WHERE id=?",
                (_now(), person_id),
            )
            return
        embeddings = [self.blob_to_embedding(row["embedding"]) for row in rows]
        mean = np.mean(np.stack(embeddings), axis=0)
        norm = float(np.linalg.norm(mean))
        if norm > 0:
            mean = mean / norm
        conn.execute(
            "UPDATE persons SET template_embedding=?, updated_at=? WHERE id=?",
            (self.embedding_to_blob(mean), _now(), person_id),
        )

    def delete_person(self, person_id: int) -> list[str]:
        with self.connection() as conn:
            paths = [
                row["image_path"]
                for row in conn.execute(
                    "SELECT image_path FROM person_faces WHERE person_id=?", (person_id,)
                )
            ]
            conn.execute("DELETE FROM persons WHERE id=?", (person_id,))
            return paths

    def get_face_templates(self) -> list[tuple[int, str, str, np.ndarray]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, name, employee_no, template_embedding
                FROM persons WHERE template_embedding IS NOT NULL
                """
            ).fetchall()
        result = []
        for row in rows:
            embedding = self.blob_to_embedding(row["template_embedding"])
            if embedding is not None:
                result.append((row["id"], row["name"], row["employee_no"], embedding))
        return result

    def list_cameras(self) -> list[sqlite3.Row]:
        with self.connection() as conn:
            return list(conn.execute("SELECT * FROM cameras ORDER BY id DESC"))

    def get_camera(self, camera_id: int) -> Optional[sqlite3.Row]:
        with self.connection() as conn:
            return conn.execute(
                "SELECT * FROM cameras WHERE id=?", (camera_id,)
            ).fetchone()

    def add_camera(self, name: str, rtsp_url: str, ip: str = "") -> int:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO cameras(name, ip, rtsp_url, status, created_at, updated_at)
                VALUES(?, ?, ?, '未测试', ?, ?)
                """,
                (name.strip(), ip.strip(), rtsp_url.strip(), _now(), _now()),
            )
            return int(cursor.lastrowid)

    def update_camera(
        self, camera_id: int, name: str, rtsp_url: str, ip: str = ""
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE cameras SET name=?, ip=?, rtsp_url=?, updated_at=? WHERE id=?
                """,
                (name.strip(), ip.strip(), rtsp_url.strip(), _now(), camera_id),
            )

    def set_camera_status(self, camera_id: int, status: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "UPDATE cameras SET status=?, updated_at=? WHERE id=?",
                (status, _now(), camera_id),
            )

    def delete_camera(self, camera_id: int) -> None:
        with self.connection() as conn:
            conn.execute("DELETE FROM cameras WHERE id=?", (camera_id,))

    def get_setting(self, key: str, default: str = "") -> str:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key=?", (key,)
            ).fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: Any) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO settings(key, value, updated_at) VALUES(?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                                               updated_at=excluded.updated_at
                """,
                (key, str(value), _now()),
            )

    def add_recognition_log(
        self,
        camera_id: int,
        person_id: int,
        person_name: str,
        similarity: float,
        snapshot_path: str,
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO recognition_logs(
                    camera_id, person_id, person_name, similarity,
                    recognized_at, snapshot_path
                ) VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    camera_id,
                    person_id,
                    person_name,
                    float(similarity),
                    _now(),
                    snapshot_path,
                ),
            )

    def list_recognition_logs(self, limit: int = 500) -> list[sqlite3.Row]:
        with self.connection() as conn:
            return list(
                conn.execute(
                    """
                    SELECT l.*, COALESCE(c.name, '已删除摄像头') AS camera_name
                    FROM recognition_logs l
                    LEFT JOIN cameras c ON c.id = l.camera_id
                    ORDER BY l.id DESC LIMIT ?
                    """,
                    (limit,),
                )
            )

    def clear_recognition_logs(self) -> None:
        with self.connection() as conn:
            conn.execute("DELETE FROM recognition_logs")

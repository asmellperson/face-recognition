from pathlib import Path

APP_NAME = "本地人脸识别系统"
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FACES_DIR = DATA_DIR / "faces"
DATABASE_DIR = DATA_DIR / "database"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
MODEL_DIR = BASE_DIR / "models"
LOG_DIR = BASE_DIR / "logs"
DB_PATH = DATABASE_DIR / "face_recognition.db"

DEFAULT_SETTINGS = {
    "recognition_threshold": "0.1",
    "frame_interval": "10",
    "recognition_cooldown": "10",
}


def ensure_directories() -> None:
    for path in (FACES_DIR, DATABASE_DIR, SNAPSHOTS_DIR, MODEL_DIR, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)

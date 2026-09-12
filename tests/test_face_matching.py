from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from app.database.db import Database
from app.services.face_service import FaceRecognitionService


def run() -> None:
    path = Path(__file__).parent / "match_test.db"
    path.unlink(missing_ok=True)
    db = Database(path)
    db.initialize()
    person_id = db.add_person("张三", "1001")
    enrolled = np.zeros(512, dtype=np.float32)
    enrolled[0] = 1.0
    db.add_person_faces(person_id, [("face.jpg", enrolled)])
    service = FaceRecognitionService(db)

    same = service.match(enrolled, 0.45)
    assert same["matched"] and same["name"] == "张三"

    different = np.zeros(512, dtype=np.float32)
    different[1] = 1.0
    unknown = service.match(different, 0.45)
    assert not unknown["matched"] and unknown["name"] == "未知人员"

    path.unlink(missing_ok=True)
    print("face matching tests passed")


if __name__ == "__main__":
    run()

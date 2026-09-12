from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from app.database.db import Database


def run() -> None:
    db_path = Path(__file__).parent / "test.db"
    db_path.unlink(missing_ok=True)
    db = Database(db_path)
    db.initialize()

    person_id = db.add_person("测试人员", "T001")
    embedding_a = np.ones(512, dtype=np.float32)
    embedding_a /= np.linalg.norm(embedding_a)
    embedding_b = np.arange(1, 513, dtype=np.float32)
    embedding_b /= np.linalg.norm(embedding_b)
    db.add_person_faces(
        person_id,
        [("a.jpg", embedding_a), ("b.jpg", embedding_b)],
    )
    persons = db.list_persons()
    assert len(persons) == 1 and persons[0]["face_count"] == 2
    templates = db.get_face_templates()
    assert len(templates) == 1
    assert abs(float(np.linalg.norm(templates[0][3])) - 1.0) < 1e-5

    camera_id = db.add_camera(
        "测试摄像头", "rtsp://admin:password@127.0.0.1/test", "127.0.0.1"
    )
    db.add_recognition_log(
        camera_id, person_id, "测试人员", 0.88, "snapshot.jpg"
    )
    assert len(db.list_recognition_logs()) == 1
    assert db.get_setting("recognition_threshold") == "0.45"
    db.set_setting("recognition_threshold", "0.50")
    assert db.get_setting("recognition_threshold") == "0.50"

    db.delete_person(person_id)
    assert not db.list_persons()
    db.delete_camera(camera_id)
    db_path.unlink(missing_ok=True)
    print("database tests passed")


if __name__ == "__main__":
    run()

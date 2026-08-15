import io
import shutil
from pathlib import Path
import numpy as np
import cv2
from fastapi.testclient import TestClient

from app.api.main import create_app
import app.api.teacher as teacher_mod
from app.config import ENCODINGS_PATH, STUDENTS_DIR
from app.db import (
    get_connection,
    get_student_with_profile,
    initialize_db,
    replace_teacher_assignments,
    upsert_admin_user,
    upsert_semester,
    upsert_subject,
    upsert_teacher_user,
)
from app.face_utils import extract_enrollment_encoding, load_known_faces


def test_complete_new_student_pipeline_runtime(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "test_attendance.db")
    encodings_path = tmp_path / "encodings.pkl"
    students_dir = tmp_path / "students"
    students_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("app.config.ENCODINGS_PATH", encodings_path)
    monkeypatch.setattr("app.config.STUDENTS_DIR", students_dir)
    monkeypatch.setattr("app.services.enrollment_service.ENCODINGS_PATH", encodings_path)
    monkeypatch.setattr("app.services.enrollment_service.STUDENTS_DIR", students_dir)
    monkeypatch.setattr("app.api.teacher.ENCODINGS_PATH", encodings_path)
    monkeypatch.setattr("app.face_utils.ENCODINGS_PATH", encodings_path)

    initialize_db(db_path=db_path)
    upsert_admin_user(admin_id="admin", name="Admin User", password="adminpassword", db_path=db_path)
    upsert_teacher_user(
        teacher_id="teacher1",
        name="Prof. Sharma",
        email="teacher1@test.com",
        password="teacherpassword",
        db_path=db_path,
    )
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=db_path)
    upsert_subject("DAA", "fall-2024", "Design and Analysis of Algorithms", 1, db_path=db_path)
    replace_teacher_assignments(
        teacher_id="teacher1",
        assignments=[
            {
                "semester_id": "fall-2024",
                "subject_id": "DAA",
                "batch": "F6",
                "class_type": "L",
            }
        ],
        db_path=db_path,
    )

    source_dir_person1 = Path("data/students/992401030300")
    source_dir_person2 = Path("data/students/992401030315")
    assert source_dir_person1.exists() and source_dir_person2.exists()

    person1_photos = sorted(source_dir_person1.glob("*.jpg"))[:7]
    person2_photos = sorted(source_dir_person2.glob("*.jpg"))[:7]
    assert len(person1_photos) >= 5
    assert len(person2_photos) >= 5


    app = create_app(db_path=db_path)

    with TestClient(app) as client:
        # 1. NEWLY REGISTERED STUDENT: TEST001, Batch F6
        login_admin = client.post("/api/admin/auth/login", json={"admin_id": "admin", "password": "adminpassword"})
        assert login_admin.status_code == 200

        files = [
            ("images", (p.name, p.read_bytes(), "image/jpeg"))
            for p in person1_photos
        ]
        data = {
            "student_id": "TEST001",
            "name": "Test Student 001",
            "branch": "CSE",
            "batch": "F6",
        }

        reg_res = client.post("/api/admin/students/register", data=data, files=files)
        assert reg_res.status_code == 200, reg_res.text
        reg_data = reg_res.json()
        assert reg_data["ok"] is True
        assert reg_data["student"]["student_id"] == "TEST001"
        assert reg_data["student"]["batch"] == "F6"
        assert reg_data["valid_images"] == len(person1_photos)

        # Verify SQLite Persistence
        stu = get_student_with_profile("TEST001", db_path=db_path)
        assert stu is not None
        assert stu["student_id"] == "TEST001"
        assert stu["batch"] == "F6"

        # Verify Disk Encodings Persistence
        assert encodings_path.exists()
        persisted = load_known_faces(encodings_path)
        test_idx = [idx for idx, sid in enumerate(persisted["student_ids"]) if sid == "TEST001"]
        assert len(test_idx) == len(person1_photos)
        for idx in test_idx:
            enc = persisted["encodings"][idx]
            assert enc.shape == (128,)
            assert enc.dtype == np.float64

        # 2. START ATTENDANCE SESSION FOR F6
        login_teacher = client.post(
            "/api/teacher/auth/login",
            json={"teacher_id": "teacher1", "password": "teacherpassword"},
        )
        assert login_teacher.status_code == 200

        start = client.post(
            "/api/teacher/sessions/start",
            json={
                "batch": "F6",
                "semester_id": "fall-2024",
                "subject_id": "DAA",
                "class_type": "L",
                "start_time": "09:00",
                "end_time": "10:00",
            },
        )
        assert start.status_code == 200, start.text
        session_id = start.json()["session_id"]

        known_loaded = teacher_mod._resolve_known_faces(db_path=db_path)
        assert "TEST001" in known_loaded["student_ids"]

        # 3. SHOW TEST001 FACE -> FRAME 1 (Confirming 1/2)
        frame1_bytes = person1_photos[0].read_bytes()
        f1_res = client.post(
            f"/api/teacher/sessions/{session_id}/frame",
            data={"tolerance": "0.6", "mode": "recognize"},
            files={"frame": ("test001.JPG", frame1_bytes, "image/jpeg")},
        )
        assert f1_res.status_code == 200
        det1 = f1_res.json()["marked_in_frame"][0]
        assert det1["student_id"] == "TEST001"
        assert det1["distance"] <= 0.6
        assert det1["status"] == "confirming"
        assert "1/2" in det1["warning"]

        # 4. SHOW TEST001 FACE -> FRAME 2 (Confirming 2/2 -> Attendance marked)
        frame2_bytes = person1_photos[1].read_bytes()
        f2_res = client.post(
            f"/api/teacher/sessions/{session_id}/frame",
            data={"tolerance": "0.6", "mode": "recognize"},
            files={"frame": ("test001_2.JPG", frame2_bytes, "image/jpeg")},
        )
        assert f2_res.status_code == 200
        det2 = f2_res.json()["marked_in_frame"][0]
        assert det2["student_id"] == "TEST001"
        assert det2["distance"] <= 0.6
        assert det2["status"] == "registered"
        assert "attendance marked" in det2["warning"].lower()

        with get_connection(db_path) as conn:
            row = conn.execute("SELECT present FROM session_attendance WHERE session_id = ? AND student_id = 'TEST001'", (session_id,)).fetchone()
            assert row is not None and row["present"] == 1

        # 5. SHOW UNREGISTERED PERSON (Person 2)
        unreg_bytes = person2_photos[0].read_bytes()
        f_unreg = client.post(
            f"/api/teacher/sessions/{session_id}/frame",
            data={"tolerance": "0.6", "mode": "recognize"},
            files={"frame": ("unreg.JPG", unreg_bytes, "image/jpeg")},
        )
        assert f_unreg.status_code == 200
        det_u = f_unreg.json()["marked_in_frame"][0]
        assert det_u["status"] == "face_mismatch"
        assert det_u["student_id"] == "Unknown"
        assert det_u["status"] != "batch_mismatch"
        assert det_u["status"] != "confirming"

        # 6. REGISTER PERSON 2 AS STUDENT_F7 *Batch F7*)
        login_admin_again = client.post("/api/admin/auth/login", json={"admin_id": "admin", "password": "adminpassword"})
        assert login_admin_again.status_code == 200

        files2 = [
            ("images", (p.name, p.read_bytes(), "image/jpeg"))
            for p in person2_photos
        ]
        reg2_res = client.post(
            "/api/admin/students/register",
            data={
                "student_id": "STUDENT_F7",
                "name": "Student From F7",
                "branch": "CSE",
                "batch": "F7",
            },
            files=files2,
        )
        assert reg2_res.status_code == 200

        # Present STUDENT_F7 to F6 session
        login_teacher_again = client.post(
            "/api/teacher/auth/login",
            json={"teacher_id": "teacher1", "password": "teacherpassword"},
        )
        assert login_teacher_again.status_code == 200

        f_f7 = client.post(
            f"/api/teacher/sessions/{session_id}/frame",
            data={"tolerance": "0.6", "mode": "recognize"},
            files={"frame": ("student_f7.JPG", unreg_bytes, "image/jpeg")},
        )
        assert f_f7.status_code == 200
        det_f7 = f_f7.json()["marked_in_frame"][0]
        assert det_f7["student_id"] == "STUDENT_F7"
        assert det_f7["distance"] <= 0.6
        assert det_f7["status"] == "batch_mismatch"
        assert "batch mismatch" in det_f7["warning"].lower()

        with get_connection(db_path) as conn:
            row = conn.execute("SELECT present FROM session_attendance WHERE session_id = ? AND student_id = 'STUDENT_F7'", (session_id,)).fetchone()
            assert row is None


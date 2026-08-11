from fastapi.testclient import TestClient

from app.api.main import create_app
from app.db import (
    get_student_with_profile,
    get_teacher_user,
    initialize_db,
    list_teacher_assignments,
    upsert_class_session,
    upsert_admin_user,
    replace_teacher_assignments,
    upsert_semester,
    upsert_session_attendance,
    upsert_student,
    upsert_student_profile,
    upsert_subject,
    upsert_teacher_user,
)


def _seed_student(db_path: str) -> None:
    upsert_student(student_id="22BCS001", name="Rahul Sharma", db_path=db_path)
    upsert_student_profile(student_id="22BCS001", branch="CSE", batch="CSE-A", db_path=db_path)


def _seed_teacher(db_path: str) -> None:
    upsert_teacher_user(
        teacher_id="admin",
        name="Faculty Demo",
        password="admin",
        db_path=db_path,
    )


def _assign_teacher(
    db_path: str,
    subject_id: str = "ENV",
    batch: str = "CSE-A",
    class_type: str = "L",
) -> None:
    replace_teacher_assignments(
        teacher_id="admin",
        assignments=[
            {
                "semester_id": "fall-2024",
                "subject_id": subject_id,
                "batch": batch,
                "class_type": class_type,
            }
        ],
        db_path=db_path,
    )


def _seed_admin(db_path: str) -> None:
    upsert_admin_user(
        admin_id="admin",
        name="Admin Demo",
        password="admin",
        db_path=db_path,
    )


def _client_for_db(db_path: str) -> TestClient:
    app = create_app(db_path=db_path)
    return TestClient(app)


def test_login_success_for_existing_student(tmp_path) -> None:
    db_path = str(tmp_path / "test_login_success.db")
    initialize_db(db_path=db_path)
    _seed_student(db_path)

    with _client_for_db(db_path) as client:
        response = client.post(
            "/api/auth/login",
            json={"student_id": "22BCS001", "password": "22BCS001"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["student"]["student_id"] == "22BCS001"


def test_login_failure_for_unknown_student(tmp_path) -> None:
    db_path = str(tmp_path / "test_login_fail.db")
    initialize_db(db_path=db_path)

    with _client_for_db(db_path) as client:
        response = client.post(
            "/api/auth/login",
            json={"student_id": "UNKNOWN", "password": "UNKNOWN"},
        )
        assert response.status_code == 401


def test_login_failure_for_wrong_student_password(tmp_path) -> None:
    db_path = str(tmp_path / "test_login_wrong_password.db")
    initialize_db(db_path=db_path)
    _seed_student(db_path)

    with _client_for_db(db_path) as client:
        response = client.post(
            "/api/auth/login",
            json={"student_id": "22BCS001", "password": "wrong"},
        )
        assert response.status_code == 401


def test_semesters_endpoint_returns_sorted_active_items(tmp_path) -> None:
    db_path = str(tmp_path / "test_semesters.db")
    initialize_db(db_path=db_path)
    _seed_student(db_path)
    upsert_semester("spring-2025", "Spring 2025", 2, 1, db_path=db_path)
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=db_path)
    upsert_semester("archive", "Archive", 0, 0, db_path=db_path)

    with _client_for_db(db_path) as client:
        login_response = client.post(
            "/api/auth/login",
            json={"student_id": "22BCS001", "password": "22BCS001"},
        )
        assert login_response.status_code == 200

        response = client.get("/api/semesters")
        assert response.status_code == 200
        payload = response.json()
        assert [item["id"] for item in payload["items"]] == ["fall-2024", "spring-2025"]


def test_summary_mixed_lecture_and_practical(tmp_path) -> None:
    db_path = str(tmp_path / "test_mixed_summary.db")
    initialize_db(db_path=db_path)
    _seed_student(db_path)
    _seed_teacher(db_path)
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=db_path)
    upsert_subject("ENV", "fall-2024", "Environment", 1, db_path=db_path)
    _assign_teacher(db_path)

    upsert_class_session(1, "ENV", "fall-2024", "L", "2024-09-01", db_path=db_path)
    upsert_class_session(2, "ENV", "fall-2024", "L", "2024-09-02", db_path=db_path)
    upsert_class_session(3, "ENV", "fall-2024", "P", "2024-09-03", db_path=db_path)
    upsert_session_attendance(1, "22BCS001", 1, db_path=db_path)
    upsert_session_attendance(2, "22BCS001", 0, db_path=db_path)
    upsert_session_attendance(3, "22BCS001", 1, db_path=db_path)

    with _client_for_db(db_path) as client:
        login_response = client.post(
            "/api/auth/login",
            json={"student_id": "22BCS001", "password": "22BCS001"},
        )
        assert login_response.status_code == 200

        response = client.get("/api/attendance/summary", params={"semester_id": "fall-2024"})
        assert response.status_code == 200
        payload = response.json()
        row = payload["rows"][0]
        assert payload["total_held"] == 3
        assert payload["total_attended"] == 2
        assert payload["total_pct"] == 67
        assert row["current_l_pct"] == 50
        assert row["current_p_pct"] == 100
        assert row["overall_pct"] == 67


def test_summary_with_only_lecture_sessions(tmp_path) -> None:
    db_path = str(tmp_path / "test_only_l.db")
    initialize_db(db_path=db_path)
    _seed_student(db_path)
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=db_path)
    upsert_subject("DAA", "fall-2024", "DAA", 1, db_path=db_path)
    upsert_class_session(1, "DAA", "fall-2024", "L", "2024-09-01", db_path=db_path)
    upsert_class_session(2, "DAA", "fall-2024", "L", "2024-09-02", db_path=db_path)
    upsert_session_attendance(1, "22BCS001", 1, db_path=db_path)
    upsert_session_attendance(2, "22BCS001", 0, db_path=db_path)

    with _client_for_db(db_path) as client:
        login_response = client.post(
            "/api/auth/login",
            json={"student_id": "22BCS001", "password": "22BCS001"},
        )
        assert login_response.status_code == 200

        response = client.get("/api/attendance/summary", params={"semester_id": "fall-2024"})
        assert response.status_code == 200
        row = response.json()["rows"][0]
        assert row["current_l_pct"] == 50
        assert row["current_p_pct"] is None
        assert row["overall_pct"] == 50


def test_summary_with_zero_sessions(tmp_path) -> None:
    db_path = str(tmp_path / "test_zero_sessions.db")
    initialize_db(db_path=db_path)
    _seed_student(db_path)
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=db_path)
    upsert_subject("DAALAB", "fall-2024", "DAA Lab", 1, db_path=db_path)

    with _client_for_db(db_path) as client:
        login_response = client.post(
            "/api/auth/login",
            json={"student_id": "22BCS001", "password": "22BCS001"},
        )
        assert login_response.status_code == 200

        response = client.get("/api/attendance/summary", params={"semester_id": "fall-2024"})
        assert response.status_code == 200
        row = response.json()["rows"][0]
        assert row["current_l_pct"] is None
        assert row["current_p_pct"] is None
        assert row["overall_pct"] is None


def test_teacher_login_success(tmp_path) -> None:
    db_path = str(tmp_path / "test_teacher_login_success.db")
    initialize_db(db_path=db_path)
    _seed_teacher(db_path)

    with _client_for_db(db_path) as client:
        response = client.post(
            "/api/teacher/auth/login",
            json={"teacher_id": "admin", "password": "admin"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["teacher"]["teacher_id"] == "admin"


def test_teacher_login_failure(tmp_path) -> None:
    db_path = str(tmp_path / "test_teacher_login_failure.db")
    initialize_db(db_path=db_path)
    _seed_teacher(db_path)

    with _client_for_db(db_path) as client:
        response = client.post(
            "/api/teacher/auth/login",
            json={"teacher_id": "admin", "password": "wrong"},
        )
        assert response.status_code == 401


def test_admin_login_success(tmp_path) -> None:
    db_path = str(tmp_path / "test_admin_login_success.db")
    initialize_db(db_path=db_path)
    _seed_admin(db_path)

    with _client_for_db(db_path) as client:
        response = client.post(
            "/api/admin/auth/login",
            json={"admin_id": "admin", "password": "admin"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["admin"]["admin_id"] == "admin"


def test_admin_login_failure(tmp_path) -> None:
    db_path = str(tmp_path / "test_admin_login_failure.db")
    initialize_db(db_path=db_path)
    _seed_admin(db_path)

    with _client_for_db(db_path) as client:
        response = client.post(
            "/api/admin/auth/login",
            json={"admin_id": "admin", "password": "wrong"},
        )
        assert response.status_code == 401


def test_admin_register_student_with_images(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "test_admin_register_student.db")
    initialize_db(db_path=db_path)
    _seed_admin(db_path)

    def fake_enroll(*args, **kwargs):
        return 2

    monkeypatch.setattr("app.api.admin.enroll_from_images", fake_enroll)

    with _client_for_db(db_path) as client:
        login = client.post(
            "/api/admin/auth/login",
            json={"admin_id": "admin", "password": "admin"},
        )
        assert login.status_code == 200

        response = client.post(
            "/api/admin/students/register",
            data={
                "student_id": "22BCS777",
                "name": "Admin Added",
                "branch": "CSE",
                "batch": "CSE-A",
            },
            files=[
                ("images", ("face1.jpg", b"fake-image-1", "image/jpeg")),
                ("images", ("face2.jpg", b"fake-image-2", "image/jpeg")),
            ],
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["uploaded_images"] == 2
        assert payload["valid_images"] == 2
        assert payload["student"]["student_id"] == "22BCS777"

        saved = get_student_with_profile("22BCS777", db_path=db_path)
        assert saved is not None
        assert saved["name"] == "Admin Added"


def test_admin_register_teacher_with_assignments(tmp_path) -> None:
    db_path = str(tmp_path / "test_admin_register_teacher.db")
    initialize_db(db_path=db_path)
    _seed_admin(db_path)
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=db_path)
    upsert_subject("ENV", "fall-2024", "Environment", 1, db_path=db_path)

    with _client_for_db(db_path) as client:
        login = client.post(
            "/api/admin/auth/login",
            json={"admin_id": "admin", "password": "admin"},
        )
        assert login.status_code == 200

        response = client.post(
            "/api/admin/teachers/register",
            json={
                "teacher_id": "faculty001",
                "name": "Faculty One",
                "password": "pass123",
                "assignments": [
                    {
                        "semester_id": "fall-2024",
                        "subject_id": "ENV",
                        "batch": "CSE-A",
                        "class_type": "L",
                    }
                ],
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["teacher"] == {"teacher_id": "faculty001", "name": "Faculty One"}
        assert len(payload["assignments"]) == 1
        assert payload["assignments"][0]["subject_name"] == "Environment"
        assert payload["assignments"][0]["batch"] == "CSE-A"

        saved_teacher = get_teacher_user("faculty001", db_path=db_path)
        assert saved_teacher is not None
        assert saved_teacher["password"] == "pass123"
        saved_assignments = list_teacher_assignments("faculty001", db_path=db_path)
        assert len(saved_assignments) == 1
        assert saved_assignments[0]["class_type"] == "L"


def test_admin_register_teacher_rejects_invalid_subject_semester(tmp_path) -> None:
    db_path = str(tmp_path / "test_admin_register_teacher_invalid_subject.db")
    initialize_db(db_path=db_path)
    _seed_admin(db_path)
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=db_path)
    upsert_semester("spring-2025", "Spring 2025", 2, 1, db_path=db_path)
    upsert_subject("ENV", "fall-2024", "Environment", 1, db_path=db_path)

    with _client_for_db(db_path) as client:
        login = client.post(
            "/api/admin/auth/login",
            json={"admin_id": "admin", "password": "admin"},
        )
        assert login.status_code == 200

        response = client.post(
            "/api/admin/teachers/register",
            json={
                "teacher_id": "faculty002",
                "name": "Faculty Two",
                "password": "pass123",
                "assignments": [
                    {
                        "semester_id": "spring-2025",
                        "subject_id": "ENV",
                        "batch": "CSE-A",
                        "class_type": "L",
                    }
                ],
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Subject does not belong to selected semester"


def test_teacher_start_and_stop_session(tmp_path) -> None:
    db_path = str(tmp_path / "test_teacher_session.db")
    initialize_db(db_path=db_path)
    _seed_teacher(db_path)
    _seed_student(db_path)
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=db_path)
    upsert_subject("ENV", "fall-2024", "Environment", 1, db_path=db_path)
    _assign_teacher(db_path)

    with _client_for_db(db_path) as client:
        login = client.post(
            "/api/teacher/auth/login",
            json={"teacher_id": "admin", "password": "admin"},
        )
        assert login.status_code == 200

        start = client.post(
            "/api/teacher/sessions/start",
            json={
                "batch": "CSE-A",
                "semester_id": "fall-2024",
                "subject_id": "ENV",
                "class_type": "L",
                "start_time": "09:00",
                "end_time": "10:00",
            },
        )
        assert start.status_code == 200
        session = start.json()
        assert session["is_active"] is True
        assert session["batch"] == "CSE-A"

        attendance = client.get(f"/api/teacher/sessions/{session['session_id']}/attendance")
        assert attendance.status_code == 200
        assert attendance.json()["present_students"] == []

        stop = client.post(f"/api/teacher/sessions/{session['session_id']}/stop")
        assert stop.status_code == 200
        assert stop.json()["is_active"] is False


def test_teacher_register_student_with_images(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "test_teacher_register_student.db")
    initialize_db(db_path=db_path)
    _seed_teacher(db_path)

    def fake_enroll(*args, **kwargs):
        return 2

    monkeypatch.setattr("app.api.teacher.enroll_from_images", fake_enroll)

    with _client_for_db(db_path) as client:
        login = client.post(
            "/api/teacher/auth/login",
            json={"teacher_id": "admin", "password": "admin"},
        )
        assert login.status_code == 200

        response = client.post(
            "/api/teacher/students/register",
            data={
                "student_id": "22BCS099",
                "name": "Test Student",
                "branch": "CSE",
                "batch": "CSE-A",
            },
            files=[
                ("images", ("face1.jpg", b"fake-image-1", "image/jpeg")),
                ("images", ("face2.jpg", b"fake-image-2", "image/jpeg")),
            ],
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["uploaded_images"] == 2
        assert payload["valid_images"] == 2
        assert payload["student"]["student_id"] == "22BCS099"
        assert payload["student"]["batch"] == "CSE-A"

        saved = get_student_with_profile("22BCS099", db_path=db_path)
        assert saved is not None
        assert saved["name"] == "Test Student"


def test_teacher_frame_detect_mode_works(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "test_teacher_frame_detect.db")
    initialize_db(db_path=db_path)
    _seed_teacher(db_path)
    _seed_student(db_path)
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=db_path)
    upsert_subject("ENV", "fall-2024", "Environment", 1, db_path=db_path)
    _assign_teacher(db_path, batch="CSE-A")

    monkeypatch.setattr(
        "app.api.teacher.face_recognition.face_locations",
        lambda *_args, **_kwargs: [(0, 10, 10, 0), (20, 30, 30, 20)],
    )

    with _client_for_db(db_path) as client:
        login = client.post(
            "/api/teacher/auth/login",
            json={"teacher_id": "admin", "password": "admin"},
        )
        assert login.status_code == 200

        start = client.post(
            "/api/teacher/sessions/start",
            json={
                "batch": "CSE-A",
                "semester_id": "fall-2024",
                "subject_id": "ENV",
                "class_type": "L",
                "start_time": "09:00",
                "end_time": "10:00",
            },
        )
        assert start.status_code == 200
        session_id = start.json()["session_id"]

        response = client.post(
            f"/api/teacher/sessions/{session_id}/frame",
            data={"tolerance": "0.5", "mode": "detect"},
            files={"frame": ("frame.jpg", b"fake", "image/jpeg")},
        )

        # fake bytes can fail imdecode, so retry with actual jpeg bytes if needed
        if response.status_code == 400 and "Invalid image frame" in response.text:
            import cv2
            import numpy as np

            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            ok, buffer = cv2.imencode(".jpg", frame)
            assert ok is True
            response = client.post(
                f"/api/teacher/sessions/{session_id}/frame",
                data={"tolerance": "0.5", "mode": "detect"},
                files={"frame": ("frame.jpg", buffer.tobytes(), "image/jpeg")},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["session_id"] == session_id
        assert len(payload["marked_in_frame"]) == 2


def test_teacher_frame_recognize_skips_batch_mismatch(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "test_teacher_frame_batch_mismatch.db")
    initialize_db(db_path=db_path)
    _seed_teacher(db_path)
    _seed_student(db_path)
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=db_path)
    upsert_subject("ENV", "fall-2024", "Environment", 1, db_path=db_path)
    _assign_teacher(db_path, batch="F6")

    monkeypatch.setattr(
        "app.api.teacher._get_known_faces",
        lambda: {"student_ids": ["22BCS001"], "names": ["Rahul Sharma"], "encodings": []},
    )
    monkeypatch.setattr(
        "app.api.teacher.recognize_in_frame",
        lambda *_args, **_kwargs: [
            {
                "matched": True,
                "student_id": "22BCS001",
                "name": "Rahul Sharma",
                "distance": 0.12,
            }
        ],
    )

    with _client_for_db(db_path) as client:
        login = client.post(
            "/api/teacher/auth/login",
            json={"teacher_id": "admin", "password": "admin"},
        )
        assert login.status_code == 200

        start = client.post(
            "/api/teacher/sessions/start",
            json={
                "batch": "F6",
                "semester_id": "fall-2024",
                "subject_id": "ENV",
                "class_type": "L",
                "start_time": "09:00",
                "end_time": "10:00",
            },
        )
        assert start.status_code == 200
        session_id = start.json()["session_id"]

        import cv2
        import numpy as np

        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        ok, buffer = cv2.imencode(".jpg", frame)
        assert ok is True

        response = client.post(
            f"/api/teacher/sessions/{session_id}/frame",
            data={"tolerance": "0.6", "mode": "recognize"},
            files={"frame": ("frame.jpg", buffer.tobytes(), "image/jpeg")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert len(payload["marked_in_frame"]) == 1
        assert payload["marked_in_frame"][0]["student_id"] == "22BCS001"
        assert payload["marked_in_frame"][0]["status"] == "batch_mismatch"
        assert payload["marked_in_frame"][0]["warning"] == "Batch mismatch"
        assert payload["present_students"] == []


def test_teacher_frame_recognize_accepts_compound_batch_match(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "test_teacher_frame_compound_batch.db")
    initialize_db(db_path=db_path)
    _seed_teacher(db_path)
    _seed_student(db_path)
    upsert_student_profile(student_id="22BCS001", branch="CSE", batch="F6", db_path=db_path)
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=db_path)
    upsert_subject("ENV", "fall-2024", "Environment", 1, db_path=db_path)
    _assign_teacher(db_path, batch="F5F6")

    monkeypatch.setattr(
        "app.api.teacher._get_known_faces",
        lambda: {"student_ids": ["22BCS001"], "names": ["Rahul Sharma"], "encodings": []},
    )
    monkeypatch.setattr(
        "app.api.teacher.recognize_in_frame",
        lambda *_args, **_kwargs: [
            {
                "matched": True,
                "student_id": "22BCS001",
                "name": "Rahul Sharma",
                "distance": 0.11,
            }
        ],
    )

    with _client_for_db(db_path) as client:
        login = client.post(
            "/api/teacher/auth/login",
            json={"teacher_id": "admin", "password": "admin"},
        )
        assert login.status_code == 200

        start = client.post(
            "/api/teacher/sessions/start",
            json={
                "batch": "F5F6",
                "semester_id": "fall-2024",
                "subject_id": "ENV",
                "class_type": "L",
                "start_time": "09:00",
                "end_time": "10:00",
            },
        )
        assert start.status_code == 200
        session_id = start.json()["session_id"]

        import cv2
        import numpy as np

        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        ok, buffer = cv2.imencode(".jpg", frame)
        assert ok is True

        response = client.post(
            f"/api/teacher/sessions/{session_id}/frame",
            data={"tolerance": "0.6", "mode": "recognize"},
            files={"frame": ("frame.jpg", buffer.tobytes(), "image/jpeg")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert len(payload["marked_in_frame"]) == 1
        assert payload["marked_in_frame"][0]["student_id"] == "22BCS001"
        assert len(payload["present_students"]) == 1
        assert payload["present_students"][0]["student_id"] == "22BCS001"


def test_teacher_frame_recognize_accepts_case_insensitive_single_batch(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "test_teacher_frame_case_insensitive_batch.db")
    initialize_db(db_path=db_path)
    _seed_teacher(db_path)
    _seed_student(db_path)
    upsert_student_profile(student_id="22BCS001", branch="CSE", batch="f6", db_path=db_path)
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=db_path)
    upsert_subject("DAA", "fall-2024", "DAA", 1, db_path=db_path)
    _assign_teacher(db_path, subject_id="DAA", batch="F6")

    monkeypatch.setattr(
        "app.api.teacher._get_known_faces",
        lambda: {"student_ids": ["22BCS001"], "names": ["Rahul Sharma"], "encodings": []},
    )
    monkeypatch.setattr(
        "app.api.teacher.recognize_in_frame",
        lambda *_args, **_kwargs: [
            {
                "matched": True,
                "student_id": "22BCS001",
                "name": "Rahul Sharma",
                "distance": 0.1,
            }
        ],
    )

    with _client_for_db(db_path) as client:
        login = client.post(
            "/api/teacher/auth/login",
            json={"teacher_id": "admin", "password": "admin"},
        )
        assert login.status_code == 200

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
        assert start.status_code == 200
        session_id = start.json()["session_id"]

        import cv2
        import numpy as np

        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        ok, buffer = cv2.imencode(".jpg", frame)
        assert ok is True

        response = client.post(
            f"/api/teacher/sessions/{session_id}/frame",
            data={"tolerance": "0.6", "mode": "recognize"},
            files={"frame": ("frame.jpg", buffer.tobytes(), "image/jpeg")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["marked_in_frame"][0]["status"] == "registered"
        assert payload["present_students"][0]["student_id"] == "22BCS001"

from fastapi.testclient import TestClient
import numpy as np

from app.api.main import create_app
from app.db import (
    get_student_with_profile,
    get_teacher_user,
    get_connection,
    initialize_db,
    list_present_students_for_session,
    list_teacher_assignments,
    upsert_class_session,
    upsert_admin_user,
    replace_teacher_assignments,
    upsert_semester,
    upsert_session_attendance,
    upsert_student,
    upsert_student_profile,
    upsert_student_subject,
    upsert_subject,
    upsert_teacher_user,
)
from app.security import verify_password
from app.face_utils import save_known_faces


def _seed_student(db_path: str) -> None:
    upsert_student(student_id="22BCS001", name="Rahul Sharma", db_path=db_path)
    upsert_student_profile(student_id="22BCS001", branch="CSE", batch="CSE-A", db_path=db_path)


def _seed_teacher(db_path: str) -> None:
    upsert_teacher_user(
        teacher_id="admin",
        name="Faculty Demo",
        email="faculty.demo@test.com",
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


def _enroll_student(
    db_path: str,
    student_id: str = "22BCS001",
    semester_id: str = "fall-2024",
    subject_id: str = "ENV",
) -> None:
    if get_student_with_profile(student_id=student_id, db_path=db_path) is None:
        upsert_student(student_id=student_id, name="Test Student", db_path=db_path)
    upsert_student_subject(
        student_id=student_id,
        semester_id=semester_id,
        subject_id=subject_id,
        db_path=db_path,
    )


def _session_attendance_count(db_path: str, session_id: int, student_id: str) -> int:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) AS row_count
            FROM session_attendance
            WHERE session_id = ?
                AND student_id = ?
                AND present = 1
            """,
            (session_id, student_id),
        )
        return int(cursor.fetchone()["row_count"])


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


def _image_files(count: int = 5) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [
        ("images", (f"face{index}.jpg", f"fake-image-{index}".encode(), "image/jpeg"))
        for index in range(1, count + 1)
    ]


def _fake_enrollment_payload(student_id: str, name: str, branch: str, batch: str, image_count: int) -> dict:
    return {
        "student": {
            "student_id": student_id,
            "name": name,
            "branch": branch,
            "batch": batch,
        },
        "uploaded_images": image_count,
        "valid_images": image_count,
        "rejected_images": 0,
        "results": [
            {"filename": f"face{index}.jpg", "accepted": True, "message": "Accepted"}
            for index in range(1, image_count + 1)
        ],
    }


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
    _enroll_student(db_path, subject_id="ENV")
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
    _enroll_student(db_path, subject_id="DAA")
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
    _enroll_student(db_path, subject_id="DAALAB")

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
        assert payload["teacher"]["email"] == "faculty.demo@test.com"


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

    async def fake_enroll(**kwargs):
        from app.db import upsert_student, upsert_student_profile

        upsert_student(kwargs["student_id"], kwargs["name"], db_path=kwargs["db_path"])
        upsert_student_profile(kwargs["student_id"], kwargs["branch"], kwargs["batch"], db_path=kwargs["db_path"])
        return _fake_enrollment_payload(
            kwargs["student_id"],
            kwargs["name"],
            kwargs["branch"],
            kwargs["batch"],
            len(kwargs["images"]),
        )

    monkeypatch.setattr("app.api.admin.enroll_student_uploads", fake_enroll)

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
            files=_image_files(),
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["uploaded_images"] == 5
        assert payload["valid_images"] == 5
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
    _enroll_student(db_path, subject_id="ENV")

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
                "email": "faculty001@test.com",
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
        assert payload["teacher"] == {
            "teacher_id": "faculty001",
            "name": "Faculty One",
            "email": "faculty001@test.com",
        }
        assert len(payload["assignments"]) == 1
        assert payload["assignments"][0]["subject_name"] == "Environment"
        assert payload["assignments"][0]["batch"] == "CSE-A"

        saved_teacher = get_teacher_user("faculty001", db_path=db_path)
        assert saved_teacher is not None
        assert saved_teacher["password"] != "pass123"
        assert verify_password("pass123", saved_teacher["password"])
        saved_assignments = list_teacher_assignments("faculty001", db_path=db_path)
        assert len(saved_assignments) == 1
        assert saved_assignments[0]["class_type"] == "L"


def test_admin_created_teacher_email_login_persists_across_clients(tmp_path) -> None:
    db_path = str(tmp_path / "test_admin_teacher_email_login.db")
    initialize_db(db_path=db_path)
    _seed_admin(db_path)
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=db_path)
    upsert_subject("ENV", "fall-2024", "Environment", 1, db_path=db_path)
    _enroll_student(db_path, subject_id="ENV")

    with _client_for_db(db_path) as client:
        assert client.post(
            "/api/admin/auth/login",
            json={"admin_id": "admin", "password": "admin"},
        ).status_code == 200
        response = client.post(
            "/api/admin/teachers/register",
            json={
                "teacher_id": "T001",
                "name": "Test Teacher",
                "email": "teacher@test.com",
                "password": "Test123",
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
        assert client.post("/api/admin/auth/logout").status_code == 200

    with _client_for_db(db_path) as client:
        by_email = client.post(
            "/api/teacher/auth/login",
            json={"teacher_id": "teacher@test.com", "password": "Test123"},
        )
        assert by_email.status_code == 200
        assert by_email.json()["teacher"]["teacher_id"] == "T001"
        assert client.post("/api/teacher/auth/logout").status_code == 200

        by_id = client.post(
            "/api/teacher/auth/login",
            json={"teacher_id": "T001", "password": "Test123"},
        )
        assert by_id.status_code == 200

        wrong_password = client.post(
            "/api/teacher/auth/login",
            json={"teacher_id": "teacher@test.com", "password": "wrong"},
        )
        assert wrong_password.status_code == 401


def test_admin_lists_persisted_teachers_and_students(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "test_admin_lists.db")
    initialize_db(db_path=db_path)
    _seed_admin(db_path)
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=db_path)
    upsert_subject("ENV", "fall-2024", "Environment", 1, db_path=db_path)
    _enroll_student(db_path, student_id="S001", subject_id="ENV")

    async def fake_enroll(**kwargs):
        from app.db import upsert_student, upsert_student_profile

        upsert_student(kwargs["student_id"], kwargs["name"], db_path=kwargs["db_path"])
        upsert_student_profile(kwargs["student_id"], kwargs["branch"], kwargs["batch"], db_path=kwargs["db_path"])
        return _fake_enrollment_payload(
            kwargs["student_id"],
            kwargs["name"],
            kwargs["branch"],
            kwargs["batch"],
            len(kwargs["images"]),
        )

    monkeypatch.setattr("app.api.admin.enroll_student_uploads", fake_enroll)

    with _client_for_db(db_path) as client:
        assert client.post(
            "/api/admin/auth/login",
            json={"admin_id": "admin", "password": "admin"},
        ).status_code == 200
        assert client.post(
            "/api/admin/teachers/register",
            json={
                "teacher_id": "T001",
                "name": "Teacher One",
                "email": "teacher1@test.com",
                "password": "Test123",
                "assignments": [
                    {
                        "semester_id": "fall-2024",
                        "subject_id": "ENV",
                        "batch": "CSE-A",
                        "class_type": "L",
                    }
                ],
            },
        ).status_code == 200
        assert client.post(
            "/api/admin/students/register",
            data={
                "student_id": "S001",
                "name": "Student One",
                "branch": "CSE",
                "batch": "CSE-A",
            },
            files=_image_files(),
        ).status_code == 200

    with _client_for_db(db_path) as client:
        assert client.post(
            "/api/admin/auth/login",
            json={"admin_id": "admin", "password": "admin"},
        ).status_code == 200
        teachers = client.get("/api/admin/teachers")
        students = client.get("/api/admin/students")
        assert teachers.status_code == 200
        assert students.status_code == 200
        assert [item["teacher_id"] for item in teachers.json()["items"]] == ["T001"]
        assert [item["student_id"] for item in students.json()["items"]] == ["S001"]


def test_admin_register_teacher_rejects_duplicate_email(tmp_path) -> None:
    db_path = str(tmp_path / "test_admin_register_teacher_duplicate_email.db")
    initialize_db(db_path=db_path)
    _seed_admin(db_path)
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=db_path)
    upsert_subject("ENV", "fall-2024", "Environment", 1, db_path=db_path)
    _enroll_student(db_path, subject_id="ENV")

    payload = {
        "name": "Teacher",
        "email": "same@test.com",
        "password": "Test123",
        "assignments": [
            {
                "semester_id": "fall-2024",
                "subject_id": "ENV",
                "batch": "CSE-A",
                "class_type": "L",
            }
        ],
    }

    with _client_for_db(db_path) as client:
        assert client.post(
            "/api/admin/auth/login",
            json={"admin_id": "admin", "password": "admin"},
        ).status_code == 200
        first = client.post(
            "/api/admin/teachers/register",
            json={**payload, "teacher_id": "T001"},
        )
        second = client.post(
            "/api/admin/teachers/register",
            json={**payload, "teacher_id": "T002"},
        )
        assert first.status_code == 200
        assert second.status_code == 400


def test_admin_register_teacher_rejects_invalid_subject_semester(tmp_path) -> None:
    db_path = str(tmp_path / "test_admin_register_teacher_invalid_subject.db")
    initialize_db(db_path=db_path)
    _seed_admin(db_path)
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=db_path)
    upsert_semester("spring-2025", "Spring 2025", 2, 1, db_path=db_path)
    upsert_subject("ENV", "fall-2024", "Environment", 1, db_path=db_path)
    _enroll_student(db_path, subject_id="ENV")

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
                "email": "faculty002@test.com",
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
    _enroll_student(db_path, subject_id="ENV")
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

    async def fake_enroll(**kwargs):
        from app.db import upsert_student, upsert_student_profile

        upsert_student(kwargs["student_id"], kwargs["name"], db_path=kwargs["db_path"])
        upsert_student_profile(kwargs["student_id"], kwargs["branch"], kwargs["batch"], db_path=kwargs["db_path"])
        return _fake_enrollment_payload(
            kwargs["student_id"],
            kwargs["name"],
            kwargs["branch"],
            kwargs["batch"],
            len(kwargs["images"]),
        )

    monkeypatch.setattr("app.api.teacher.enroll_student_uploads", fake_enroll)

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
            files=_image_files(),
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["uploaded_images"] == 5
        assert payload["valid_images"] == 5
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
    _enroll_student(db_path, subject_id="ENV")
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
    _enroll_student(db_path, subject_id="ENV")
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

        first_response = client.post(
            f"/api/teacher/sessions/{session_id}/frame",
            data={"tolerance": "0.6", "mode": "recognize"},
            files={"frame": ("frame.jpg", buffer.tobytes(), "image/jpeg")},
        )
        assert first_response.status_code == 200
        assert first_response.json()["marked_in_frame"][0]["status"] == "batch_mismatch"

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
    _enroll_student(db_path, subject_id="ENV")
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

        first_response = client.post(
            f"/api/teacher/sessions/{session_id}/frame",
            data={"tolerance": "0.6", "mode": "recognize"},
            files={"frame": ("frame.jpg", buffer.tobytes(), "image/jpeg")},
        )
        assert first_response.status_code == 200
        assert first_response.json()["marked_in_frame"][0]["status"] == "confirming"

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
    _enroll_student(db_path, subject_id="DAA")
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

        first_response = client.post(
            f"/api/teacher/sessions/{session_id}/frame",
            data={"tolerance": "0.6", "mode": "recognize"},
            files={"frame": ("frame.jpg", buffer.tobytes(), "image/jpeg")},
        )
        assert first_response.status_code == 200
        assert first_response.json()["marked_in_frame"][0]["status"] == "confirming"

        response = client.post(
            f"/api/teacher/sessions/{session_id}/frame",
            data={"tolerance": "0.6", "mode": "recognize"},
            files={"frame": ("frame.jpg", buffer.tobytes(), "image/jpeg")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["marked_in_frame"][0]["status"] == "registered"
        assert payload["present_students"][0]["student_id"] == "22BCS001"


def test_teacher_frame_recognize_accepts_branch_session_for_section_student(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "test_teacher_frame_branch_session_section_student.db")
    initialize_db(db_path=db_path)
    _seed_teacher(db_path)
    upsert_student(student_id="992401030315", name="Arshdeep Singh", db_path=db_path)
    upsert_student_profile(student_id="992401030315", branch="CSE", batch="CSE-F6", db_path=db_path)
    upsert_semester("spring-2025", "Spring 2025", 1, 1, db_path=db_path)
    upsert_subject("CN", "spring-2025", "Computer Networks", 1, db_path=db_path)
    _enroll_student(db_path, student_id="992401030315", semester_id="spring-2025", subject_id="CN")
    replace_teacher_assignments(
        teacher_id="admin",
        assignments=[
            {
                "semester_id": "spring-2025",
                "subject_id": "CN",
                "batch": "CSE",
                "class_type": "L",
            }
        ],
        db_path=db_path,
    )

    monkeypatch.setattr(
        "app.api.teacher._get_known_faces",
        lambda: {"student_ids": ["992401030315"], "names": ["Arshdeep Singh"], "encodings": [np.zeros(128)]},
    )
    monkeypatch.setattr(
        "app.api.teacher.recognize_in_frame",
        lambda *_args, **_kwargs: [
            {
                "matched": True,
                "student_id": "992401030315",
                "name": "Arshdeep Singh",
                "distance": 0.18,
                "best_student_id": "992401030315",
                "best_name": "Arshdeep Singh",
                "threshold": 0.6,
                "reason": "matched",
            }
        ],
    )

    with _client_for_db(db_path) as client:
        assert client.post(
            "/api/teacher/auth/login",
            json={"teacher_id": "admin", "password": "admin"},
        ).status_code == 200
        start = client.post(
            "/api/teacher/sessions/start",
            json={
                "batch": "CSE",
                "semester_id": "spring-2025",
                "subject_id": "CN",
                "class_type": "L",
                "start_time": "09:00",
                "end_time": "10:00",
            },
        )
        assert start.status_code == 200
        session_id = start.json()["session_id"]

        import cv2

        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        ok, buffer = cv2.imencode(".jpg", frame)
        assert ok is True

        first_response = client.post(
            f"/api/teacher/sessions/{session_id}/frame",
            data={"tolerance": "0.6", "mode": "recognize"},
            files={"frame": ("frame.jpg", buffer.tobytes(), "image/jpeg")},
        )
        assert first_response.status_code == 200
        first_payload = first_response.json()
        assert first_payload["marked_in_frame"][0]["status"] == "confirming"
        assert first_payload["debug"]["loaded_student_ids"] == ["992401030315"]
        assert first_payload["debug"]["decisions"][0]["student_db_batch"] == "CSE-F6"
        assert first_payload["debug"]["decisions"][0]["active_session_batch"] == "CSE"

        second_response = client.post(
            f"/api/teacher/sessions/{session_id}/frame",
            data={"tolerance": "0.6", "mode": "recognize"},
            files={"frame": ("frame.jpg", buffer.tobytes(), "image/jpeg")},
        )
        assert second_response.status_code == 200
        second_payload = second_response.json()
        assert second_payload["marked_in_frame"][0]["status"] == "registered"
        assert second_payload["present_students"][0]["student_id"] == "992401030315"
        assert second_payload["debug"]["decisions"][0]["reason"] == "attendance_marked"


def test_teacher_frame_recognize_loads_persisted_encodings_for_db_students(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "test_teacher_frame_persisted_encodings.db")
    encodings_path = tmp_path / "encodings.pkl"
    initialize_db(db_path=db_path)
    _seed_teacher(db_path)
    _seed_student(db_path)
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=db_path)
    upsert_subject("ENV", "fall-2024", "Environment", 1, db_path=db_path)
    _enroll_student(db_path, subject_id="ENV")
    _assign_teacher(db_path, batch="CSE-A")
    save_known_faces(
        {
            "student_ids": ["22BCS001", "missing-student"],
            "names": ["Rahul Sharma", "Missing"],
            "encodings": [np.full(128, 0.1), np.full(128, 0.9)],
        },
        encodings_path=encodings_path,
    )

    monkeypatch.setattr("app.api.teacher.ENCODINGS_PATH", encodings_path)
    cache = __import__("app.api.teacher", fromlist=["_KNOWN_FACES_CACHE"])._KNOWN_FACES_CACHE
    cache["file_token"] = None
    cache["data"] = None
    cache["db_path"] = None
    cache["active_db_path"] = None

    def fake_recognize(_frame, known_faces, tolerance=0.6):
        assert known_faces["student_ids"] == ["22BCS001"]
        assert len(known_faces["encodings"]) == 1
        return [
            {
                "matched": True,
                "student_id": "22BCS001",
                "name": "Rahul Sharma",
                "distance": 0.1,
            }
        ]

    monkeypatch.setattr("app.api.teacher.recognize_in_frame", fake_recognize)

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

        import cv2

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
        assert payload["marked_in_frame"][0]["student_id"] == "22BCS001"
        assert payload["marked_in_frame"][0]["status"] == "confirming"

        response = client.post(
            f"/api/teacher/sessions/{session_id}/frame",
            data={"tolerance": "0.6", "mode": "recognize"},
            files={"frame": ("frame.jpg", buffer.tobytes(), "image/jpeg")},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["marked_in_frame"][0]["student_id"] == "22BCS001"
        assert payload["present_students"][0]["student_id"] == "22BCS001"


def test_teacher_frame_recognize_does_not_duplicate_attendance_for_session(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "test_teacher_frame_no_duplicate_attendance.db")
    initialize_db(db_path=db_path)
    _seed_teacher(db_path)
    _seed_student(db_path)
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=db_path)
    upsert_subject("ENV", "fall-2024", "Environment", 1, db_path=db_path)
    _enroll_student(db_path, subject_id="ENV")
    _assign_teacher(db_path, batch="CSE-A")

    monkeypatch.setattr(
        "app.api.teacher._get_known_faces",
        lambda: {"student_ids": ["22BCS001"], "names": ["Rahul Sharma"], "encodings": [np.zeros(128)]},
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
        assert client.post(
            "/api/teacher/auth/login",
            json={"teacher_id": "admin", "password": "admin"},
        ).status_code == 200
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
        session_id = start.json()["session_id"]

        import cv2

        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        ok, buffer = cv2.imencode(".jpg", frame)
        assert ok is True

        for _ in range(2):
            response = client.post(
                f"/api/teacher/sessions/{session_id}/frame",
                data={"tolerance": "0.6", "mode": "recognize"},
                files={"frame": ("frame.jpg", buffer.tobytes(), "image/jpeg")},
            )
            assert response.status_code == 200

    rows = list_present_students_for_session(session_id, db_path=db_path)
    assert [row["student_id"] for row in rows] == ["22BCS001"]


def test_runtime_attendance_persists_updates_summary_and_survives_restart(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "test_runtime_attendance_persistence.db")
    initialize_db(db_path=db_path)
    _seed_teacher(db_path)
    _seed_student(db_path)
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=db_path)
    upsert_subject("ENV", "fall-2024", "Environment", 1, db_path=db_path)
    _enroll_student(db_path, subject_id="ENV")
    _assign_teacher(db_path, batch="CSE-A")

    monkeypatch.setattr(
        "app.api.teacher._get_known_faces",
        lambda: {"student_ids": ["22BCS001"], "names": ["Rahul Sharma"], "encodings": [np.zeros(128)]},
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

    import cv2

    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    ok, buffer = cv2.imencode(".jpg", frame)
    assert ok is True

    with _client_for_db(db_path) as client:
        assert client.post(
            "/api/teacher/auth/login",
            json={"teacher_id": "admin", "password": "admin"},
        ).status_code == 200
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

        first = client.post(
            f"/api/teacher/sessions/{session_id}/frame",
            data={"tolerance": "0.6", "mode": "recognize"},
            files={"frame": ("frame.jpg", buffer.tobytes(), "image/jpeg")},
        )
        assert first.status_code == 200
        assert first.json()["marked_in_frame"][0]["status"] == "confirming"
        assert _session_attendance_count(db_path, session_id, "22BCS001") == 0

        second = client.post(
            f"/api/teacher/sessions/{session_id}/frame",
            data={"tolerance": "0.6", "mode": "recognize"},
            files={"frame": ("frame.jpg", buffer.tobytes(), "image/jpeg")},
        )
        assert second.status_code == 200
        payload = second.json()
        assert payload["marked_in_frame"][0]["status"] == "registered"
        assert payload["debug"]["decisions"][0]["reason"] == "attendance_marked"
        assert payload["debug"]["decisions"][0]["attendance_inserted"] is True
        assert _session_attendance_count(db_path, session_id, "22BCS001") == 1

        assert client.post(
            "/api/auth/login",
            json={"student_id": "22BCS001", "password": "22BCS001"},
        ).status_code == 200
        summary = client.get("/api/attendance/summary", params={"semester_id": "fall-2024"})
        assert summary.status_code == 200
        assert summary.json()["total_held"] == 1
        assert summary.json()["total_attended"] == 1
        assert summary.json()["total_pct"] == 100

    with _client_for_db(db_path) as restarted_client:
        assert _session_attendance_count(db_path, session_id, "22BCS001") == 1
        assert restarted_client.post(
            "/api/auth/login",
            json={"student_id": "22BCS001", "password": "22BCS001"},
        ).status_code == 200
        restarted_summary = restarted_client.get("/api/attendance/summary", params={"semester_id": "fall-2024"})
        assert restarted_summary.status_code == 200
        assert restarted_summary.json()["total_attended"] == 1


def test_runtime_attendance_does_not_duplicate_same_student_same_session(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "test_runtime_attendance_no_duplicate.db")
    initialize_db(db_path=db_path)
    _seed_teacher(db_path)
    _seed_student(db_path)
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=db_path)
    upsert_subject("ENV", "fall-2024", "Environment", 1, db_path=db_path)
    _enroll_student(db_path, subject_id="ENV")
    _assign_teacher(db_path, batch="CSE-A")

    monkeypatch.setattr(
        "app.api.teacher._get_known_faces",
        lambda: {"student_ids": ["22BCS001"], "names": ["Rahul Sharma"], "encodings": [np.zeros(128)]},
    )
    monkeypatch.setattr(
        "app.api.teacher.recognize_in_frame",
        lambda *_args, **_kwargs: [
            {"matched": True, "student_id": "22BCS001", "name": "Rahul Sharma", "distance": 0.1}
        ],
    )

    import cv2

    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    ok, buffer = cv2.imencode(".jpg", frame)
    assert ok is True

    with _client_for_db(db_path) as client:
        assert client.post("/api/teacher/auth/login", json={"teacher_id": "admin", "password": "admin"}).status_code == 200
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
        session_id = start.json()["session_id"]
        for _ in range(3):
            response = client.post(
                f"/api/teacher/sessions/{session_id}/frame",
                data={"tolerance": "0.6", "mode": "recognize"},
                files={"frame": ("frame.jpg", buffer.tobytes(), "image/jpeg")},
            )
            assert response.status_code == 200

    assert _session_attendance_count(db_path, session_id, "22BCS001") == 1


def test_runtime_attendance_rejects_student_not_registered_for_subject(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "test_runtime_attendance_subject_not_registered.db")
    initialize_db(db_path=db_path)
    _seed_teacher(db_path)
    _seed_student(db_path)
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=db_path)
    upsert_subject("SE", "fall-2024", "Software Engineering", 1, db_path=db_path)
    _assign_teacher(db_path, subject_id="SE", batch="CSE-A")

    monkeypatch.setattr(
        "app.api.teacher._get_known_faces",
        lambda: {"student_ids": ["22BCS001"], "names": ["Rahul Sharma"], "encodings": [np.zeros(128)]},
    )
    monkeypatch.setattr(
        "app.api.teacher.recognize_in_frame",
        lambda *_args, **_kwargs: [
            {"matched": True, "student_id": "22BCS001", "name": "Rahul Sharma", "distance": 0.1}
        ],
    )

    import cv2

    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    ok, buffer = cv2.imencode(".jpg", frame)
    assert ok is True

    with _client_for_db(db_path) as client:
        assert client.post("/api/teacher/auth/login", json={"teacher_id": "admin", "password": "admin"}).status_code == 200
        start = client.post(
            "/api/teacher/sessions/start",
            json={
                "batch": "CSE-A",
                "semester_id": "fall-2024",
                "subject_id": "SE",
                "class_type": "L",
                "start_time": "09:00",
                "end_time": "10:00",
            },
        )
        session_id = start.json()["session_id"]
        for _ in range(2):
            response = client.post(
                f"/api/teacher/sessions/{session_id}/frame",
                data={"tolerance": "0.6", "mode": "recognize"},
                files={"frame": ("frame.jpg", buffer.tobytes(), "image/jpeg")},
            )
            assert response.status_code == 200

        payload = response.json()
        assert payload["marked_in_frame"][0]["status"] == "subject_not_registered"
        assert payload["marked_in_frame"][0]["warning"] == "Student is not registered for this subject."
        assert payload["present_students"] == []

    assert _session_attendance_count(db_path, session_id, "22BCS001") == 0


def test_runtime_teacher_without_assignment_cannot_start_or_manage_subject_session(tmp_path) -> None:
    db_path = str(tmp_path / "test_runtime_teacher_assignment_required.db")
    initialize_db(db_path=db_path)
    _seed_teacher(db_path)
    _seed_student(db_path)
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=db_path)
    upsert_subject("ENV", "fall-2024", "Environment", 1, db_path=db_path)
    _enroll_student(db_path, subject_id="ENV")

    with _client_for_db(db_path) as client:
        assert client.post("/api/teacher/auth/login", json={"teacher_id": "admin", "password": "admin"}).status_code == 200
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
        assert start.status_code == 403
        assert start.json()["detail"] == "Class is not assigned to this teacher"

        upsert_class_session(
            99,
            "ENV",
            "fall-2024",
            "L",
            "2024-09-01",
            batch="CSE-A",
            teacher_id="admin",
            is_active=1,
            db_path=db_path,
        )
        manage = client.get("/api/teacher/sessions/99/attendance")
        assert manage.status_code == 403


def test_runtime_assignments_enrollments_and_attendance_persist_after_restart(tmp_path) -> None:
    db_path = str(tmp_path / "test_runtime_restart_persistence.db")
    initialize_db(db_path=db_path)
    _seed_teacher(db_path)
    _seed_student(db_path)
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=db_path)
    upsert_subject("ENV", "fall-2024", "Environment", 1, db_path=db_path)
    _enroll_student(db_path, subject_id="ENV")
    _assign_teacher(db_path, batch="CSE-A")
    upsert_class_session(1, "ENV", "fall-2024", "L", "2024-09-01", batch="CSE-A", teacher_id="admin", db_path=db_path)
    upsert_session_attendance(1, "22BCS001", 1, db_path=db_path)

    initialize_db(db_path=db_path)

    assert list_teacher_assignments("admin", db_path=db_path)[0]["subject_id"] == "ENV"
    assert _session_attendance_count(db_path, 1, "22BCS001") == 1
    with _client_for_db(db_path) as client:
        assert client.post(
            "/api/auth/login",
            json={"student_id": "22BCS001", "password": "22BCS001"},
        ).status_code == 200
        summary = client.get("/api/attendance/summary", params={"semester_id": "fall-2024"})
        assert summary.status_code == 200
        assert summary.json()["total_attended"] == 1

import pytest
from pathlib import Path

from app.db import (
    initialize_db,
    upsert_student,
    upsert_student_profile,
    update_student_password,
    get_student_by_login,
    upsert_semester,
    upsert_subject,
    delete_subject,
    update_subject,
    delete_student,
    get_admin_dashboard_stats,
    create_class_session,
    upsert_session_attendance,
    list_student_attendance_history,
)
from app.security import verify_password


@pytest.fixture
def temp_db(tmp_path: Path) -> str:
    db_file = str(tmp_path / "test_prod.db")
    initialize_db(db_file)
    return db_file


def test_student_password_hashing(temp_db: str):
    student_id = "STU_HASH_1"
    upsert_student(student_id, "Test Hash Student", db_path=temp_db)
    update_student_password(student_id, "SecretPass123", db_path=temp_db)

    student = get_student_by_login(student_id, db_path=temp_db)
    assert student is not None
    assert student["password"].startswith("pbkdf2_sha256$")
    assert verify_password("SecretPass123", student["password"]) is True
    assert verify_password("WrongPass", student["password"]) is False


def test_subject_crud(temp_db: str):
    semester_id = "fall-2024"
    upsert_semester(semester_id, "Fall 2024", 1, 1, db_path=temp_db)

    # Create
    upsert_subject("MATH101", semester_id, "Mathematics 101", 1, db_path=temp_db)

    # Update
    update_subject("MATH101", semester_id, "Advanced Mathematics", 2, db_path=temp_db)

    # Delete
    delete_subject("MATH101", semester_id, db_path=temp_db)


def test_admin_dashboard_stats(temp_db: str):
    semester_id = "fall-2024"
    upsert_semester(semester_id, "Fall 2024", 1, 1, db_path=temp_db)
    upsert_student("S001", "Student 1", db_path=temp_db)
    upsert_student_profile("S001", "CSE", "CSE-A", db_path=temp_db)
    upsert_subject("ENV", semester_id, "Environment", 1, db_path=temp_db)

    s_id = create_class_session("ENV", semester_id, "L", "2024-09-01", "CSE-A", "09:00", "10:00", None, db_path=temp_db)
    upsert_session_attendance(s_id, "S001", 1, db_path=temp_db)

    stats = get_admin_dashboard_stats(semester_id=semester_id, db_path=temp_db)
    assert stats["total_students"] == 1
    assert stats["total_subjects"] == 1
    assert stats["total_sessions"] == 1
    assert len(stats["recent_attendance"]) == 1
    assert stats["recent_attendance"][0]["student_id"] == "S001"


def test_student_attendance_history(temp_db: str):
    semester_id = "fall-2024"
    upsert_semester(semester_id, "Fall 2024", 1, 1, db_path=temp_db)
    upsert_student("S002", "Student 2", db_path=temp_db)
    upsert_student_profile("S002", "CSE", "CSE-A", db_path=temp_db)
    upsert_subject("ENV", semester_id, "Environment", 1, db_path=temp_db)

    from app.db import upsert_student_subject
    upsert_student_subject("S002", semester_id, "ENV", db_path=temp_db)

    s_id = create_class_session("ENV", semester_id, "L", "2026-08-12", "CSE-A", "09:00", "10:00", None, db_path=temp_db)
    upsert_session_attendance(s_id, "S002", 1, db_path=temp_db)

    history = list_student_attendance_history("S002", semester_id, db_path=temp_db)
    assert len(history) == 1
    assert history[0]["session_id"] == s_id
    assert history[0]["present"] == 1

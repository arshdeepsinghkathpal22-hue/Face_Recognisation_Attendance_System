import pytest
import sqlite3
from pathlib import Path

from app.db import (
    initialize_db,
    upsert_student,
    upsert_student_profile,
    upsert_semester,
    upsert_subject,
    upsert_student_subject,
    create_class_session,
    upsert_session_attendance,
    upsert_teacher_user,
    upsert_teacher_assignment,
)
from app.services.attendance_service import build_attendance_summary


@pytest.fixture
def temp_db(tmp_path: Path) -> str:
    db_file = str(tmp_path / "test_attendance.db")
    initialize_db(db_file)
    return db_file


def test_registered_subjects_only(temp_db: str):
    # Setup student
    student_id = "STU001"
    semester_id = "fall-2024"
    upsert_student(student_id, "John Doe", db_path=temp_db)
    upsert_student_profile(student_id, branch="CSE", batch="CSE-F1", db_path=temp_db)
    upsert_semester(semester_id, "Fall 2024", sort_order=1, is_active=1, db_path=temp_db)

    # Subjects: Subject A (registered), Subject B (NOT registered)
    upsert_subject("SUB_A", semester_id, "Subject A", sort_order=1, db_path=temp_db)
    upsert_subject("SUB_B", semester_id, "Subject B", sort_order=2, db_path=temp_db)
    upsert_student_subject(student_id, semester_id, "SUB_A", db_path=temp_db)

    # Teacher assignment
    upsert_teacher_user("T1", "Teacher One", "pass", db_path=temp_db)
    upsert_teacher_assignment("T1", semester_id, "SUB_A", "CSE-F1", "L", db_path=temp_db)
    upsert_teacher_assignment("T1", semester_id, "SUB_B", "CSE-F1", "L", db_path=temp_db)

    # Sessions for Subject A: 10 held, 7 attended
    for i in range(10):
        s_id = create_class_session("SUB_A", semester_id, "L", f"2024-09-{i+1:02d}", "CSE-F1", "09:00", "10:00", "T1", db_path=temp_db)
        if i < 7:
            upsert_session_attendance(s_id, student_id, 1, db_path=temp_db)

    # Sessions for Subject B: 10 held, student not registered
    for i in range(10):
        create_class_session("SUB_B", semester_id, "L", f"2024-09-{i+1:02d}", "CSE-F1", "09:00", "10:00", "T1", db_path=temp_db)

    summary = build_attendance_summary(student_id, semester_id, temp_db)

    # Only SUB_A should be in rows
    assert len(summary["rows"]) == 1
    assert summary["rows"][0]["subject_id"] == "SUB_A"
    assert summary["rows"][0]["lecture"]["held"] == 10
    assert summary["rows"][0]["lecture"]["attended"] == 7
    assert summary["rows"][0]["lecture"]["pct"] == 70

    # Total recorded attendance denominator MUST NOT include SUB_B sessions
    assert summary["total_held"] == 10
    assert summary["total_attended"] == 7
    assert summary["total_pct"] == 70


def test_type_breakdown_and_overall(temp_db: str):
    student_id = "STU002"
    semester_id = "fall-2024"
    upsert_student(student_id, "Jane Smith", db_path=temp_db)
    upsert_student_profile(student_id, branch="CSE", batch="CSE", db_path=temp_db)
    upsert_semester(semester_id, "Fall 2024", sort_order=1, is_active=1, db_path=temp_db)
    upsert_subject("ENV", semester_id, "Environment", sort_order=1, db_path=temp_db)
    upsert_student_subject(student_id, semester_id, "ENV", db_path=temp_db)

    upsert_teacher_user("T1", "Teacher One", "pass", db_path=temp_db)
    upsert_teacher_assignment("T1", semester_id, "ENV", "CSE", "L", db_path=temp_db)
    upsert_teacher_assignment("T1", semester_id, "ENV", "CSE", "P", db_path=temp_db)

    # 12 Lecture sessions held, 1 attended
    for i in range(12):
        s_id = create_class_session("ENV", semester_id, "L", f"2024-09-{i+1:02d}", "CSE", "09:00", "10:00", "T1", db_path=temp_db)
        if i == 0:
            upsert_session_attendance(s_id, student_id, 1, db_path=temp_db)

    # 2 Practical sessions held, 0 attended
    for i in range(2):
        create_class_session("ENV", semester_id, "P", f"2024-09-{i+1:02d}", "CSE", "11:00", "12:00", "T1", db_path=temp_db)

    summary = build_attendance_summary(student_id, semester_id, temp_db)
    row = summary["rows"][0]

    assert row["lecture"]["held"] == 12
    assert row["lecture"]["attended"] == 1
    assert row["lecture"]["pct"] == 8  # 1/12 = 8.33% -> 8%

    assert row["practical"]["held"] == 2
    assert row["practical"]["attended"] == 0
    assert row["practical"]["pct"] == 0

    assert row["tutorial"]["held"] == 0
    assert row["tutorial"]["pct"] is None

    # Overall: 1 / 14 = 7.14% -> 7%
    assert row["overall"]["held"] == 14
    assert row["overall"]["attended"] == 1
    assert row["overall"]["pct"] == 7

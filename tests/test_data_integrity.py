import pytest
from pathlib import Path
from datetime import datetime

from app.db import (
    initialize_db,
    upsert_student,
    upsert_student_profile,
    upsert_semester,
    upsert_subject,
    upsert_student_subject,
    create_class_session,
    upsert_session_attendance,
    list_student_attendance_history,
    fetch_subject_attendance_counts,
)
from app.services.attendance_service import build_attendance_summary


@pytest.fixture
def temp_db(tmp_path: Path) -> str:
    db_file = str(tmp_path / "test_integrity.db")
    initialize_db(db_file)
    return db_file


def test_unique_attendance_per_student_session(temp_db: str):
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=temp_db)
    upsert_student("S001", "Student One", db_path=temp_db)
    upsert_student_profile("S001", "CSE", "CSE-A", db_path=temp_db)
    upsert_subject("DAALAB", "fall-2024", "DAA Lab", 1, db_path=temp_db)
    upsert_student_subject("S001", "fall-2024", "DAALAB", db_path=temp_db)

    session_id = create_class_session("DAALAB", "fall-2024", "P", "2026-08-12", "CSE-A", "02:46", "03:36", "T1", db_path=temp_db)
    
    # First insertion -> Present
    upsert_session_attendance(session_id, "S001", 1, db_path=temp_db)
    
    # Second insertion -> Present update (upsert)
    upsert_session_attendance(session_id, "S001", 1, db_path=temp_db)

    history = list_student_attendance_history("S001", "fall-2024", db_path=temp_db)
    assert len(history) == 1
    assert history[0]["session_id"] == session_id
    assert history[0]["present"] == 1


def test_session_idempotency_prevents_duplicate_active_sessions(temp_db: str):
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=temp_db)
    upsert_subject("DAALAB", "fall-2024", "DAA Lab", 1, db_path=temp_db)

    today = datetime.now().strftime("%Y-%m-%d")
    s1 = create_class_session("DAALAB", "fall-2024", "P", today, "CSE-A", "02:46", "03:36", "T1", db_path=temp_db)
    s2 = create_class_session("DAALAB", "fall-2024", "P", today, "CSE-A", "02:46", "03:36", "T1", db_path=temp_db)

    assert s1 == s2, "Starting the same session twice must return the same session ID"


def test_cooldown_window_prevents_rapid_duplicate_sessions(temp_db: str):
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=temp_db)
    upsert_subject("DAALAB", "fall-2024", "DAA Lab", 1, db_path=temp_db)

    today = datetime.now().strftime("%Y-%m-%d")
    s1 = create_class_session("DAALAB", "fall-2024", "P", today, "CSE-A", "05:10", "06:00", None, db_path=temp_db)
    s2 = create_class_session("DAALAB", "fall-2024", "P", today, "CSE-A", "05:24", "06:14", None, db_path=temp_db)

    assert s1 == s2, "Starting session within 120 min cooldown for Lab must reuse original session ID"



def test_unregistered_subject_excluded_from_history(temp_db: str):
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=temp_db)
    upsert_student("S002", "Student Two", db_path=temp_db)
    upsert_student_profile("S002", "CSE", "CSE-A", db_path=temp_db)

    # Subject A (Registered), Subject B (Unregistered)
    upsert_subject("SUB_REG", "fall-2024", "Registered Subject", 1, db_path=temp_db)
    upsert_subject("SUB_UNREG", "fall-2024", "Unregistered Subject", 2, db_path=temp_db)
    upsert_student_subject("S002", "fall-2024", "SUB_REG", db_path=temp_db)

    create_class_session("SUB_REG", "fall-2024", "L", "2026-08-12", "CSE-A", "09:00", "10:00", "T1", db_path=temp_db)
    create_class_session("SUB_UNREG", "fall-2024", "L", "2026-08-12", "CSE-A", "10:00", "11:00", "T1", db_path=temp_db)

    history = list_student_attendance_history("S002", "fall-2024", db_path=temp_db)
    subject_ids = [h["subject_id"] for h in history]
    assert "SUB_REG" in subject_ids
    assert "SUB_UNREG" not in subject_ids


def test_no_obsolete_2024_seed_records_in_active_history(temp_db: str):
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=temp_db)
    upsert_student("S003", "Student Three", db_path=temp_db)
    upsert_student_profile("S003", "CSE", "CSE-A", db_path=temp_db)
    upsert_subject("ENV", "fall-2024", "Environment", 1, db_path=temp_db)
    upsert_student_subject("S003", "fall-2024", "ENV", db_path=temp_db)

    # Insert old 2024 session
    create_class_session("ENV", "fall-2024", "L", "2024-09-12", "CSE-A", "09:00", "10:00", "T1", db_path=temp_db)
    # Insert current 2026 session
    create_class_session("ENV", "fall-2024", "L", "2026-08-12", "CSE-A", "09:00", "10:00", "T1", db_path=temp_db)

    history = list_student_attendance_history("S003", "fall-2024", db_path=temp_db)
    dates = [h["session_date"] for h in history]
    assert "2026-08-12" in dates
    assert "2024-09-12" not in dates, "Obsolete 2024 seed data must not appear in student history"


def test_attendance_percentage_uses_unique_sessions(temp_db: str):
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=temp_db)
    upsert_student("S004", "Student Four", db_path=temp_db)
    upsert_student_profile("S004", "CSE", "CSE-A", db_path=temp_db)
    upsert_subject("DAA", "fall-2024", "DAA", 1, db_path=temp_db)
    upsert_student_subject("S004", "fall-2024", "DAA", db_path=temp_db)

    sess1 = create_class_session("DAA", "fall-2024", "L", "2026-08-12", "CSE-A", "09:00", "10:00", "T1", db_path=temp_db)
    sess2 = create_class_session("DAA", "fall-2024", "L", "2026-08-13", "CSE-A", "09:00", "10:00", "T1", db_path=temp_db)

    # Student attended sess1, missed sess2
    upsert_session_attendance(sess1, "S004", 1, db_path=temp_db)

    summary = build_attendance_summary("S004", "fall-2024", db_path=temp_db)
    daa_row = summary["rows"][0]
    assert daa_row["held_l"] == 2
    assert daa_row["attended_l"] == 1
    assert daa_row["current_l_pct"] == 50


def test_lab_subjects_forced_to_practical(temp_db: str):
    upsert_semester("fall-2024", "Fall 2024", 1, 1, db_path=temp_db)
    upsert_subject("DAALAB", "fall-2024", "DAA Lab", 1, db_path=temp_db)

    s_id = create_class_session("DAALAB", "fall-2024", "L", "2026-08-13", "CSE-A", "05:10", "06:00", None, db_path=temp_db)

    from app.db import get_class_session
    sess = get_class_session(s_id, db_path=temp_db)
    assert sess["class_type"] == "P", "Lab subjects must be forced to Practical ('P')"


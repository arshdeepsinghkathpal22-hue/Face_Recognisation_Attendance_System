import json
import sqlite3
from pathlib import Path

from app.config import DB_PATH
from app.db import initialize_db, get_connection

print(f"=== 1. SQLITE DATABASE PATH ===")
print(f"DB Path: {DB_PATH.resolve()}")

with get_connection(DB_PATH) as conn:
    print("\n=== 2. TABLE SCHEMAS ===")
    for table in ["students", "student_profile", "subjects", "student_subjects", "class_sessions", "session_attendance", "teacher_assignments"]:
        schema = conn.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'").fetchone()
        if schema:
            print(f"--- {table} ---")
            print(schema["sql"])

    print("\n=== 3. RAW ROWS FOR STUDENT 992401030315 ===")
    student = conn.execute("SELECT * FROM students WHERE student_id = '992401030315'").fetchone()
    print("Student:", dict(student) if student else "Not found")
    profile = conn.execute("SELECT * FROM student_profile WHERE student_id = '992401030315'").fetchone()
    print("Profile:", dict(profile) if profile else "Not found")

    subjects = conn.execute("SELECT * FROM student_subjects WHERE student_id = '992401030315'").fetchall()
    print("Registered Subjects:", [dict(s) for s in subjects])

    print("\n=== 4. RAW ROWS FOR DAA LAB SESSION (2026-08-12 DAA Lab 02:46) ===")
    sessions_daa = conn.execute("""
        SELECT cs.*, sub.name as subject_name
        FROM class_sessions cs
        JOIN subjects sub ON sub.id = cs.subject_id AND sub.semester_id = cs.semester_id
        WHERE cs.subject_id IN ('DAALAB', 'DAA') AND cs.session_date = '2026-08-12'
    """).fetchall()
    for s in sessions_daa:
        print("Session Row:", dict(s))
        att = conn.execute("SELECT * FROM session_attendance WHERE session_id = ?", (s['id'],)).fetchall()
        print("  Attendance Rows for Session:", [dict(a) for a in att])

    print("\n=== 5. RAW ROWS FOR 2024-09-* DAA SESSIONS ===")
    sessions_2024 = conn.execute("""
        SELECT cs.*, sub.name as subject_name
        FROM class_sessions cs
        JOIN subjects sub ON sub.id = cs.subject_id AND sub.semester_id = cs.semester_id
        WHERE cs.session_date LIKE '2024-09%' AND cs.subject_id IN ('DAA', 'DAALAB')
    """).fetchall()
    for s in sessions_2024[:10]: # Print top 10
        print("2024 Session Row:", dict(s))
        att = conn.execute("SELECT * FROM session_attendance WHERE session_id = ?", (s['id'],)).fetchall()
        print("  Attendance Rows:", [dict(a) for a in att])
    print(f"Total 2024-09 DAA/DAALAB sessions count: {len(sessions_2024)}")

    print("\n=== 6. SQL QUERY GENERATING HISTORY ===")
    sql = """
        SELECT
            cs.id AS session_id,
            cs.session_date,
            cs.start_time,
            cs.end_time,
            cs.class_type,
            cs.subject_id,
            sub.name AS subject_name,
            COALESCE(sa.present, 0) AS present
        FROM class_sessions cs
        JOIN subjects sub ON sub.id = cs.subject_id AND sub.semester_id = cs.semester_id
        JOIN student_subjects ss ON ss.subject_id = cs.subject_id AND ss.semester_id = cs.semester_id AND ss.student_id = ?
        LEFT JOIN session_attendance sa ON sa.session_id = cs.id AND sa.student_id = ?
        WHERE cs.semester_id = ?
        ORDER BY cs.session_date DESC, cs.id DESC
    """
    print(sql)

    print("\n=== 7. EXACT API JSON RETURNED FOR /api/attendance/history (for student 992401030315, fall-2024) ===")
    rows = conn.execute(sql, ('992401030315', '992401030315', 'fall-2024')).fetchall()
    json_output = [dict(r) for r in rows]
    print(json.dumps(json_output, indent=2))

import json
import sqlite3
from pathlib import Path

from app.config import DB_PATH
from app.db import get_connection

with get_connection(DB_PATH) as conn:
    print("=" * 80)
    print("1. SQLITE DATABASE PATH")
    print("=" * 80)
    print(f"Path: {DB_PATH.resolve()}")

    print("\n" + "=" * 80)
    print("2. RELEVANT TABLE SCHEMAS")
    print("=" * 80)
    for table in ["students", "student_profile", "subjects", "student_subjects", "class_sessions", "session_attendance", "teacher_assignments"]:
        schema = conn.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'").fetchone()
        if schema:
            print(f"[{table}]")
            print(schema["sql"])
            print()

    print("=" * 80)
    print("3. RAW ROWS FOR DUPLICATE DAA LAB SESSIONS (2026-08-12)")
    print("=" * 80)
    sessions = conn.execute("""
        SELECT cs.*, sub.name as subject_name
        FROM class_sessions cs
        JOIN subjects sub ON sub.id = cs.subject_id AND sub.semester_id = cs.semester_id
        WHERE cs.subject_id IN ('DAALAB', 'DAA') AND cs.session_date = '2026-08-12'
    """).fetchall()
    for s in sessions:
        print("class_sessions row:", dict(s))
        att = conn.execute("SELECT * FROM session_attendance WHERE session_id = ?", (s['id'],)).fetchall()
        print("session_attendance rows:", [dict(a) for a in att])
        print("-" * 40)

    print("\n" + "=" * 80)
    print("4. RAW ROWS FOR 2024 DAA SESSIONS")
    print("=" * 80)
    sessions_2024 = conn.execute("""
        SELECT cs.*, sub.name as subject_name
        FROM class_sessions cs
        JOIN subjects sub ON sub.id = cs.subject_id AND sub.semester_id = cs.semester_id
        WHERE cs.session_date LIKE '2024-09%' AND cs.subject_id IN ('DAA', 'DAALAB')
    """).fetchall()
    for s in sessions_2024:
        print("2024 class_sessions row:", dict(s))
        att = conn.execute("SELECT * FROM session_attendance WHERE session_id = ?", (s['id'],)).fetchall()
        print("session_attendance rows:", [dict(a) for a in att])
        print("-" * 40)

    print("\n" + "=" * 80)
    print("5. SQL QUERY GENERATING STUDENT HISTORY")
    print("=" * 80)
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

    print("\n" + "=" * 80)
    print("6. EXACT STUDENT HISTORY API RESPONSE FOR STUDENT 992401030315 (2026 sessions only view)")
    print("=" * 80)
    rows_all = conn.execute(sql, ('992401030315', '992401030315', 'fall-2024')).fetchall()
    rows_2026 = [dict(r) for r in rows_all if r['session_date'].startswith('2026')]
    print("2026 Session History rows returned to API:")
    print(json.dumps(rows_2026, indent=2))

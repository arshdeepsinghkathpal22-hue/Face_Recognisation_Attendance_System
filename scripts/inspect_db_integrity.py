import sqlite3

conn = sqlite3.connect('attendance.db')
conn.row_factory = sqlite3.Row

print("=== 1. DAA LAB SESSIONS (2026-08-12) ===")
sessions = conn.execute("""
    SELECT cs.id, cs.subject_id, cs.semester_id, cs.class_type, cs.session_date, cs.batch, cs.start_time, cs.end_time, cs.teacher_id, cs.is_active
    FROM class_sessions cs
    WHERE cs.subject_id = 'DAALAB' AND cs.session_date = '2026-08-12'
""").fetchall()
for s in sessions:
    print(dict(s))
    att = conn.execute("SELECT * FROM session_attendance WHERE session_id = ?", (s['id'],)).fetchall()
    print("   Session Attendance:", [dict(a) for a in att])

print("\n=== 2. SESSION HISTORY QUERY RESULTS FOR 992401030315 ===")
query = """
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
rows = conn.execute(query, ('992401030315', '992401030315', 'fall-2024')).fetchall()
for r in rows:
    print(dict(r))

print("\n=== 3. ALL DATES IN CLASS SESSIONS ===")
dates = conn.execute("SELECT session_date, COUNT(*) as count FROM class_sessions GROUP BY session_date ORDER BY session_date ASC").fetchall()
for d in dates:
    print(dict(d))

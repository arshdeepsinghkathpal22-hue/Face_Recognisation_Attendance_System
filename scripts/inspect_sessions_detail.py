import sqlite3

conn = sqlite3.connect('attendance.db')
conn.row_factory = sqlite3.Row

print("=== ALL SESSIONS ON 2026-08-12 ===")
sessions = conn.execute("SELECT * FROM class_sessions WHERE session_date = '2026-08-12'").fetchall()
for s in sessions:
    print(f"Session {s['id']}: subject={s['subject_id']}, type={s['class_type']}, batch='{s['batch']}', start={s['start_time']}, end={s['end_time']}, active={s['is_active']}")
    att = conn.execute("SELECT * FROM session_attendance WHERE session_id = ?", (s['id'],)).fetchall()
    print("   Attendance rows:", [dict(a) for a in att])

print("\n=== ALL ATTENDANCE ROWS FOR STUDENT 992401030315 ===")
att = conn.execute("SELECT * FROM session_attendance WHERE student_id = '992401030315'").fetchall()
for a in att:
    print(dict(a))

print("\n=== ATTENDANCE TABLE (OLD ATTENDANCE TABLE) ===")
try:
    old_att = conn.execute("SELECT * FROM attendance WHERE student_id = '992401030315'").fetchall()
    for a in old_att:
        print(dict(a))
except Exception as e:
    print("Old attendance table error:", e)

import sqlite3
from app.config import DB_PATH

print("=== INSPECTING SESSIONS ON 2026-08-13 ===")
with sqlite3.connect(DB_PATH) as conn:
    conn.row_factory = sqlite3.Row
    sessions = conn.execute("SELECT * FROM class_sessions WHERE session_date = '2026-08-13' ORDER BY id ASC").fetchall()
    for s in sessions:
        print(f"Session {s['id']}: subject={s['subject_id']}, type={s['class_type']}, batch='{s['batch']}', start={s['start_time']}, active={s['is_active']}")
        att = conn.execute("SELECT * FROM session_attendance WHERE session_id = ?", (s['id'],)).fetchall()
        print("  Attendance:", [dict(a) for a in att])

    # Move all attendance from 05:24 / 05:25 sessions into 05:10 session (Session 85)
    primary_session_id = None
    all_sessions_13 = conn.execute("SELECT * FROM class_sessions WHERE session_date = '2026-08-13' AND subject_id = 'DAALAB' ORDER BY id ASC").fetchall()
    if all_sessions_13:
        primary_session_id = all_sessions_13[0]['id']
        for extra in all_sessions_13[1:]:
            extra_id = extra['id']
            # Reassign attendance rows to primary session if not already existing
            att_rows = conn.execute("SELECT * FROM session_attendance WHERE session_id = ?", (extra_id,)).fetchall()
            for a in att_rows:
                conn.execute("""
                    INSERT INTO session_attendance(session_id, student_id, present)
                    VALUES (?, ?, ?)
                    ON CONFLICT(session_id, student_id) DO UPDATE SET present = excluded.present
                """, (primary_session_id, a['student_id'], a['present']))
            conn.execute("DELETE FROM session_attendance WHERE session_id = ?", (extra_id,))
            conn.execute("DELETE FROM class_sessions WHERE id = ?", (extra_id,))
            print(f"Merged extra session {extra_id} into primary session {primary_session_id}.")

    conn.commit()

print("Cleanup of 2026-08-13 sessions complete.")

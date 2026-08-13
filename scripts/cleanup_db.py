import sqlite3
from app.config import DB_PATH

print("Cleaning up database data integrity issues...")
with sqlite3.connect(DB_PATH) as conn:
    # 1. Delete 2024 demo sessions from class_sessions and session_attendance
    res1 = conn.execute("DELETE FROM session_attendance WHERE session_id IN (SELECT id FROM class_sessions WHERE session_date LIKE '2024-09%')")
    res2 = conn.execute("DELETE FROM class_sessions WHERE session_date LIKE '2024-09%'")
    print(f"Deleted {res2.rowcount} obsolete 2024 demo sessions and {res1.rowcount} attendance rows.")

    # 2. Delete empty duplicate sessions where no attendance was ever recorded for anyone, but a conducted session at the exact same date/time/subject exists
    dupes = conn.execute("""
        SELECT cs1.id
        FROM class_sessions cs1
        JOIN class_sessions cs2 ON cs1.subject_id = cs2.subject_id
                               AND cs1.semester_id = cs2.semester_id
                               AND cs1.class_type = cs2.class_type
                               AND cs1.session_date = cs2.session_date
                               AND cs1.start_time = cs2.start_time
                               AND cs1.id <> cs2.id
        WHERE (SELECT COUNT(*) FROM session_attendance sa WHERE sa.session_id = cs1.id) = 0
          AND (SELECT COUNT(*) FROM session_attendance sa WHERE sa.session_id = cs2.id) > 0
    """).fetchall()
    dupe_ids = [r[0] for r in dupes]
    if dupe_ids:
        conn.execute(f"DELETE FROM class_sessions WHERE id IN ({','.join(map(str, dupe_ids))})")
        print(f"Deleted empty duplicate sessions: {dupe_ids}")
    else:
        print("No empty duplicate sessions found.")

    conn.commit()
print("Cleanup complete.")

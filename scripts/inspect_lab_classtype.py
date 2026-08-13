import sqlite3
from app.config import DB_PATH

with sqlite3.connect(DB_PATH) as conn:
    conn.row_factory = sqlite3.Row
    print("=== TEACHER ASSIGNMENTS FOR DAALAB & LAB SUBJECTS ===")
    rows = conn.execute("SELECT * FROM teacher_assignments WHERE subject_id LIKE '%LAB%' OR subject_id LIKE '%PRAC%'").fetchall()
    for r in rows:
        print(dict(r))

    print("\n=== CLASS SESSIONS FOR LAB SUBJECTS ===")
    sessions = conn.execute("SELECT cs.id, cs.subject_id, sub.name as subject_name, cs.class_type, cs.session_date FROM class_sessions cs JOIN subjects sub ON sub.id = cs.subject_id WHERE cs.subject_id LIKE '%LAB%' OR sub.name LIKE '%Lab%' OR cs.class_type = 'P'").fetchall()
    for s in sessions:
        print(dict(s))

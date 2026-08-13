import sqlite3
from app.config import DB_PATH

print("Fixing all Lab subjects to be Practical ('P')...")
with sqlite3.connect(DB_PATH) as conn:
    # 1. Update class_sessions for lab subjects to 'P'
    res1 = conn.execute("""
        UPDATE class_sessions
        SET class_type = 'P'
        WHERE subject_id IN (
            SELECT id FROM subjects WHERE UPPER(id) LIKE '%LAB%' OR UPPER(name) LIKE '%LAB%' OR UPPER(name) LIKE '%PRACTICAL%'
        ) OR UPPER(subject_id) LIKE '%LAB%'
    """)
    print(f"Updated {res1.rowcount} class_sessions rows to class_type='P'.")

    # 2. Update teacher_assignments for lab subjects to 'P'
    res2 = conn.execute("""
        UPDATE teacher_assignments
        SET class_type = 'P'
        WHERE subject_id IN (
            SELECT id FROM subjects WHERE UPPER(id) LIKE '%LAB%' OR UPPER(name) LIKE '%LAB%' OR UPPER(name) LIKE '%PRACTICAL%'
        ) OR UPPER(subject_id) LIKE '%LAB%'
    """)
    print(f"Updated {res2.rowcount} teacher_assignments rows to class_type='P'.")

    conn.commit()

print("Lab class_type fix complete.")

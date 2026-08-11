from app.db import fetch_subject_attendance_counts, get_semester


def _percent(attended: int, held: int) -> int | None:
    if held <= 0:
        return None
    return round((attended / held) * 100)


def build_attendance_summary(
    student_id: str,
    semester_id: str,
    db_path: str,
) -> dict:
    semester = get_semester(semester_id, db_path=db_path)
    if semester is None:
        raise ValueError(f"Semester not found: {semester_id}")

    subject_rows = fetch_subject_attendance_counts(
        student_id=student_id,
        semester_id=semester_id,
        db_path=db_path,
    )

    rows: list[dict] = []
    total_held = 0
    total_attended = 0
    for index, row in enumerate(subject_rows, start=1):
        held_l = int(row["held_l"])
        held_p = int(row["held_p"])
        attended_l = int(row["attended_l"])
        attended_p = int(row["attended_p"])

        held_total = held_l + held_p
        attended_total = attended_l + attended_p
        total_held += held_total
        total_attended += attended_total

        current_l_pct = _percent(attended_l, held_l)
        current_p_pct = _percent(attended_p, held_p)
        overall_pct = _percent(attended_total, held_total)

        rows.append(
            {
                "sl_no": index,
                "subject_name": row["subject_name"],
                "current_l_pct": current_l_pct,
                "current_p_pct": current_p_pct,
                "overall_pct": overall_pct,
            }
        )

    return {
        "semester": semester,
        "total_held": total_held,
        "total_attended": total_attended,
        "total_pct": _percent(total_attended, total_held),
        "rows": rows,
    }

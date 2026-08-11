import sqlite3

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from app.api.schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminMeResponse,
    AdminResponse,
    AdminSemesterOptionResponse,
    AdminStudentsListResponse,
    AdminSubjectOptionResponse,
    AdminTeacherOptionsResponse,
    AdminTeachersListResponse,
    StudentRegisterResponse,
    StudentResponse,
    StudentSubjectsResponse,
    StudentSubjectsUpdateRequest,
    StudentSubjectResponse,
    TeacherAssignmentResponse,
    TeacherAssignmentRequest,
    TeacherRegisterRequest,
    TeacherRegisterResponse,
    TeacherResponse,
)
from app.db import (
    delete_teacher_assignment,
    get_admin_user,
    get_student_with_profile,
    get_teacher_user,
    list_active_semesters,
    list_batches,
    list_students,
    list_student_subjects,
    list_subjects_for_semester,
    list_teacher_assignments,
    list_teacher_users,
    replace_teacher_assignments,
    replace_student_subjects,
    update_admin_password,
    update_teacher_assignment,
    upsert_teacher_assignment,
    upsert_teacher_user,
)
from app.face_utils import EnrollmentValidationError
from app.security import hash_password, password_needs_rehash, verify_password
from app.services.enrollment_service import enroll_student_uploads

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _get_authenticated_admin(request: Request) -> AdminResponse:
    admin_id = request.session.get("admin_id")
    if not admin_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    admin = get_admin_user(admin_id=admin_id, db_path=request.app.state.db_path)
    if admin is None:
        request.session.pop("admin_id", None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    return AdminResponse(admin_id=admin["admin_id"], name=admin["name"])


@router.post("/auth/login", response_model=AdminLoginResponse)
def admin_login(payload: AdminLoginRequest, request: Request) -> AdminLoginResponse:
    admin = get_admin_user(admin_id=payload.admin_id, db_path=request.app.state.db_path)
    if admin is None or not verify_password(payload.password, admin["password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials")
    if password_needs_rehash(admin["password"]):
        update_admin_password(payload.admin_id, hash_password(payload.password), db_path=request.app.state.db_path)

    request.session["admin_id"] = payload.admin_id
    request.session.pop("teacher_id", None)
    request.session.pop("student_id", None)
    return AdminLoginResponse(
        ok=True,
        admin=AdminResponse(admin_id=admin["admin_id"], name=admin["name"]),
    )


@router.post("/auth/logout")
def admin_logout(request: Request) -> dict:
    request.session.pop("admin_id", None)
    return {"ok": True}


@router.get("/me", response_model=AdminMeResponse)
def admin_me(request: Request) -> AdminMeResponse:
    admin_id = request.session.get("admin_id")
    if not admin_id:
        return AdminMeResponse(logged_in=False, admin=None)

    admin = get_admin_user(admin_id=admin_id, db_path=request.app.state.db_path)
    if admin is None:
        request.session.pop("admin_id", None)
        return AdminMeResponse(logged_in=False, admin=None)

    return AdminMeResponse(
        logged_in=True,
        admin=AdminResponse(admin_id=admin["admin_id"], name=admin["name"]),
    )


@router.get("/teacher-options", response_model=AdminTeacherOptionsResponse)
def admin_teacher_options(
    request: Request,
    _: AdminResponse = Depends(_get_authenticated_admin),
) -> AdminTeacherOptionsResponse:
    semesters_payload: list[AdminSemesterOptionResponse] = []
    for semester in list_active_semesters(db_path=request.app.state.db_path):
        subjects = list_subjects_for_semester(
            semester_id=semester["id"],
            db_path=request.app.state.db_path,
        )
        semesters_payload.append(
            AdminSemesterOptionResponse(
                id=semester["id"],
                label=semester["label"],
                subjects=[AdminSubjectOptionResponse(**subject) for subject in subjects],
            )
        )

    batch_options = list(dict.fromkeys([*list_batches(db_path=request.app.state.db_path), "CSE", "CSE-F5", "CSE-F6", "CSE-F10", "F5", "F6", "F10", "F5F6"]))

    return AdminTeacherOptionsResponse(
        semesters=semesters_payload,
        batches=batch_options,
    )


@router.get("/teachers", response_model=AdminTeachersListResponse)
def admin_list_teachers(
    request: Request,
    _: AdminResponse = Depends(_get_authenticated_admin),
) -> AdminTeachersListResponse:
    teachers = list_teacher_users(db_path=request.app.state.db_path)
    return AdminTeachersListResponse(items=[TeacherResponse(**teacher) for teacher in teachers])


@router.get("/students", response_model=AdminStudentsListResponse)
def admin_list_students(
    request: Request,
    _: AdminResponse = Depends(_get_authenticated_admin),
) -> AdminStudentsListResponse:
    students = list_students(db_path=request.app.state.db_path)
    return AdminStudentsListResponse(items=[StudentResponse(**student) for student in students])


@router.get("/students/{student_id}/subjects", response_model=StudentSubjectsResponse)
def admin_get_student_subjects(
    student_id: str,
    request: Request,
    _: AdminResponse = Depends(_get_authenticated_admin),
) -> StudentSubjectsResponse:
    db_path = request.app.state.db_path
    student = get_student_with_profile(student_id=student_id, db_path=db_path)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    rows = list_student_subjects(student_id=student_id, db_path=db_path)
    return StudentSubjectsResponse(
        student_id=student_id,
        subjects=[StudentSubjectResponse(**row) for row in rows],
    )


@router.put("/students/{student_id}/subjects", response_model=StudentSubjectsResponse)
def admin_replace_student_subjects(
    student_id: str,
    payload: StudentSubjectsUpdateRequest,
    request: Request,
    _: AdminResponse = Depends(_get_authenticated_admin),
) -> StudentSubjectsResponse:
    db_path = request.app.state.db_path
    student = get_student_with_profile(student_id=student_id, db_path=db_path)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    normalized_subjects = []
    for item in payload.subjects:
        semester_id = item.semester_id.strip()
        subject_id = item.subject_id.strip()
        subjects = list_subjects_for_semester(semester_id=semester_id, db_path=db_path)
        if not any(subject["id"] == subject_id for subject in subjects):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subject does not belong to selected semester")
        normalized_subjects.append({"semester_id": semester_id, "subject_id": subject_id})

    replace_student_subjects(
        student_id=student_id,
        subject_refs=normalized_subjects,
        db_path=db_path,
    )
    rows = list_student_subjects(student_id=student_id, db_path=db_path)
    return StudentSubjectsResponse(
        student_id=student_id,
        subjects=[StudentSubjectResponse(**row) for row in rows],
    )


@router.post("/teachers/register", response_model=TeacherRegisterResponse)
def register_teacher_via_admin(
    payload: TeacherRegisterRequest,
    request: Request,
    _: AdminResponse = Depends(_get_authenticated_admin),
) -> TeacherRegisterResponse:
    db_path = request.app.state.db_path
    teacher_id = payload.teacher_id.strip()
    teacher_name = payload.name.strip()
    teacher_email = payload.email.strip().lower()
    password = payload.password.strip()

    if not teacher_id or not teacher_name or not teacher_email or not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Teacher ID, name, email, and password are required")
    if not payload.assignments:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Add at least one subject/batch assignment")

    normalized_assignments = []
    for assignment in payload.assignments:
        semester_id = assignment.semester_id.strip()
        subject_id = assignment.subject_id.strip()
        batch = assignment.batch.strip()
        class_type = assignment.class_type.strip().upper()
        if not semester_id or not subject_id or not batch:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assignment semester, subject, and batch are required")
        if class_type not in {"L", "T", "P"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Class type must be L, T, or P")

        subjects = list_subjects_for_semester(semester_id=semester_id, db_path=db_path)
        if not any(subject["id"] == subject_id for subject in subjects):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subject does not belong to selected semester")

        normalized_assignments.append(
            {
                "semester_id": semester_id,
                "subject_id": subject_id,
                "batch": batch,
                "class_type": class_type,
            }
        )

    try:
        upsert_teacher_user(
            teacher_id=teacher_id,
            name=teacher_name,
            email=teacher_email,
            password=password,
            db_path=db_path,
        )
        replace_teacher_assignments(
            teacher_id=teacher_id,
            assignments=normalized_assignments,
            db_path=db_path,
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Teacher ID or email already exists",
        ) from exc
    assignments = list_teacher_assignments(teacher_id=teacher_id, db_path=db_path)

    return TeacherRegisterResponse(
        ok=True,
        teacher=TeacherResponse(teacher_id=teacher_id, name=teacher_name, email=teacher_email),
        assignments=[TeacherAssignmentResponse(**item) for item in assignments],
    )


def _validate_assignment_payload(payload: TeacherAssignmentRequest, db_path: str) -> dict:
    semester_id = payload.semester_id.strip()
    subject_id = payload.subject_id.strip()
    batch = payload.batch.strip()
    class_type = payload.class_type.strip().upper()
    if not semester_id or not subject_id or not batch:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assignment semester, subject, and batch are required")
    if class_type not in {"L", "T", "P"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Class type must be L, T, or P")
    subjects = list_subjects_for_semester(semester_id=semester_id, db_path=db_path)
    if not any(subject["id"] == subject_id for subject in subjects):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subject does not belong to selected semester")
    return {
        "semester_id": semester_id,
        "subject_id": subject_id,
        "batch": batch,
        "class_type": class_type,
    }


@router.post("/teachers/{teacher_id}/assignments", response_model=TeacherAssignmentResponse)
def create_teacher_assignment_via_admin(
    teacher_id: str,
    payload: TeacherAssignmentRequest,
    request: Request,
    _: AdminResponse = Depends(_get_authenticated_admin),
) -> TeacherAssignmentResponse:
    db_path = request.app.state.db_path
    teacher = get_teacher_user(teacher_id=teacher_id, db_path=db_path)
    if teacher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    assignment = _validate_assignment_payload(payload, db_path)
    assignment_id = upsert_teacher_assignment(
        teacher_id=teacher_id,
        semester_id=assignment["semester_id"],
        subject_id=assignment["subject_id"],
        batch=assignment["batch"],
        class_type=assignment["class_type"],
        db_path=db_path,
    )
    rows = list_teacher_assignments(teacher_id=teacher_id, db_path=db_path)
    saved = next((row for row in rows if row["id"] == assignment_id), None)
    if saved is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Assignment save failed")
    return TeacherAssignmentResponse(**saved)


@router.put("/teacher-assignments/{assignment_id}", response_model=TeacherAssignmentResponse)
def update_teacher_assignment_via_admin(
    assignment_id: int,
    payload: TeacherAssignmentRequest,
    request: Request,
    _: AdminResponse = Depends(_get_authenticated_admin),
) -> TeacherAssignmentResponse:
    db_path = request.app.state.db_path
    assignment = _validate_assignment_payload(payload, db_path)
    try:
        update_teacher_assignment(
            assignment_id=assignment_id,
            semester_id=assignment["semester_id"],
            subject_id=assignment["subject_id"],
            batch=assignment["batch"],
            class_type=assignment["class_type"],
            db_path=db_path,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    teachers = list_teacher_users(db_path=db_path)
    for teacher in teachers:
        for row in list_teacher_assignments(teacher_id=teacher["teacher_id"], db_path=db_path):
            if row["id"] == assignment_id:
                return TeacherAssignmentResponse(**row)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")


@router.delete("/teacher-assignments/{assignment_id}")
def delete_teacher_assignment_via_admin(
    assignment_id: int,
    request: Request,
    _: AdminResponse = Depends(_get_authenticated_admin),
) -> dict:
    try:
        delete_teacher_assignment(assignment_id=assignment_id, db_path=request.app.state.db_path)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"ok": True}


@router.post("/students/register", response_model=StudentRegisterResponse)
async def register_student_via_admin(
    request: Request,
    student_id: str = Form(..., min_length=1),
    name: str = Form(..., min_length=1),
    branch: str = Form(..., min_length=1),
    batch: str = Form(""),
    images: list[UploadFile] = File(...),
    _: AdminResponse = Depends(_get_authenticated_admin),
) -> StudentRegisterResponse:
    db_path = request.app.state.db_path
    normalized_student_id = student_id.strip()
    normalized_name = name.strip()
    normalized_branch = branch.strip()
    normalized_batch = (batch.strip() or normalized_branch)

    if not images:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload/capture 5-15 face images")

    try:
        enrollment = await enroll_student_uploads(
            student_id=normalized_student_id,
            name=normalized_name,
            branch=normalized_branch,
            batch=normalized_batch,
            images=images,
            db_path=db_path,
            filename_prefix="admin",
        )
        from app.api.teacher import _invalidate_known_faces_cache

        _invalidate_known_faces_cache()
    except EnrollmentValidationError as exc:
        detail = {"message": str(exc), "results": exc.results}
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Enrollment failed: {exc}",
        ) from exc

    return StudentRegisterResponse(
        ok=True,
        student=StudentResponse(**enrollment["student"]),
        uploaded_images=enrollment["uploaded_images"],
        valid_images=enrollment["valid_images"],
        rejected_images=enrollment["rejected_images"],
        results=enrollment["results"],
    )
